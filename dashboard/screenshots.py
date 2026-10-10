"""Capture each dashboard page to docs/images/dashboard_*.png with Playwright."""
from pathlib import Path
from playwright.sync_api import sync_playwright

d = Path(__file__).parent
out = d.parent / "docs" / "images"
names = ["dashboard_1_executive_summary", "dashboard_2_why_the_gap_exists",
         "dashboard_3_concentration", "dashboard_4_documentation_opportunity"]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1340, "height": 760}, device_scale_factor=1.5)
    for i, name in enumerate(names):
        page.goto(f"{(d / 'index.html').as_uri()}#{i}")
        page.reload()
        page.screenshot(path=str(out / f"{name}.png"), full_page=True)
    browser.close()
