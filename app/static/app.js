/* Tahqeeq front end. Vanilla JS, no build step, no framework.
   Everything user-supplied goes through textContent or a DOM node — never
   innerHTML — because the whole point of this app is that people paste
   untrusted text into it. */

(() => {
  "use strict";

  const TOKEN_KEY = "tahqeeq.token";
  const state = { token: localStorage.getItem(TOKEN_KEY) || "", user: null, view: "check" };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ---------- tiny DOM helper ----------
  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else node.setAttribute(key, value);
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  // ---------- api ----------
  async function api(path, { method = "GET", body, auth = true } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (auth && state.token) headers.Authorization = `Bearer ${state.token}`;

    const response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (response.status === 204) return null;

    let payload = null;
    try { payload = await response.json(); } catch { /* empty body */ }

    if (!response.ok) {
      if (response.status === 401 && auth) signOut();
      const detail = payload && payload.detail ? payload.detail : `Request failed (${response.status}).`;
      throw new Error(typeof detail === "string" ? detail : "That request was rejected.");
    }
    return payload;
  }

  // ---------- verdict styling ----------
  const VERDICT_STYLE = {
    credible:        { color: "var(--good)", soft: "var(--good-soft)" },
    "mostly-credible": { color: "var(--ok)",   soft: "var(--ok-soft)" },
    mixed:           { color: "var(--warn)", soft: "var(--warn-soft)" },
    questionable:    { color: "var(--bad)",  soft: "var(--bad-soft)" },
    unreliable:      { color: "var(--bad)",  soft: "var(--bad-soft)" },
  };
  const styleFor = (verdict) => VERDICT_STYLE[verdict] || VERDICT_STYLE.mixed;

  // ---------- views ----------
  function showView(name) {
    state.view = name;
    for (const view of $$(".view")) view.hidden = view.id !== `view-${name}`;
    for (const btn of $$("[data-view]")) {
      btn.classList.toggle("is-active", btn.dataset.view === name);
    }
    if (name === "history") loadHistory();
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function setError(form, message) {
    const box = $("[data-error]", form);
    if (!box) return;
    box.textContent = message || "";
    box.hidden = !message;
  }

  // ---------- auth ----------
  function applySession(token, user) {
    state.token = token;
    state.user = user;
    localStorage.setItem(TOKEN_KEY, token);
    $("#signout").hidden = false;
    showView("check");
  }

  function signOut() {
    state.token = "";
    state.user = null;
    localStorage.removeItem(TOKEN_KEY);
    $("#signout").hidden = true;
    $("#result").hidden = true;
    showView("auth");
  }

  async function handleAuth(form, path) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      setError(form, "");
      const button = $("button[type=submit]", form);
      button.disabled = true;
      const data = Object.fromEntries(new FormData(form).entries());
      try {
        const payload = await api(path, { method: "POST", body: data, auth: false });
        applySession(payload.access_token, payload.user);
        form.reset();
      } catch (error) {
        setError(form, error.message);
      } finally {
        button.disabled = false;
      }
    });
  }

  handleAuth($("#form-login"), "/api/auth/login");
  handleAuth($("#form-register"), "/api/auth/register");

  $("#demo-login").addEventListener("click", async () => {
    const form = $("#form-login");
    setError(form, "");
    try {
      const payload = await api("/api/auth/login", {
        method: "POST",
        body: { email: "demo@tahqeeq.app", password: "tahqeeq-demo-2026" },
        auth: false,
      });
      applySession(payload.access_token, payload.user);
    } catch (error) {
      setError(form, `${error.message} The demo account may not be seeded on this instance.`);
    }
  });

  $("#signout").addEventListener("click", signOut);

  // ---------- tabs ----------
  for (const tab of $$(".tab")) {
    tab.addEventListener("click", () => {
      for (const other of $$(".tab")) other.classList.toggle("is-active", other === tab);
      for (const pane of $$("[data-pane]")) pane.hidden = pane.dataset.pane !== tab.dataset.tab;
    });
  }

  // ---------- counters ----------
  const textArea = $("#text");
  function updateCounts() {
    const value = textArea.value;
    const words = value.trim() ? value.trim().split(/\s+/).length : 0;
    $("#wordcount").textContent = `${words.toLocaleString()} word${words === 1 ? "" : "s"}`;
    $("#charcount").textContent = `${value.length.toLocaleString()} characters`;
  }
  textArea.addEventListener("input", updateCounts);
  updateCounts();

  // ---------- samples ----------
  const SAMPLES = [
    {
      headline: "SHOCKING: They don't want you to know the REAL truth about Karachi",
      text: `SHOCKING!!! They don't want you to know the REAL truth about what happened in Karachi last night!!!

A friend of a senior official has revealed that a MASSIVE cover-up is underway. Sources say that thousands of people were affected but the mainstream media won't report it. This is UNDENIABLE proof that the deep state is hiding everything from you.

Experts say this is the biggest scandal in the country's history and nobody is talking about it. The government has completely destroyed the evidence. It is being reported that the real number is in the millions.

SHARE THIS BEFORE THEY DELETE IT!!! Forward to everyone you know. Do your own research. Wake up before it's too late!`,
    },
    {
      headline: "State Bank holds policy rate at 11 percent as inflation eases",
      text: `Pakistan's central bank held its policy rate at 11 percent on Monday, citing easing inflation.

The State Bank of Pakistan said in a statement that inflation had slowed to 4.9 percent in October from 6.2 percent a month earlier. "We expect inflation to remain within the target range over the coming quarters," Governor Jameel Ahmad told reporters in Karachi.

According to the bank's monetary policy report published on 10 November 2026, food prices rose 3.1 percent while core inflation held at 7.4 percent. Analysts at Topline Securities said the decision was widely expected.

The next policy meeting is scheduled for 15 December 2026.`,
    },
  ];
  let sampleIndex = 0;

  $("#load-sample").addEventListener("click", () => {
    const sample = SAMPLES[sampleIndex % SAMPLES.length];
    sampleIndex += 1;
    $("#headline").value = sample.headline;
    textArea.value = sample.text;
    updateCounts();
    textArea.focus();
  });

  // ---------- analyze ----------
  $("#form-analyze").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    setError(form, "");
    const button = $("#submit-analyze");
    button.disabled = true;
    button.textContent = "Reading…";

    const activeTab = $(".tab.is-active").dataset.tab;
    try {
      let result;
      if (activeTab === "link") {
        const url = $("#url").value.trim();
        if (!url) throw new Error("Paste a link first, or switch to the text tab.");
        result = await api("/api/analyze-url", { method: "POST", body: { url } });
      } else {
        const text = textArea.value.trim();
        if (text.length < 20) throw new Error("Paste at least a couple of sentences.");
        const headline = $("#headline").value.trim();
        result = await api("/api/analyze", {
          method: "POST",
          body: { text, headline: headline || null },
        });
      }
      renderResult(result);
    } catch (error) {
      setError(form, error.message);
    } finally {
      button.disabled = false;
      button.textContent = "Check it";
    }
  });

  // ---------- result rendering ----------
  function gauge(score, color) {
    const radius = 46;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100);

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "108");
    svg.setAttribute("height", "108");
    svg.setAttribute("viewBox", "0 0 108 108");
    svg.setAttribute("aria-hidden", "true");

    const track = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    track.setAttribute("class", "gauge-track");
    track.setAttribute("cx", "54");
    track.setAttribute("cy", "54");
    track.setAttribute("r", String(radius));
    track.setAttribute("fill", "none");
    track.setAttribute("stroke-width", "7");

    const fill = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    fill.setAttribute("class", "gauge-fill");
    fill.setAttribute("cx", "54");
    fill.setAttribute("cy", "54");
    fill.setAttribute("r", String(radius));
    fill.setAttribute("fill", "none");
    fill.setAttribute("stroke-width", "7");
    fill.setAttribute("stroke", color);
    fill.setAttribute("stroke-dasharray", String(circumference));
    fill.setAttribute("stroke-dashoffset", String(circumference));

    svg.append(track, fill);
    requestAnimationFrame(() => fill.setAttribute("stroke-dashoffset", String(offset)));

    return el("div", { class: "gauge" }, [svg, el("div", { class: "gauge-num", text: String(Math.round(score)) })]);
  }

  function renderResult(report) {
    const style = styleFor(report.verdict);
    const container = $("#result");
    container.replaceChildren();
    container.hidden = false;

    const applicable = report.signals.filter((s) => s.applicable);
    const skipped = report.signals.filter((s) => !s.applicable);
    const ranked = [...applicable].sort((a, b) => b.points_lost - a.points_lost);

    // --- score header ---
    const header = el("div", { class: "score-top" }, [
      gauge(report.score, style.color),
      el("div", { class: "verdict" }, [
        el("span", {
          class: "pill",
          text: report.verdict_label,
          style: `background:${style.soft};color:${style.color}`,
        }),
        el("h2", { text: report.headline || "Untitled text" }),
        el("p", {
          text: `${Math.round(report.confidence * 100)}% confidence · ${report.word_count.toLocaleString()} words · about ${report.reading_seconds}s to read`,
        }),
      ]),
    ]);

    // --- meta ---
    const metaBits = [];
    if (report.domain) {
      metaBits.push(el("span", {}, [el("b", { text: "Source: " }), report.domain.domain]));
      metaBits.push(el("span", {}, [el("b", { text: "Publisher: " }), report.domain.label]));
    }
    metaBits.push(el("span", {}, [el("b", { text: "Signals run: " }), `${applicable.length} of ${report.signals.length}`]));
    const meta = el("div", { class: "meta-row" }, metaBits);

    // --- notes ---
    const notes = report.notes && report.notes.length
      ? el("div", { class: "notes" }, report.notes.map((note) => el("p", { text: note })))
      : null;

    // --- signals ---
    const signalNodes = ranked.map((signal) => {
      const costly = signal.points_lost >= 25;
      const width = Math.max(2, Math.round(signal.severity * 100));
      const barColor = signal.severity >= 0.6 ? "var(--bad)" : signal.severity >= 0.3 ? "var(--warn)" : "var(--good)";

      return el("div", { class: "signal" }, [
        el("div", { class: "signal-top" }, [
          el("span", { class: "signal-name", text: signal.label }),
          el("span", {
            class: `signal-cost${costly ? " is-costly" : ""}`,
            text: signal.points_lost > 0 ? `−${signal.points_lost} pts` : "no cost",
          }),
        ]),
        el("div", { class: "bar" }, [
          el("div", { class: "bar-fill", style: `width:${width}%;background:${barColor}` }),
        ]),
        el("p", { text: signal.explanation }),
        signal.evidence && signal.evidence.length
          ? el("div", { class: "evidence" }, signal.evidence.map((item) => el("span", { class: "chip", text: item })))
          : null,
      ]);
    });

    const skippedNodes = skipped.map((signal) =>
      el("div", { class: "signal is-skipped" }, [
        el("div", { class: "signal-top" }, [
          el("span", { class: "signal-name", text: signal.label }),
          el("span", { class: "signal-cost", text: "excluded" }),
        ]),
        el("p", { text: signal.explanation }),
      ])
    );

    const signalsBlock = el("div", { class: "signals" }, [
      el("div", { class: "signals-head" }, [
        el("h3", { text: "What cost it points" }),
        el("span", { text: "worst first" }),
      ]),
      ...signalNodes,
      ...skippedNodes,
    ]);

    // --- actions ---
    const shareButton = el("button", { class: "btn btn-ghost btn-small", type: "button", text: "Copy share link" });
    shareButton.addEventListener("click", async () => {
      shareButton.disabled = true;
      try {
        const shared = await api(`/api/analyses/${report.id}/share`, { method: "POST" });
        const link = `${location.origin}${shared.url}`;
        await navigator.clipboard.writeText(link);
        shareButton.textContent = "Link copied";
      } catch (error) {
        shareButton.textContent = "Could not copy";
        console.error(error);
      } finally {
        setTimeout(() => { shareButton.disabled = false; shareButton.textContent = "Copy share link"; }, 2200);
      }
    });

    const actions = el("div", { class: "score-actions" }, [
      shareButton,
      el("button", {
        class: "btn btn-ghost btn-small",
        type: "button",
        text: "Check something else",
        onclick: () => {
          container.hidden = true;
          textArea.value = "";
          $("#headline").value = "";
          $("#url").value = "";
          updateCounts();
          textArea.focus();
          window.scrollTo({ top: 0, behavior: "smooth" });
        },
      }),
    ]);

    container.append(el("div", { class: "score-card" }, [header, meta, notes, signalsBlock, actions]));
    container.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------- history ----------
  async function loadHistory() {
    const list = $("#history-list");
    const stats = $("#stat-row");
    list.replaceChildren(el("p", { class: "empty", text: "Loading…" }));

    try {
      const [page, summary] = await Promise.all([api("/api/analyses?limit=50"), api("/api/stats")]);

      stats.replaceChildren(
        el("div", { class: "stat" }, [el("b", { text: String(summary.total_analyses) }), el("span", { text: "Checked" })]),
        el("div", { class: "stat" }, [el("b", { text: summary.average_score.toFixed(1) }), el("span", { text: "Average score" })]),
        el("div", { class: "stat" }, [el("b", { text: String(summary.last_7_days) }), el("span", { text: "Last 7 days" })]),
        el("div", { class: "stat" }, [
          el("b", { text: String(summary.by_verdict.unreliable || 0) }),
          el("span", { text: "Unreliable" }),
        ])
      );

      if (!page.items.length) {
        list.replaceChildren(el("p", { class: "empty", text: "Nothing checked yet. Paste something and see what it says." }));
        return;
      }

      list.replaceChildren(
        ...page.items.map((item) => {
          const style = styleFor(item.verdict);
          const when = new Date(item.created_at).toLocaleString(undefined, {
            day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
          });
          return el("button", { class: "history-item", type: "button" }, [
            el("span", { class: "history-score", text: String(Math.round(item.score)), style: `color:${style.color}` }),
            el("span", { class: "history-body" }, [
              el("p", { class: "history-title", text: item.headline || "Untitled text" }),
              el("p", { class: "history-sub", text: `${item.verdict_label} · ${item.word_count} words · ${when}` }),
            ]),
          ]);
        })
      );

      for (const [index, node] of Array.from(list.children).entries()) {
        node.addEventListener("click", async () => {
          try {
            const report = await api(`/api/analyses/${page.items[index].id}`);
            showView("check");
            renderResult(report);
          } catch (error) {
            console.error(error);
          }
        });
      }
    } catch (error) {
      list.replaceChildren(el("p", { class: "empty", text: error.message }));
    }
  }

  // ---------- nav ----------
  for (const btn of $$("[data-view]")) {
    btn.addEventListener("click", () => showView(btn.dataset.view));
  }

  // ---------- boot ----------
  (async function boot() {
    if (!state.token) { showView("auth"); return; }
    try {
      state.user = await api("/api/auth/me");
      $("#signout").hidden = false;
      showView("check");
    } catch {
      signOut();
    }
  })();
})();
