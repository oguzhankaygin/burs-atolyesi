"""Yerel, kurallara dayalı geri bildirim."""

import re

from .analysis import CHECKLIST

CLICHES = (
    "kendimi geliştirmek", "fark yaratmak", "hayallerimi gerçekleştirmek",
    "çocukluğumdan beri", "büyük bir fırsat", "en büyük hayalim",
)
EVIDENCE = r"\d|\b(?:proje|atölye|araştırma|staj|gönüllü|rapor|ekip)\w*"
WORD = re.compile(r"[^\W\d_]{5,}", re.UNICODE)
STOP_WORDS = {"program", "programa", "programın", "başvuru", "olarak", "kendi", "birlikte"}


def demo_response(form):
    draft = form["taslak"]
    lower = draft.translate(str.maketrans("Iİ", "ıi")).lower()
    motivation = bool(re.search(r"istiyorum|hedef|ilgim|başvuruyorum|öğrenmek", lower))
    timing = bool(re.search(r"bu yıl|şimdi|dönem|sonrasında|son sınıf", lower))
    evidence = bool(re.search(EVIDENCE, lower))
    outcome = bool(re.search(r"sonuc|tamamla|ölçt|ulaşt|teslim|yayımla|sundum", lower))
    words = set(WORD.findall(lower)) - STOP_WORDS
    program = (form["program_adi"] + " " + form["program_aciklamasi"])
    program = program.translate(str.maketrans("Iİ", "ıi")).lower()
    matches = words.intersection(WORD.findall(program))
    future = bool(re.search(r"sonra|gelecek|aktaracağ|paylaşacağ|uygulayacağ", lower))
    action = bool(re.search(r"atölye|oturum|sunum|kılavuz|rapor|eğitim", lower))

    def section(score, present, missing, question):
        return {"puan": score, "gerekce": present if score else missing, "soru": question}

    sections = {
        "motivasyon": section(
            2 * motivation + timing, "Taslakta bir hedef veya zamanlama işareti var.",
            "Alana ilgin ve başvuru zamanlaman taslakta belirsiz.",
            "Bu alana yönelmene ne sebep oldu ve neden şimdi başvuruyorsun?",
        ),
        "kanit": section(
            evidence + outcome + bool(re.search(r"\d", lower)),
            "Taslakta bir deneyim, ölçü veya sonuç işareti var.",
            "Taslakta somut bir deneyim veya sonuç görünmüyor.",
            "Hangi deneyimde ne yaptın ve sonucunu nasıl gözlemledin?",
        ),
        "uyum": section(
            min(2, len(matches)), "Taslak ve program açıklamasında ortak sözcükler var.",
            "Programla bağlantıyı görünür kılan bir ayrıntı bulunamadı.",
            "Program metnindeki hangi imkân, üzerinde çalıştığın hangi hedefe uyuyor?",
        ),
        "gelecek": section(
            2 * future + (future and action), "Taslakta geleceğe dönük bir ifade var.",
            "Program sonrasındaki planın taslakta görünmüyor.",
            "Programdan sonra öğrendiklerini kiminle, hangi ilk adımla paylaşacaksın?",
        ),
    }
    weak = []
    for match in re.finditer(r".+?(?:[!?]+|\.(?!\S)|$)", draft, re.M):
        sentence = match.group().strip()
        if not sentence:
            continue
        plain = sentence.lower()
        if any(item in plain for item in CLICHES):
            issue = ("genel/klişe", "Bu ifade sana özgü bir neden göstermiyor.",
                     "[Seni başvuruya yönelten deneyim] sırasında [ilgini çeken konuyu] fark ettim.")
        elif len(sentence.split()) > 28:
            issue = ("uzun", "Cümlenin ana fikrini takip etmek zorlaşıyor.",
                     "[Cümlenin ana fikri]. [Bu fikri destekleyen tek ayrıntı].")
        elif re.search(r"başarılı|lider|etkili|yetenek|beceri|disiplin", plain) and not re.search(EVIDENCE, plain):
            issue = ("kanıtsız iddia", "Bu iddiayı destekleyen bir eylem veya sonuç görünmüyor.",
                     "[Deneyim] sırasında [üstlendiğin görev] ile [gözlemlediğin sonuç] elde ettim.")
        else:
            continue
        kind, explanation, suggestion = issue
        weak.append({"alinti": sentence, "tur": kind, "aciklama": explanation, "oneri": suggestion})
        if len(weak) == 12:
            break
    return {"bolumler": sections, "zayif_cumleler": weak, "kontrol_listesi": list(CHECKLIST)}
