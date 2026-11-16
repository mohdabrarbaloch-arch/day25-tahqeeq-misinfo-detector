# Usage

How to actually use Tahqeeq, and how to read what it tells you.

---

## The two ways in

### Paste text

Best for WhatsApp forwards, social posts, and anything behind a paywall. Paste
it, optionally give it a headline, and hit **Check it**.

Minimum 20 characters. Maximum 60,000 — roughly a long magazine feature.

### From a link

Give it a URL and it fetches the page, strips the navigation and scripts, pulls
out the article body, and scores that.

This works on ordinary server-rendered news sites. It does **not** work on:

- paywalled articles (you get the teaser, not the body)
- JavaScript-rendered sites (the HTML arrives empty)
- PDFs, videos, or anything that isn't HTML

When it fails it tells you which of those it thinks happened. Paste the text
instead.

---

## Reading the report

### The score

0 to 100, where higher means *fewer warning signs in the writing*. It is not a
truth score and the app never claims it is.

| Band | Verdict | What it means |
|---|---|---|
| 85–100 | Credible | Reads like standard reporting |
| 65–84 | Mostly credible | Sound overall, some weak spots |
| 45–64 | Mixed | Check the primary source yourself |
| 25–44 | Questionable | Several strong warning signs |
| 0–24 | Unreliable | Reads like misinformation |

### Confidence

Separate from the score, and worth understanding. Confidence reflects **how much
text the engine had to work with**, not how sure it is about the truth.

A 30-word snippet can't be assessed for attribution or structure, so those
signals are skipped and confidence drops. A 600-word article gets everything
assessed and confidence is high. If confidence is low, treat the score as
provisional — the report says so explicitly.

### The signals

Each signal shows four things:

- **What it looked for** — the label and a plain-English explanation
- **How bad it was** — the bar, from 0 to 100% severity
- **What it cost** — points deducted, so you can see which finding actually
  moved the number
- **The evidence** — the exact phrases that triggered it

Signals are sorted worst-first, because the top one or two are usually the whole
story.

Signals marked **not assessed** were excluded from scoring entirely. They're
shown rather than hidden so you can see what wasn't checked.

---

## Worked examples

### A WhatsApp forward

> SHOCKING!!! They don't want you to know the REAL truth... SHARE THIS BEFORE
> THEY DELETE IT!!! Forward to everyone you know.

**Score: 23.7 — unreliable.**

The three signals that did the damage:

- **Share pressure** (severity 1.0, −100 pts) — evidence: `SHARE THIS BEFORE THEY DELETE IT`
- **Conspiracy framing** (severity 0.8) — evidence: `they don't want you to know`, `do your own research`
- **Sensational language** (severity 0.7) — 4 alarm words, 6.2% of words capitalised, 5 exclamation marks

Note what the report does *not* say: it never claims the underlying event didn't
happen. It says the writing has the shape of a forward, which is a claim it can
actually support.

### A wire-style report

> Pakistan's central bank held its policy rate at 11 percent on Monday...
> "We expect inflation to remain within the target range," Governor Jameel Ahmad
> told reporters in Karachi.

**Score: 95.0 — credible.**

Named sources, specific figures, a date, a link, hedged language where hedging
is appropriate. Nothing to penalise.

### The interesting middle

> A new study has found a strong link between air quality and childhood asthma...
> The findings were described as important by people familiar with the work.

**Score: 51.6 — mixed.**

This is the case worth studying. It *reads* like a news story — proper
paragraphs, measured tone, no capitals. But: no named source, no link, no date,
and "people familiar with the work" is anonymous sourcing dressed up as
attribution. It lands in the middle, which is exactly right. It might be
perfectly true; the writing just doesn't let you check.

---

## Sharing a report

Hit **Copy share link** on any report. You get a public, read-only URL at
`/r/<slug>` that anyone can open without an account.

The shared copy is a **snapshot**, not a live view. Deleting your analysis also
deletes the public link, because the share row cascades with it.

---

## History

Every analysis is stored with its full report, so the evidence you saw is the
evidence you'll see later — even if the engine's weights change in a future
version. The stats row shows your totals, average score, activity over the last
seven days, and how many came back unreliable.

---

## What it can't do

Worth being blunt about, because a tool like this is easy to over-trust:

- **It reads style, not facts.** A well-written lie with named sources and
  specific figures will score well. That's the ceiling of this approach.
- **English only.** The lexicons are English. Urdu and Roman-Urdu forwards — a
  large share of the real problem in Pakistan — aren't handled yet.
- **It can be gamed.** Anyone who reads the signal list can write around it.
  That's true of every style-based detector.
- **A high score is not an endorsement.** It means nothing suspicious was found
  in the writing. Check the primary source.
