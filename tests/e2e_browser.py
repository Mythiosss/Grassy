"""Drives the real PWA in headless Chromium: python tests/e2e_browser.py [base_url]"""
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, service_workers="allow")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(BASE)
    page.wait_for_selector("text=Try with an example group")
    page.click("text=Try with an example group")
    page.wait_for_selector("text=Work it out")
    page.click("text=Work it out")
    page.wait_for_selector(".results .res")
    assert page.locator(".res").count() == 3, "expected 3 candidate dates"
    body = page.inner_text("body")
    for bad in ("undefined", "NaN", "[object"):
        assert bad not in body, bad
    assert "Plan supplies for" in body or "Siapkan" in body or "Prepara" in body or "Andaa" in body
    wa = page.get_attribute('[data-action="wa"]', "href")
    assert wa.startswith("https://wa.me/?text="), wa
    if SHOTS: page.screenshot(path=f"{SHOTS}/plan.png", full_page=True)
    # persistence across reload
    page.reload()
    page.wait_for_selector("text=Work it out")
    # history tab: add + remove an event
    page.click('[data-tab="history"]')
    n0 = page.locator(".hist li").count()
    page.fill("#ed", "2026-10-04"); page.fill("#ea", "21"); page.click('[data-action="addEvent"]')
    assert page.locator(".hist li").count() == n0 + 1
    page.click('.hist li >> nth=0 >> .x')
    assert page.locator(".hist li").count() == n0
    if SHOTS: page.screenshot(path=f"{SHOTS}/history.png")
    # language switch
    page.click('[data-tab="settings"]')
    page.select_option("#lang", "id")
    page.wait_for_selector("text=Pengaturan")
    # offline: service worker caches the shell
    page.wait_for_function("navigator.serviceWorker.controller !== null || true")
    page.evaluate("navigator.serviceWorker.ready")
    page.reload(); page.wait_for_timeout(500)
    ctx.set_offline(True)
    page.reload()
    page.wait_for_selector("text=Pengaturan", timeout=5000)
    print("offline reload OK")
    assert not errors, errors
    b.close()
print("browser e2e OK")
