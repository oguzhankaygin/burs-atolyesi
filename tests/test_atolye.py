import copy
import http.client
import io
import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from atolye.analysis import SECTIONS, parse_response, validate_form, validate_response
from atolye.llm import choose_provider, EvaluationError, load_dotenv
from atolye.server import MAX_BODY, WorkshopHandler, WorkshopServer

FORM = {
    "program_adi": "İklim Atölyesi",
    "program_aciklamasi": "Sıcaklık ölçümü ve veri atölyesi.",
    "soru": "Neden başvuruyorsun?",
    "deneyimler": "- 6 noktada sıcaklık ölçtüm.",
    "taslak": "Fark yaratmak istiyorum. Başarılı bir liderim.",
    "karakter_siniri": 20,
    "kelime_siniri": 20,
}
MISSING_ENV = Path(__file__).parent / "missing.env"


def provider(env=None, force_demo=False):
    return choose_provider(force_demo, env or {}, MISSING_ENV)


def llm_result():
    return {
        "bolumler": {key: {"puan": 2, "gerekce": "Bir ayrıntı eklenebilir.", "soru": "Ne yaptın?"}
                     for key in SECTIONS},
        "zayif_cumleler": [],
        "kontrol_listesi": ["Bir ayrıntı ekledim."],
    }


def suggestion(quote):
    return {"alinti": quote, "tur": "genel/klişe", "aciklama": "A" * 400, "oneri": "B" * 500}


class ValidationTests(unittest.TestCase):
    def test_validation_trims_and_checks_quotes(self):
        data = llm_result()
        data["bolumler"]["motivasyon"].update(puan=8, gerekce="G" * 400)
        data["bolumler"]["uyum"].update(puan=-4, soru="")
        data["zayif_cumleler"] = [
            suggestion("Taslakta olmayan cümle."),
            suggestion("Fark yaratmak istiyorum."),
            suggestion("Fark yaratmak istiyorum."),
        ]
        data["tam_yanit"] = "Atılacak bilinmeyen alan."
        result = validate_response(data, FORM)
        self.assertEqual(result["bolumler"]["motivasyon"], {"puan": 3, "gerekce": "G" * 360, "soru": ""})
        self.assertEqual(result["bolumler"]["uyum"]["puan"], 0)
        self.assertTrue(result["bolumler"]["uyum"]["soru"])
        self.assertNotIn("tam_yanit", result)
        self.assertEqual(result["zayif_cumleler"], [{
            "alinti": "Fark yaratmak istiyorum.", "tur": "genel/klişe",
            "aciklama": "A" * 300, "oneri": "B" * 360,
        }])
        self.assertEqual(len(result["kontrol_listesi"]), 5)
        self.assertEqual(result["sinir_kontrolu"]["karakter"]["asim"], len(FORM["taslak"]) - 20)
        self.assertEqual(result["sinir_kontrolu"]["kelime"], {"sayi": 6, "sinir": 20, "asim": 0})

    def test_collection_caps(self):
        quotes = [f"Cümle {i}." for i in range(14)]
        data = llm_result()
        data["zayif_cumleler"] = [suggestion(quote) for quote in quotes]
        data["kontrol_listesi"] = [f"Madde {i}" for i in range(10)]
        result = validate_response(data, dict(FORM, taslak=" ".join(quotes)))
        self.assertEqual(len(result["zayif_cumleler"]), 12)
        self.assertEqual(len(result["kontrol_listesi"]), 8)

    def test_invalid_form_and_schema(self):
        for form in ([], dict(FORM, taslak=" "), dict(FORM, soru="ş" * 1001),
                     dict(FORM, taslak="\ud800"), dict(FORM, kelime_siniri=True),
                     dict(FORM, karakter_siniri=0)):
            with self.subTest(form=form), self.assertRaises(ValueError):
                validate_form(form)
        with self.assertRaises(ValueError):
            validate_response({"bolumler": {}}, FORM)
        data = llm_result()
        data["bolumler"]["kanit"]["puan"] = True
        with self.assertRaises(ValueError):
            validate_response(data, FORM)

    def test_fenced_json(self):
        self.assertEqual(parse_response('  ```json\n{"a": 3}\n```  '), {"a": 3})
        self.assertEqual(parse_response('{"a": 3}'), {"a": 3})
        self.assertEqual(parse_response("İşte:\n```json\n{\"a\": 4}\n```\nBitti"), {"a": 4})
        self.assertEqual(parse_response("Tamam {\"a\": 5} bitti"), {"a": 5})


class ProviderTests(unittest.TestCase):
    def test_provider_precedence_defaults_and_override(self):
        self.assertEqual(provider().status(), {"saglayici": "demo", "model": None, "demo": True})
        keys = {"ANTHROPIC_API_KEY": "a", "OPENROUTER_API_KEY": "b"}
        with patch.dict("os.environ", keys, clear=True):
            self.assertEqual(choose_provider(dotenv_path=MISSING_ENV).model, "claude-sonnet-5-5")
        self.assertEqual(provider(keys, True).name, "demo")
        self.assertEqual(provider({"OPENROUTER_API_KEY": "b"}).model, "anthropic/claude-haiku-5.5")
        self.assertEqual(provider(dict(keys, ATOLYE_MODEL="override")).model, "override")
        self.assertNotIn("key=", repr(provider(keys)))

    def test_dotenv_and_environment_override(self):
        with patch.object(Path, "read_text", return_value=(
            "# comment\nexport OPENROUTER_API_KEY='file key'\nATOLYE_MODEL = from-file\nOTHER=x"
        )):
            self.assertEqual(load_dotenv(MISSING_ENV), {
                "OPENROUTER_API_KEY": "file key", "ATOLYE_MODEL": "from-file",
            })
            chosen = provider({"OPENROUTER_API_KEY": "environment key"})
        self.assertEqual(chosen.key, "environment key")
        self.assertEqual(chosen.model, "from-file")

    def test_demo_deterministic(self):
        form = validate_form(dict(FORM, taslak=FORM["taslak"] + " " + "ayrıntı " * 29 + "bitti."))
        demo = provider()
        first = demo.evaluate(form)
        self.assertEqual(first, demo.evaluate(copy.deepcopy(form)))
        self.assertEqual(set(first["bolumler"]), set(SECTIONS))
        self.assertEqual([row["tur"] for row in first["zayif_cumleler"]],
                         ["genel/klişe", "kanıtsız iddia", "uzun"])
        self.assertTrue(all("[" in row["oneri"] for row in first["zayif_cumleler"]))

    def test_remote_provider_requests_are_mocked(self):
        content = "```json\n" + json.dumps(llm_result()) + "\n```"
        cases = (
            ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/messages",
             {"content": [{"type": "text", "text": content}]}),
            ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/chat/completions",
             {"choices": [{"message": {"content": content}}]}),
        )
        for env_key, url, body in cases:
            with self.subTest(env_key=env_key), patch("atolye.llm.urllib.request.urlopen") as opened:
                opened.return_value = io.BytesIO(json.dumps(body).encode())
                result = provider({env_key: "mock-key"}).evaluate(
                    dict(FORM, soru="</basvuru_verisi>")
                )
                request = opened.call_args.args[0]
                self.assertEqual(request.full_url, url)
                self.assertEqual(opened.call_args.kwargs["timeout"], 90)
                payload = json.loads(request.data)
                message = payload["messages"][-1]["content"]
                self.assertEqual(message.count("</basvuru_verisi>"), 1)
                self.assertIn(r"\u003c", message)
                self.assertEqual(result["bolumler"]["uyum"]["puan"], 2)
                headers = dict(request.header_items())
                if env_key == "ANTHROPIC_API_KEY":
                    self.assertEqual(headers["Anthropic-version"], "2023-06-01")
                    self.assertEqual(headers["X-api-key"], "mock-key")
                else:
                    self.assertEqual(headers["Authorization"], "Bearer mock-key")
                    self.assertEqual(payload["messages"][0]["role"], "system")

    def test_invalid_provider_response_is_sanitized(self):
        with patch("atolye.llm.urllib.request.urlopen", return_value=io.BytesIO(b"{}")):
            with self.assertRaisesRegex(EvaluationError, "geçerli bir değerlendirme"):
                provider({"ANTHROPIC_API_KEY": "mock-key"}).evaluate(FORM)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.server = WorkshopServer(("127.0.0.1", 0), provider())
        except PermissionError:
            # TCP soketinin yasak olduğu ortamlarda aynı işleyiciye HTTP gönder.
            cls.server = None
            return
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        if cls.server is None:
            return
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def test_foreign_host_rejected(self):
        for method, path, body in (("GET", "/api/durum", None), ("POST", "/api/degerlendir", b"{}")):
            status, _, _ = self.request(method, path, body,
                                        {"Host": "saldirgan.example", "X-Atolye-Request": "1",
                                         "Content-Type": "application/json"})
            self.assertEqual(status, 403)

    def request(self, method, path, body=None, headers=None):
        if self.server is None:
            incoming = io.BytesIO()
            outgoing = io.BytesIO()
            connection = http.client.HTTPConnection("localhost")
            connection.sock = SimpleNamespace(sendall=incoming.write)
            connection.request(method, path, body, headers or {})
            incoming.seek(0)
            request = SimpleNamespace(
                settimeout=lambda seconds: None,
                makefile=lambda mode, size: incoming,
                sendall=outgoing.write,
            )

            def handle():
                WorkshopHandler(request, ("localhost", 0), SimpleNamespace(provider=provider(), server_address=("127.0.0.1", 80)))

            thread = Thread(target=handle)
            thread.start()
            thread.join()
            response = http.client.HTTPResponse(
                SimpleNamespace(makefile=lambda mode: io.BytesIO(outgoing.getvalue()))
            )
            response.begin()
            return response.status, dict(response.getheaders()), response.read()
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_status_and_static_security_headers(self):
        status, headers, body = self.request("GET", "/api/durum")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), provider().status())
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        for route, mime in (("/", "text/html"), ("/app.js", "text/javascript"), ("/style.css", "text/css")):
            status, headers, body = self.request("GET", route)
            self.assertEqual(status, 200)
            self.assertTrue(headers["Content-Type"].startswith(mime))
            self.assertTrue(body)
        self.assertEqual(self.request("GET", "/.env")[0], 404)

    def test_evaluation_statuses(self):
        required = {"Content-Type": "application/json", "X-Atolye-Request": "1"}
        valid = json.dumps(FORM).encode()
        cases = (
            (403, valid, {}),
            (403, valid, dict(required, **{"X-Atolye-Request": "0"})),
            (413, b" " * (MAX_BODY + 1), required),
            (400, b"{", required),
            (400, b"{}", required),
            (400, valid, dict(required, **{"Content-Type": "text/plain"})),
            (200, valid.ljust(MAX_BODY), required),
            (200, valid, required),
        )
        for expected, payload, headers in cases:
            with self.subTest(expected=expected, length=len(payload)):
                code, _, raw = self.request("POST", "/api/degerlendir", payload, headers)
                self.assertEqual(code, expected)
                data = json.loads(raw)
                if expected == 200:
                    self.assertEqual(set(data["bolumler"]), set(SECTIONS))
                else:
                    self.assertTrue(data["hata"])

