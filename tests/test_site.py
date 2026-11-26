import json
from pathlib import Path
import unittest

from atolye.analysis import parse_response, validate_response
from atolye.build import DOCS, site_files
from atolye.demo import demo_response

CASES = json.loads(Path(__file__).with_name("vakalar.json").read_text(encoding="utf-8"))


class SiteTests(unittest.TestCase):
    def test_generated_site_is_current(self):
        actual = {path.relative_to(DOCS): path.read_bytes()
                  for path in DOCS.rglob("*") if path.is_file()}
        expected_files = site_files()
        self.assertEqual(set(actual), set(expected_files))
        for path, expected in expected_files.items():
            with self.subTest(path=path):
                self.assertEqual(actual[path], expected, "python3 -m atolye build-site")

    def test_static_mode_blocks_requests_and_submissions(self):
        index = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn("connect-src 'none'", index)
        self.assertIn("form-action 'none'", index)
        self.assertIn("staticMode = true", (DOCS / "config.mjs").read_text(encoding="utf-8"))

    def test_shared_response_cases(self):
        for case in CASES["responses"]:
            form = case.get("form", CASES["form"])
            with self.subTest(case=case["name"]):
                if "error" in case:
                    with self.assertRaises(ValueError) as error:
                        validate_response(parse_response(case["raw"]), form)
                    if case["error"]:
                        self.assertEqual(str(error.exception), case["error"])
                else:
                    self.assertEqual(validate_response(parse_response(case["raw"]), form),
                                     case["expected"])

    def test_shared_demo_cases(self):
        for case in CASES["demo"]:
            with self.subTest(case=case["name"]):
                form = dict(CASES["form"], **case["form"])
                self.assertEqual(validate_response(demo_response(form), form), case["expected"])


class OfflineTests(unittest.TestCase):
    def test_service_worker_caches_existing_site_files(self):
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")
        liste = json.loads(sw.split("const DOSYALAR = ", 1)[1].split(";\n", 1)[0])
        self.assertIn("./index.html", liste)
        for dosya in liste[1:]:
            self.assertTrue((DOCS / dosya).is_file(), dosya)
