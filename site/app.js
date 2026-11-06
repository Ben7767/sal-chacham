// סל חכם – Tech4U
(() => {
  const $ = (s) => document.querySelector(s);
  const state = { chains: [], items: [], byCode: new Map(), basket: {} };
  const STORE_KEY = "salchacham.basket.v1";

  const fmt = (n) => (n == null ? "—" : "₪" + n.toFixed(2));
  const norm = (s) => (s || "").toLowerCase().replace(/["'`׳״\-.,()]/g, " ").replace(/\s+/g, " ").trim();

  function loadBasket() {
    try { state.basket = JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch { state.basket = {}; }
  }
  function saveBasket() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state.basket)); } catch {}
    $("#basketCount").textContent = Object.keys(state.basket).length;
  }

  // ---------- data ----------
  async function load() {
    const res = await fetch("data/prices.json", { cache: "no-cache" });
    const data = await res.json();
    state.chains = data.chains;
    state.items = data.items.map(([code, name, brand, qty, unit, prices, promos]) => ({
      code, name, brand, qty, unit, prices, promos,
      key: norm(name + " " + brand),
    }));
    state.items.forEach((it) => state.byCode.set(it.code, it));
    $("#updated").textContent = `עודכן: ${data.updated} · ${state.items.length.toLocaleString("he-IL")} מוצרים להשוואה · ${state.chains.map((c) => c.name).join(", ")}`;
    $("#demoBanner").hidden = !data.demo;
    for (const code of Object.keys(state.basket)) if (!state.byCode.has(code)) delete state.basket[code];
    saveBasket();
    renderBasket();
  }

  const sizeText = (it) => {
    const q = String(it.qty || "").replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
    const u = it.unit === "לא ידוע" ? "" : it.unit;
    return [q, u].filter((x) => x && x !== "0").join(" ");
  };
  const minIdx = (arr) => {
    let best = -1;
    arr.forEach((v, i) => { if (v != null && (best < 0 || v < arr[best])) best = i; });
    return best;
  };

  // ---------- search ----------
  function search(q) {
    const nq = norm(q);
    if (!nq) return [];
    if (/^\d{4,}$/.test(nq)) return state.items.filter((it) => it.code.includes(nq)).slice(0, 40);
    const words = nq.split(" ");
    const hits = [];
    for (const it of state.items) {
      if (words.every((w) => it.key.includes(w))) {
        hits.push(it);
        if (hits.length > 400) break;
      }
    }
    hits.sort((a, b) => (b.key.startsWith(words[0]) - a.key.startsWith(words[0])) || a.name.length - b.name.length);
    return hits.slice(0, 40);
  }

  function priceChips(it) {
    const best = minIdx(it.prices);
    return state.chains.map((c, i) => {
      const p = it.prices[i], pr = it.promos[i];
      if (p == null) return `<div class="chip na"><span class="cn">${c.name}</span><span class="cp">אין</span></div>`;
      return `<div class="chip ${i === best ? "best" : ""}"><span class="cn">${c.name}</span><span class="cp">${fmt(p)}</span>${
        pr ? `<span class="promo">✦ ${escapeHtml(pr[2] || "מבצע")}</span>` : ""}</div>`;
    }).join("");
  }

  function renderResults() {
    const q = $("#q").value;
    const list = search(q);
    $("#hint").textContent = !q ? "התחל להקליד כדי לחפש מבין כל המוצרים שמופיעים ביותר מרשת אחת."
      : list.length ? `נמצאו ${list.length}${list.length === 40 ? "+" : ""} מוצרים` : "לא נמצאו מוצרים. נסה מילה אחרת או ברקוד.";
    $("#results").innerHTML = list.map((it) => {
      const inB = state.basket[it.code];
      return `<li class="card">
        <div class="card-head">
          <div><div class="pname">${escapeHtml(it.name)}</div>
          <div class="pmeta">${escapeHtml(it.brand)} ${sizeText(it) ? "· " + escapeHtml(sizeText(it)) : ""} · ${it.code}</div></div>
          <button class="btn ${inB ? "added" : ""}" data-add="${it.code}">${inB ? "✓ בסל" : "+ לסל"}</button>
        </div>
        <div class="prices">${priceChips(it)}</div>
      </li>`;
    }).join("");
  }

  // ---------- basket ----------
  function lineCost(it, i, qty, usePromos) {
    const p = it.prices[i];
    if (p == null) return null;
    const pr = usePromos ? it.promos[i] : null;
    if (pr && qty >= pr[1]) {
      const promoUnits = Math.floor(qty / pr[1]) * pr[1];
      return promoUnits * pr[0] + (qty - promoUnits) * p;
    }
    return qty * p;
  }

  function renderBasket() {
    const codes = Object.keys(state.basket);
    $("#basketEmpty").hidden = codes.length > 0;
    $("#basketWrap").hidden = codes.length === 0;
    if (!codes.length) return;
    const usePromos = $("#usePromos").checked;
    const n = state.chains.length;
    const fair = Array(n).fill(0), all = Array(n).fill(0), missing = Array(n).fill(0);
    let split = 0, fairCount = 0;

    const rows = codes.map((code) => {
      const it = state.byCode.get(code), qty = state.basket[code];
      const costs = state.chains.map((_, i) => lineCost(it, i, qty, usePromos));
      const inAll = costs.every((c) => c != null);
      const best = minIdx(costs);
      costs.forEach((c, i) => {
        if (c == null) missing[i]++; else all[i] += c;
        if (inAll) fair[i] += c;
      });
      if (inAll) fairCount++;
      if (inAll && best >= 0) split += costs[best];
      const cells = costs.map((c, i) => {
        if (c == null) return `<td class="price na">אין</td>`;
        const promoUsed = usePromos && it.promos[i] && qty >= it.promos[i][1];
        return `<td class="price ${i === best ? "best" : ""}">${fmt(c)}${promoUsed ? " ✦" : ""}</td>`;
      }).join("");
      return `<tr><td class="prod"><div class="pname">${escapeHtml(it.name)}</div>
        <div class="pmeta">${escapeHtml(it.brand)} ${escapeHtml(sizeText(it))}</div>
        <div class="qty"><button data-dec="${code}" aria-label="פחות">−</button><span>${qty}</span><button data-inc="${code}" aria-label="יותר">+</button></div>
        </td>${cells}</tr>`;
    }).join("");

    const head = `<thead><tr><th>מוצר</th>${state.chains.map((c) => `<th>${c.name}</th>`).join("")}</tr></thead>`;
    const foot = `<tfoot><tr><td class="prod">סה"כ (${fairCount} מוצרים שיש בכל הרשתות)</td>${
      fair.map((v, i) => `<td class="${i === minIdx(fair) ? "best" : ""}">${fmt(v)}</td>`).join("")}</tr></tfoot>`;
    $("#compare").innerHTML = head + "<tbody>" + rows + "</tbody>" + foot;

    const win = fairCount ? minIdx(fair) : -1;
    const maxFair = Math.max(...fair);
    $("#totals").innerHTML = state.chains.map((c, i) => `
      <div class="total ${i === win ? "win" : ""}">
        <div class="tn">${i === win ? "🏆 " : ""}${c.name}</div>
        <div class="tv">${fmt(fairCount ? fair[i] : null)}</div>
        <div class="td">${i === win && maxFair > fair[i] ? `חוסך ${fmt(maxFair - fair[i])} מול היקרה` : missing[i] ? (missing[i] === 1 ? "חסר מוצר 1" : `חסרים ${missing[i]} מוצרים`) : "&nbsp;"}</div>
      </div>`).join("") + `
      <div class="total split">
        <div class="tn">כל מוצר בזול ביותר</div>
        <div class="tv">${fmt(split)}</div>
        <div class="td">אם מפצלים את הקנייה בין הרשתות</div>
      </div>`;
  }

  function setQty(code, qty) {
    if (qty <= 0) delete state.basket[code]; else state.basket[code] = qty;
    saveBasket(); renderBasket(); renderResults();
  }

  // ---------- barcode scanner (Chrome on Android) ----------
  let stream = null, scanning = false;
  async function startScan() {
    try {
      const detector = new BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      const video = $("#video");
      video.srcObject = stream; await video.play();
      $("#scanner").hidden = false; scanning = true;
      const tick = async () => {
        if (!scanning) return;
        try {
          const codes = await detector.detect(video);
          if (codes.length) { $("#q").value = codes[0].rawValue; stopScan(); renderResults(); return; }
        } catch {}
        requestAnimationFrame(tick);
      };
      tick();
    } catch (e) {
      alert("לא ניתן לפתוח את המצלמה: " + e.message);
      stopScan();
    }
  }
  function stopScan() {
    scanning = false;
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null; $("#scanner").hidden = true;
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---------- events ----------
  let t;
  $("#q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(renderResults, 120); });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.add) { const c = b.dataset.add; setQty(c, state.basket[c] ? 0 : 1); }
    if (b.dataset.inc) setQty(b.dataset.inc, state.basket[b.dataset.inc] + 1);
    if (b.dataset.dec) setQty(b.dataset.dec, state.basket[b.dataset.dec] - 1);
    if (b.dataset.tab) {
      document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
      $("#tab-search").hidden = b.dataset.tab !== "search";
      $("#tab-basket").hidden = b.dataset.tab !== "basket";
      if (b.dataset.tab === "basket") renderBasket();
    }
  });
  $("#usePromos").addEventListener("change", renderBasket);
  $("#clearBasket").addEventListener("click", () => { state.basket = {}; saveBasket(); renderBasket(); renderResults(); });
  if ("BarcodeDetector" in window) {
    $("#scanBtn").hidden = false;
    $("#scanBtn").addEventListener("click", startScan);
    $("#scanClose").addEventListener("click", stopScan);
  }

  loadBasket();
  load().catch((e) => { $("#updated").textContent = "שגיאה בטעינת המחירים: " + e.message; });
})();
