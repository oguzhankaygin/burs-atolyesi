"""Form ve değerlendirme verisinin doğrulanması."""

import json
import re

SECTIONS = {
    "motivasyon": "Motivasyon",
    "kanit": "Kanıt",
    "uyum": "Uyum",
    "gelecek": "Katkı / Gelecek",
}
ISSUES = ("genel/klişe", "kanıtsız iddia", "uzun", "pasif", "konu dışı")
FIELDS = {
    "program_adi": ("Program adı", 200),
    "program_aciklamasi": ("Program açıklaması", 10000),
    "soru": ("Başvuru sorusu", 1000),
    "deneyimler": ("Deneyimler", 6000),
    "taslak": ("Taslak", 12000),
}
LIMITS = {"karakter_siniri": "Karakter sınırı", "kelime_siniri": "Kelime sınırı"}
CHECKLIST = (
    "Bu alana neden şimdi başvurduğumu açıkladım.",
    "İddialarımı somut deneyimlerimle destekledim.",
    "Deneyimimdeki rolümü ve sonucunu belirttim.",
    "Program açıklamasındaki bir imkânı hedefimle ilişkilendirdim.",
    "Programdan sonra atacağım adımı belirttim.",
    "Soruya odaklandım ve varsa uzunluk sınırına uydum.",
)


def validate_form(data):
    if not isinstance(data, dict):
        raise ValueError("Form bir JSON nesnesi olmalı.")
    result = {}
    for key, (label, maximum) in FIELDS.items():
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} boş bırakılamaz.")
        if len(value) > maximum:
            raise ValueError(f"{label} en fazla {maximum} karakter olabilir.")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError(f"{label} geçersiz karakter içeriyor.") from None
        result[key] = value

    for key, label in LIMITS.items():
        value = data.get(key)
        if value is not None and (type(value) is not int or not 1 <= value <= 100000):
            raise ValueError(f"{label} 1 ile 100.000 arasında bir tam sayı olmalı.")
        result[key] = value
    return result


def count_limits(form):
    draft = form["taslak"]
    return {
        unit: {
            "sayi": count,
            "sinir": form[f"{unit}_siniri"],
            "asim": max(0, count - form[f"{unit}_siniri"])
            if form[f"{unit}_siniri"] is not None else 0,
        }
        for unit, count in (("karakter", len(draft)), ("kelime", len(draft.split())))
    }


def parse_response(raw):
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.I | re.S)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except ValueError:
        # Model JSON'un önüne/arkasına kısa bir açıklama eklerse ilk nesneyi al.
        start = text.find("{")
        if start == -1:
            raise
        return json.JSONDecoder().raw_decode(text[start:])[0]


def clean_text(value, maximum):
    if not isinstance(value, str):
        return ""
    return value[:maximum].encode("utf-8", errors="replace").decode("utf-8").strip()


def validate_response(data, form):
    if not isinstance(data, dict) or not isinstance(data.get("bolumler"), dict):
        raise ValueError("Değerlendirme bölümleri eksik.")
    sections = {}
    for key in SECTIONS:
        row = data["bolumler"].get(key)
        if not isinstance(row, dict) or type(row.get("puan")) is not int:
            raise ValueError("Bölüm puanı geçersiz.")
        score = min(3, max(0, row["puan"]))
        reason = clean_text(row.get("gerekce"), 360)
        if not reason:
            raise ValueError("Bölüm gerekçesi eksik.")
        question = clean_text(row.get("soru"), 240)
        sections[key] = {
            "puan": score,
            "gerekce": reason,
            "soru": (question or "Bu bölümü hangi somut ayrıntıyla güçlendirebilirsin?")
            if score < 3 else "",
        }

    weak = []
    seen = set()
    rows = data.get("zayif_cumleler")
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        quote = row.get("alinti")
        issue = row.get("tur")
        explanation = clean_text(row.get("aciklama"), 300)
        suggestion = clean_text(row.get("oneri"), 360)
        if (not isinstance(quote, str) or not quote.strip() or len(quote) > 1500
                or quote not in form["taslak"] or quote in seen or issue not in ISSUES
                or not explanation or not suggestion):
            continue
        seen.add(quote)
        weak.append({"alinti": quote, "tur": issue, "aciklama": explanation, "oneri": suggestion})
        if len(weak) == 12:
            break

    items = data.get("kontrol_listesi")
    checklist = []
    for item in items if isinstance(items, list) else []:
        item = clean_text(item, 180)
        if item and item not in checklist:
            checklist.append(item)
        if len(checklist) == 8:
            break
    for item in CHECKLIST:
        if len(checklist) >= 5:
            break
        if item not in checklist:
            checklist.append(item)

    return {"bolumler": sections, "zayif_cumleler": weak,
            "kontrol_listesi": checklist, "sinir_kontrolu": count_limits(form)}
