import { buildPrompt, charCount, parseResponse, sections, trim, validateResponse, wordCount } from "./analysis.mjs";
import { demoResponse } from "./demo.mjs";
import { staticMode } from "./config.mjs";
import { systemPrompt } from "./prompt.mjs";

const byId = (id) => document.getElementById(id);
const form = byId("application");
const draft = byId("draft");
const saveDraft = byId("save-draft");
const fields = ["program_adi", "program_aciklamasi", "soru", "deneyimler", "taslak",
  "karakter_siniri", "kelime_siniri"];
const storageKey = "burs-atolyesi-taslak-v1";
const example = {
  program_adi: "Kent ve İklim Gençlik Programı",
  program_aciklamasi: "Program, lise öğrencilerine mahalle ölçeğinde iklim gözlemi yapmayı öğretir. Katılımcılar veri okuryazarlığı atölyelerine katılır, bir mentorla çalışır ve sonuçlarını yerel bir sunumda paylaşır.",
  soru: "Bu programa neden başvuruyorsunuz?",
  deneyimler: "- Okulun çevre kulübünde 3 arkadaşımla bahçenin gölgeli ve güneşli alanlarını belirledim.\n- 2 hafta boyunca 6 noktada sıcaklık ölçüp sonuçları okul panosunda paylaştım.\n- Gelecek dönem yeni kulüp üyelerine ölçüm yöntemimizi anlatmak istiyorum.",
  taslak: "Bu programa kendimi geliştirmek ve fark yaratmak için başvuruyorum. Çevre kulübünde iki hafta boyunca okul bahçesinin 6 noktasında sıcaklık ölçtüm. Başarılı bir ekip lideriyim. Veri okuryazarlığı atölyesinde ölçümlerimi yorumlamayı öğrenmek istiyorum. Programdan sonra çevre kulübünde bir oturum düzenleyeceğim.",
  karakter_siniri: "",
  kelime_siniri: "100",
};

function element(tag, value, className) {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (className) node.className = className;
  return node;
}

function fill(values) {
  for (const name of fields) {
    if (typeof values[name] === "string") form.elements.namedItem(name).value = values[name];
  }
  updateCount();
}

function updateCount() {
  byId("live-count").value = `${charCount(draft.value)} karakter · ${wordCount(draft.value)} kelime`;
}

function showError(message) {
  const error = byId("error");
  error.textContent = message;
  error.hidden = !message;
}

function persistDraft() {
  try {
    if (saveDraft.checked) {
      localStorage.setItem(storageKey, JSON.stringify(Object.fromEntries(new FormData(form))));
    } else {
      localStorage.removeItem(storageKey);
    }
  } catch {
    saveDraft.checked = false;
    byId("form-status").textContent = "Tarayıcı taslağı kaydetmeye izin vermedi.";
  }
}

function restoreDraft() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (saved && typeof saved === "object") {
      fill(saved);
      saveDraft.checked = true;
    }
  } catch {
    // Depolama kapalı veya önceki taslak okunamıyor.
  }
  updateCount();
}

function renderScores(scores) {
  const cards = Object.entries(sections).map(([key, title]) => {
    const row = scores[key];
    const card = element("article", undefined, "score");
    const head = element("div", undefined, "score-head");
    head.append(element("strong", title), element("span", `${row.puan}/3`));
    const meter = element("meter");
    meter.max = 3;
    meter.value = row.puan;
    meter.setAttribute("aria-label", title);
    card.append(head, meter, element("p", row.gerekce));
    if (row.soru) card.append(element("p", row.soru, "question"));
    return card;
  });
  byId("scores").replaceChildren(...cards);
}

function renderLimits(limits) {
  const rows = Object.entries(limits).map(([unit, details]) => {
    let text = `${details.sayi} ${unit}`;
    if (details.sinir !== null) {
      text += ` · sınır ${details.sinir}`;
      text += details.asim ? ` · ${details.asim} ${unit} fazla` : " · sınır içinde";
    }
    return element("li", text, details.asim ? "over" : "");
  });
  byId("limits").replaceChildren(...rows);
}

function renderSuggestions(rows, text) {
  const cards = rows.map((row) => {
    const card = element("article", undefined, "suggestion");
    card.tabIndex = -1;
    card.append(element("strong", row.tur), element("blockquote", row.alinti),
      element("p", row.aciklama), element("p", `Öneri — ${row.oneri}`, "rewrite"));
    return card;
  });
  byId("suggestions").replaceChildren(...(cards.length ? cards : [
    element("p", "Bu değerlendirmede vurgulanacak cümle bulunmadı.", "muted"),
  ]));

  const fragment = document.createDocumentFragment();
  let cursor = 0;
  while (cursor < text.length) {
    let next = null;
    rows.forEach((row, index) => {
      const start = text.indexOf(row.alinti, cursor);
      if (start !== -1 && (!next || start < next.start ||
          (start === next.start && row.alinti.length > next.quote.length))) {
        next = { start, quote: row.alinti, index };
      }
    });
    if (!next) {
      fragment.append(text.slice(cursor));
      break;
    }
    fragment.append(text.slice(cursor, next.start));
    // Satır içinde kırılabilsin diye düğme yerine erişilebilir bir span kullanılır.
    const mark = element("span", next.quote, "highlight");
    mark.tabIndex = 0;
    mark.setAttribute("role", "button");
    mark.title = "Cümle önerisine git";
    const target = cards[next.index];
    const go = () => {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "center" });
    };
    mark.addEventListener("click", go);
    mark.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); go(); }
    });
    fragment.append(mark);
    cursor = next.start + next.quote.length;
  }
  byId("annotated").replaceChildren(fragment);
}

function renderResult(data, text) {
  renderScores(data.bolumler);
  renderLimits(data.sinir_kontrolu);
  renderSuggestions(data.zayif_cumleler, text);
  byId("checklist").replaceChildren(...data.kontrol_listesi.map((item) => {
    const label = element("label", undefined, "check");
    const input = element("input");
    input.type = "checkbox";
    label.append(input, element("span", item));
    return label;
  }));
  byId("empty").hidden = true;
  byId("results").hidden = false;
  byId("feedback-title").focus();
}

function resetResult() {
  byId("empty").hidden = false;
  byId("results").hidden = true;
  for (const id of ["scores", "limits", "annotated", "suggestions", "checklist"]) {
    byId(id).replaceChildren();
  }
  showError("");
  byId("form-status").textContent = "";
}

async function evaluateOnServer(values) {
  const button = byId("evaluate");
  const controls = [...form.elements, byId("example")].filter((control) => !control.disabled);
  controls.forEach((control) => { control.disabled = true; });
  byId("feedback").setAttribute("aria-busy", "true");
  button.textContent = "Değerlendiriliyor…";
  byId("form-status").textContent = "Taslağın inceleniyor.";
  try {
    const response = await fetch("/api/degerlendir", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Atolye-Request": "1" },
      body: JSON.stringify(values),
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.hata || "Değerlendirme tamamlanamadı.");
      return;
    }
    renderResult(data, values.taslak);
  } catch {
    showError("Değerlendirme alınamadı. Bağlantını kontrol edip tekrar dene.");
  } finally {
    controls.forEach((control) => { control.disabled = false; });
    button.textContent = "Taslağı sunucuda değerlendir";
    byId("feedback").removeAttribute("aria-busy");
    byId("form-status").textContent = "";
  }
}

let activePrompt;

async function openClaude(values) {
  const guide = byId("claude-guide");
  const fallback = byId("prompt-fallback");
  const prompt = byId("prompt");
  const status = byId("form-status");
  const text = buildPrompt(systemPrompt, values);
  activePrompt = text;
  guide.open = true;
  // Panoya yazma ve yeni sekme açma aynı kullanıcı etkileşiminde başlatılır.
  let copy;
  try {
    copy = navigator.clipboard?.writeText(text);
  } catch {
    // Bazı tarayıcılar panoya erişimi eşzamanlı olarak reddeder.
  }
  window.open("https://claude.ai/new", "_blank", "noopener,noreferrer");
  try {
    if (!copy) throw new Error();
    await copy;
    if (activePrompt !== text) return;
    status.textContent = "İstem kopyalandı. Claude sohbetine yapıştırıp gönder.";
  } catch {
    if (activePrompt !== text) return;
    prompt.value = text;
    fallback.hidden = false;
    prompt.focus();
    prompt.select();
    status.textContent = "Panoya otomatik kopyalanamadı. Seçili istemi kopyala.";
  }
}

function submit(event) {
  event.preventDefault();
  clearClaudePrompt();
  const values = Object.fromEntries(new FormData(form));
  for (const name of fields.slice(-2)) values[name] = values[name] ? Number(values[name]) : null;
  resetResult();
  const empty = fields.slice(0, -2).find((name) => !trim(values[name]));
  if (empty) {
    const input = form.elements.namedItem(empty);
    showError("Bu alanı doldur.");
    input.focus();
    return;
  }

  switch (event.submitter?.id) {
    case "claude":
      openClaude(values);
      break;
    case "parse": {
      let response;
      try {
        response = parseResponse(byId("claude-response").value);
      } catch {
        showError("Claude’un yanıtı okunamadı. JSON yanıtının tamamını yapıştır.");
        byId("claude-response").focus();
        return;
      }
      try {
        renderResult(validateResponse(response, values), values.taslak);
      } catch (error) {
        showError(error.message);
        byId("claude-response").focus();
      }
      break;
    }
    case "evaluate":
      if (!staticMode) evaluateOnServer(values);
      break;
    default:
      renderResult(validateResponse(demoResponse(values), values), values.taslak);
  }
}

function clearClaudePrompt() {
  activePrompt = undefined;
  byId("prompt").value = "";
  byId("prompt-fallback").hidden = true;
}

async function loadStatus() {
  const badge = byId("provider");
  try {
    const response = await fetch("/api/durum");
    if (!response.ok) throw new Error();
    const status = await response.json();
    badge.textContent = status.demo ? "Demo modu" :
      status.saglayici === "anthropic" ? "Anthropic" : "OpenRouter";
  } catch {
    badge.textContent = "Sağlayıcı durumu alınamadı";
  }
  badge.hidden = false;
}

restoreDraft();
if (staticMode) {
  byId("privacy").hidden = false;
  // Pages sürümü bir kez açıldıktan sonra internetsiz de çalışsın.
  navigator.serviceWorker?.register("./sw.js").catch(() => {});
} else {
  byId("evaluate").hidden = false;
  loadStatus();
}
form.addEventListener("input", () => {
  updateCount();
  persistDraft();
});
form.addEventListener("submit", submit);
byId("example").addEventListener("click", () => {
  clearClaudePrompt();
  byId("claude-response").value = "";
  resetResult();
  fill(example);
  persistDraft();
  form.elements.namedItem(fields[0]).focus();
});
byId("clear").addEventListener("click", () => {
  form.reset();
  clearClaudePrompt();
  byId("claude-guide").open = false;
  resetResult();
  updateCount();
  persistDraft();
  form.elements.namedItem(fields[0]).focus();
});
