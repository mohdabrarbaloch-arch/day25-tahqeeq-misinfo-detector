"""Capture real screenshots of the running app.

Run the server first, then:

    python scripts/capture_screenshots.py http://127.0.0.1:8111

Writes PNGs into screenshots/. These are genuine captures of the live app, not
mockups — the README links to them and they should always be regenerated from a
running instance rather than hand-edited.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "screenshots"

MISLEADING = (
    "SHOCKING!!! They don't want you to know the REAL truth about what happened "
    "in Karachi last night!!!\n\n"
    "A friend of a senior official has revealed that a MASSIVE cover-up is "
    "underway. Sources say that thousands of people were affected but the "
    "mainstream media won't report it. This is UNDENIABLE proof that the deep "
    "state is hiding everything from you.\n\n"
    "Experts say this is the biggest scandal in the country's history and nobody "
    "is talking about it. The government has completely destroyed the evidence. "
    "It is being reported that the real number is in the millions.\n\n"
    "SHARE THIS BEFORE THEY DELETE IT!!! Forward to everyone you know. Do your "
    "own research. Wake up before it's too late!"
)

CLEAN = (
    "Pakistan's central bank held its policy rate at 11 percent on Monday, citing "
    "easing inflation.\n\n"
    "The State Bank of Pakistan said in a statement that inflation had slowed to "
    '4.9 percent in October from 6.2 percent a month earlier. "We expect '
    'inflation to remain within the target range over the coming quarters," '
    "Governor Jameel Ahmad told reporters in Karachi.\n\n"
    "According to the bank's monetary policy report published on 10 November "
    "2026, food prices rose 3.1 percent while core inflation held at 7.4 percent. "
    "Analysts at Topline Securities said the decision was widely expected.\n\n"
    "The next policy meeting is scheduled for 15 December 2026."
)


def main(base_url: str) -> int:
    OUT.mkdir(exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        # 1. Landing / sign-in
        page.goto(base_url, wait_until="networkidle")
        page.screenshot(path=OUT / "01-signin.png", full_page=True)
        print("01-signin.png")

        # 2. Sign in with the demo account
        page.click("#demo-login")
        page.wait_for_selector("#view-check:not([hidden])", timeout=10_000)
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "02-check-empty.png", full_page=True)
        print("02-check-empty.png")

        # 3. A misleading forward, scored
        page.fill("#headline", "SHOCKING: They don't want you to know the REAL truth")
        page.fill("#text", MISLEADING)
        page.click("#submit-analyze")
        page.wait_for_selector(".score-card", timeout=15_000)
        page.wait_for_timeout(1200)  # let the gauge animate to its final value
        page.screenshot(path=OUT / "03-unreliable-report.png", full_page=True)
        print("03-unreliable-report.png")

        # 4. A clean report, for contrast
        page.click("text=Check something else")
        page.wait_for_timeout(300)
        page.fill("#headline", "State Bank holds policy rate at 11 percent")
        page.fill("#text", CLEAN)
        page.click("#submit-analyze")
        page.wait_for_selector(".score-card", timeout=15_000)
        page.wait_for_timeout(1200)
        page.screenshot(path=OUT / "04-credible-report.png", full_page=True)
        print("04-credible-report.png")

        # 5. History with the stats row
        page.click("[data-view=history]")
        page.wait_for_selector(".history-item", timeout=10_000)
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "05-history.png", full_page=True)
        print("05-history.png")

        # 6. Mobile, on the report view
        page.click("[data-view=check]")
        page.wait_for_timeout(300)
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        mobile.goto(base_url, wait_until="networkidle")
        mobile.click("#demo-login")
        mobile.wait_for_selector("#view-check:not([hidden])", timeout=10_000)
        mobile.fill("#text", MISLEADING)
        mobile.click("#submit-analyze")
        mobile.wait_for_selector(".score-card", timeout=15_000)
        mobile.wait_for_timeout(1200)
        mobile.screenshot(path=OUT / "06-mobile-report.png", full_page=True)
        print("06-mobile-report.png")

        browser.close()

    print(f"\nwrote {len(list(OUT.glob('*.png')))} screenshots to {OUT}")
    return 0


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8111"
    sys.exit(main(url))
