"""Needs: python -m grassy.server on PORT=8010 and `python -m http.server 8765 -d web`."""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); page=b.new_page(viewport={"width":390,"height":844})
    errs=[]; page.on("pageerror",lambda e:errs.append(str(e)))
    page.goto("http://localhost:8765/")
    page.click("text=Try with an example group"); page.wait_for_selector("text=Work it out")
    page.click('[data-tab="settings"]'); page.fill("#smart","http://localhost:8010"); page.click('[data-action="saveSmart"]')
    page.click('[data-tab="plan"]'); page.click("text=Work it out"); page.wait_for_selector(".res")
    print(page.inner_text(".result").split("Method")[1][:80])
    assert "Smart mode used" in page.inner_text("body"), page.inner_text("body")[-400:]
    page.wait_for_selector('[data-action="polish"]'); page.click('[data-action="polish"]'); page.wait_for_timeout(500)
    # unreachable server falls back
    page.click('[data-tab="settings"]'); page.fill("#smart","http://localhost:9"); page.click('[data-action="saveSmart"]')
    page.click('[data-tab="plan"]'); page.click("text=Work it out"); page.wait_for_selector(".res")
    page.wait_for_selector("text=unreachable", timeout=12000)
    assert not errs, errs
    print("smart mode OK + fallback OK")
