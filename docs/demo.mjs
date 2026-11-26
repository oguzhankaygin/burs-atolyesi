import { checklist, trim, wordCount } from "./analysis.mjs";

const cliches = [
  "kendimi geliştirmek", "fark yaratmak", "hayallerimi gerçekleştirmek",
  "çocukluğumdan beri", "büyük bir fırsat", "en büyük hayalim",
];
const evidencePattern = /\p{Nd}|(?<![\p{L}\p{N}_])(?:proje|atölye|araştırma|staj|gönüllü|rapor|ekip)/u;
const stopWords = new Set(["program", "programa", "programın", "başvuru", "olarak", "kendi", "birlikte"]);
const lowerTurkish = (text) => text.replaceAll("I", "ı").replaceAll("İ", "i").toLowerCase();
const words = (text) => text.match(/[\p{L}\p{Nl}\p{No}]{5,}/gu) ?? [];

export function demoResponse(form) {
  const lower = lowerTurkish(form.taslak);
  const motivation = /istiyorum|hedef|ilgim|başvuruyorum|öğrenmek/.test(lower);
  const timing = /bu yıl|şimdi|dönem|sonrasında|son sınıf/.test(lower);
  const evidence = evidencePattern.test(lower);
  const outcome = /sonuc|tamamla|ölçt|ulaşt|teslim|yayımla|sundum/.test(lower);
  const program = new Set(words(lowerTurkish(`${form.program_adi} ${form.program_aciklamasi}`)));
  const matches = [...new Set(words(lower))].filter((word) => !stopWords.has(word) && program.has(word));
  const future = /sonra|gelecek|aktaracağ|paylaşacağ|uygulayacağ/.test(lower);
  const action = /atölye|oturum|sunum|kılavuz|rapor|eğitim/.test(lower);

  const section = (score, present, missing, question) => ({
    puan: score, gerekce: score ? present : missing, soru: question,
  });
  const sections = {
    motivasyon: section(
      2 * motivation + timing, "Taslakta bir hedef veya zamanlama işareti var.",
      "Alana ilgin ve başvuru zamanlaman taslakta belirsiz.",
      "Bu alana yönelmene ne sebep oldu ve neden şimdi başvuruyorsun?",
    ),
    kanit: section(
      Number(evidence) + Number(outcome) + Number(/\p{Nd}/u.test(lower)),
      "Taslakta bir deneyim, ölçü veya sonuç işareti var.",
      "Taslakta somut bir deneyim veya sonuç görünmüyor.",
      "Hangi deneyimde ne yaptın ve sonucunu nasıl gözlemledin?",
    ),
    uyum: section(
      Math.min(2, matches.length), "Taslak ve program açıklamasında ortak sözcükler var.",
      "Programla bağlantıyı görünür kılan bir ayrıntı bulunamadı.",
      "Program metnindeki hangi imkân, üzerinde çalıştığın hangi hedefe uyuyor?",
    ),
    gelecek: section(
      2 * future + Number(future && action), "Taslakta geleceğe dönük bir ifade var.",
      "Program sonrasındaki planın taslakta görünmüyor.",
      "Programdan sonra öğrendiklerini kiminle, hangi ilk adımla paylaşacaksın?",
    ),
  };
  const weak = [];
  const sentences = /[^\n]+?(?:[!?]+|\.(?![^\u0009-\u000d\u001c-\u0020\u0085\p{Z}])|(?=\n|$))/gu;
  for (const [match] of form.taslak.matchAll(sentences)) {
    const sentence = trim(match);
    if (!sentence) continue;
    const plain = sentence.toLowerCase();
    let issue;
    if (cliches.some((item) => plain.includes(item))) {
      issue = ["genel/klişe", "Bu ifade sana özgü bir neden göstermiyor.",
        "[Seni başvuruya yönelten deneyim] sırasında [ilgini çeken konuyu] fark ettim."];
    } else if (wordCount(sentence) > 28) {
      issue = ["uzun", "Cümlenin ana fikrini takip etmek zorlaşıyor.",
        "[Cümlenin ana fikri]. [Bu fikri destekleyen tek ayrıntı]."];
    } else if (/başarılı|lider|etkili|yetenek|beceri|disiplin/.test(plain) && !evidencePattern.test(plain)) {
      issue = ["kanıtsız iddia", "Bu iddiayı destekleyen bir eylem veya sonuç görünmüyor.",
        "[Deneyim] sırasında [üstlendiğin görev] ile [gözlemlediğin sonuç] elde ettim."];
    } else {
      continue;
    }
    const [kind, explanation, suggestion] = issue;
    weak.push({ alinti: sentence, tur: kind, aciklama: explanation, oneri: suggestion });
    if (weak.length === 12) break;
  }
  return { bolumler: sections, zayif_cumleler: weak, kontrol_listesi: [...checklist] };
}
