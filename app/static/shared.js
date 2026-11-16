/* Public shared-report page. Read-only, no auth, no account.
   Reuses the same rendering rules as the main app but without the actions. */

(() => {
  "use strict";

  const VERDICT_STYLE = {
    credible: { color: "var(--good)", soft: "var(--good-soft)" },
    "mostly-credible": { color: "var(--ok)", soft: "var(--ok-soft)" },
    mixed: { color: "var(--warn)", soft: "var(--warn-soft)" },
    questionable: { color: "var(--bad)", soft: "var(--bad-soft)" },
    unreliable: { color: "var(--bad)", soft: "var(--bad-soft)" },
  };

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else node.setAttribute(key, value);
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function gauge(score, color) {
    const radius = 46;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100);
    const ns = "http://www.w3.org/2000/svg";

    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("width", "108");
    svg.setAttribute("height", "108");
    svg.setAttribute("viewBox", "0 0 108 108");
    svg.setAttribute("aria-hidden", "true");

    for (const [cls, stroke, dash] of [
      ["gauge-track", null, null],
      ["gauge-fill", color, String(circumference)],
    ]) {
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("class", cls);
      circle.setAttribute("cx", "54");
      circle.setAttribute("cy", "54");
      circle.setAttribute("r", String(radius));
      circle.setAttribute("fill", "none");
      circle.setAttribute("stroke-width", "7");
      if (stroke) circle.setAttribute("stroke", stroke);
      if (dash) {
        circle.setAttribute("stroke-dasharray", dash);
        circle.setAttribute("stroke-dashoffset", dash);
      }
      svg.append(circle);
    }

    const fill = svg.querySelector(".gauge-fill");
    requestAnimationFrame(() => fill.setAttribute("stroke-dashoffset", String(offset)));

    return el("div", { class: "gauge" }, [
      svg,
      el("div", { class: "gauge-num", text: String(Math.round(score)) }),
    ]);
  }

  function render(report) {
    const style = VERDICT_STYLE[report.verdict] || VERDICT_STYLE.mixed;
    const applicable = report.signals.filter((s) => s.applicable);
    const skipped = report.signals.filter((s) => !s.applicable);
    const ranked = [...applicable].sort((a, b) => b.points_lost - a.points_lost);

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
          text: `${Math.round(report.confidence * 100)}% confidence · ${report.word_count.toLocaleString()} words`,
        }),
      ]),
    ]);

    const metaBits = [];
    if (report.domain) {
      metaBits.push(el("span", {}, [el("b", { text: "Source: " }), report.domain.domain]));
      metaBits.push(el("span", {}, [el("b", { text: "Publisher: " }), report.domain.label]));
    }
    metaBits.push(
      el("span", {}, [el("b", { text: "Signals run: " }), `${applicable.length} of ${report.signals.length}`])
    );
    const meta = el("div", { class: "meta-row" }, metaBits);

    const notes = report.notes && report.notes.length
      ? el("div", { class: "notes" }, report.notes.map((note) => el("p", { text: note })))
      : null;

    const signalNodes = ranked.map((signal) => {
      const width = Math.max(2, Math.round(signal.severity * 100));
      const barColor =
        signal.severity >= 0.6 ? "var(--bad)" : signal.severity >= 0.3 ? "var(--warn)" : "var(--good)";
      return el("div", { class: "signal" }, [
        el("div", { class: "signal-top" }, [
          el("span", { class: "signal-name", text: signal.label }),
          el("span", {
            class: `signal-cost${signal.points_lost >= 25 ? " is-costly" : ""}`,
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

    document.getElementById("result").append(
      el("div", { class: "score-card" }, [header, meta, notes, signalsBlock])
    );
  }

  (async function boot() {
    const slug = location.pathname.split("/").filter(Boolean).pop();
    const meta = document.getElementById("shared-meta");
    try {
      const response = await fetch(`/api/shared/${encodeURIComponent(slug)}`);
      if (!response.ok) throw new Error("not found");
      const payload = await response.json();
      meta.textContent = `Viewed ${payload.views} time${payload.views === 1 ? "" : "s"}. This is a snapshot taken when the report was created.`;
      render(payload.report);
    } catch {
      meta.textContent = "";
      document.getElementById("result").append(
        el("p", { class: "empty", text: "That report doesn't exist, or the link has been revoked." })
      );
    }
  })();
})();
