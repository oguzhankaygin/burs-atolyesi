export const sections = {
  motivasyon: "Motivasyon",
  kanit: "Kanıt",
  uyum: "Uyum",
  gelecek: "Katkı / Gelecek",
};

const issues = ["genel/klişe", "kanıtsız iddia", "uzun", "pasif", "konu dışı"];
export const checklist = [
  "Bu alana neden şimdi başvurduğumu açıkladım.",
  "İddialarımı somut deneyimlerimle destekledim.",
  "Deneyimimdeki rolümü ve sonucunu belirttim.",
  "Program açıklamasındaki bir imkânı hedefimle ilişkilendirdim.",
  "Programdan sonra atacağım adımı belirttim.",
  "Soruya odaklandım ve varsa uzunluk sınırına uydum.",
];
const whitespace = "[\\u0009-\\u000d\\u001c-\\u0020\\u0085\\p{Z}]";
export const trim = (text) => text.replace(new RegExp(`^${whitespace}+|${whitespace}+$`, "gu"), "");
export const wordCount = (text) => text.match(new RegExp(`[^${whitespace.slice(1)}+`, "gu"))?.length ?? 0;
export const charCount = (text) => Array.from(text).length;
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const clean = (value, limit) => typeof value === "string"
  ? trim(Array.from(value).slice(0, limit).join("").replace(/[\uD800-\uDFFF]/gu, "?")) : "";

export function countLimits(form) {
  return Object.fromEntries([
    ["karakter", charCount(form.taslak)], ["kelime", wordCount(form.taslak)],
  ].map(([unit, count]) => {
    const limit = form[`${unit}_siniri`] ?? null;
    return [unit, { sayi: count, sinir: limit, asim: Math.max(0, count - (limit ?? count)) }];
  }));
}

function decode(text) {
  // Python, ondalık ve üslü JSON sayılarını tam sayı olarak kabul etmez.
  const normalized = text.replace(/"(?:[^"\\]|\\[\s\S])*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|-?Infinity|NaN/g,
    (token) => {
      if (token.startsWith('"')) return token;
      if (/[.eE]|Infinity|NaN/.test(token)) return "null";
      // Çok büyük tam sayılarda yalnızca puan aralığının hangi ucu olduğu önemli.
      if (!Number.isFinite(Number(token))) return token.startsWith("-") ? "-1" : "4";
      return token;
    });
  return JSON.parse(normalized);
}

export function parseResponse(raw) {
  let text = trim(raw);
  const fenced = /```(?:json)?([\s\S]*?)```/i.exec(text);
  if (fenced) text = trim(fenced[1]);
  try {
    return decode(text);
  } catch (error) {
    const start = text.indexOf("{");
    if (start === -1) throw error;
    let depth = 0;
    const tokens = /"(?:[^"\\]|\\[\s\S])*"|[{}]/g;
    tokens.lastIndex = start;
    for (const match of text.matchAll(tokens)) {
      if (match[0] === "{") depth += 1;
      if (match[0] === "}" && --depth === 0) return decode(text.slice(start, match.index + 1));
    }
    throw error;
  }
}

export function validateResponse(data, form) {
  if (!object(data) || !object(data.bolumler)) throw new Error("Değerlendirme bölümleri eksik.");
  const scores = {};
  for (const key of Object.keys(sections)) {
    const row = data.bolumler[key];
    if (!object(row) || !Number.isInteger(row.puan)) throw new Error("Bölüm puanı geçersiz.");
    const score = Math.min(3, Math.max(0, row.puan));
    const reason = clean(row.gerekce, 360);
    if (!reason) throw new Error("Bölüm gerekçesi eksik.");
    const question = clean(row.soru, 240);
    scores[key] = { puan: score, gerekce: reason, soru: score < 3
      ? question || "Bu bölümü hangi somut ayrıntıyla güçlendirebilirsin?" : "" };
  }

  const weak = [];
  const seen = new Set();
  for (const row of Array.isArray(data.zayif_cumleler) ? data.zayif_cumleler : []) {
    if (!object(row)) continue;
    const { alinti: quote, tur: issue } = row;
    const explanation = clean(row.aciklama, 300);
    const suggestion = clean(row.oneri, 360);
    if (typeof quote !== "string" || !trim(quote) || charCount(quote) > 1500 ||
        !form.taslak.includes(quote) || seen.has(quote) || !issues.includes(issue) ||
        !explanation || !suggestion) continue;
    seen.add(quote);
    weak.push({ alinti: quote, tur: issue, aciklama: explanation, oneri: suggestion });
    if (weak.length === 12) break;
  }

  const items = new Set();
  for (const value of Array.isArray(data.kontrol_listesi) ? data.kontrol_listesi : []) {
    const item = clean(value, 180);
    if (item) items.add(item);
    if (items.size === 8) break;
  }
  for (const item of checklist) {
    if (items.size >= 5) break;
    items.add(item);
  }

  return { bolumler: scores, zayif_cumleler: weak, kontrol_listesi: [...items],
    sinir_kontrolu: countLimits(form) };
}

export function buildPrompt(systemPrompt, form) {
  const data = JSON.stringify(form).replaceAll("<", "\\u003c").replaceAll(">", "\\u003e");
  return `${systemPrompt.trim()}\n\n<basvuru_verisi>\n${data}\n</basvuru_verisi>\n\nYanıtı yalnızca JSON olarak ver.`;
}
