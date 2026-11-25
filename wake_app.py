from playwright.sync_api import sync_playwright

APP_URL = "https://growth-audit-engine.streamlit.app/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(APP_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)

    wake_btn = page.get_by_text("Yes, get this app back up!")
    if wake_btn.count() > 0:
        wake_btn.first.click()
        page.wait_for_timeout(30000)

    browser.close()
