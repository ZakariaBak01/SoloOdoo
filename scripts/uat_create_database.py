from pathlib import Path

from playwright.sync_api import sync_playwright


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto("http://localhost:8070/web/database/manager", wait_until="domcontentloaded")
    form = page.locator("form").first
    form.locator("input[name='master_pwd']").fill("uat-master-password")
    form.locator("input[name='name']").fill("soloodoo_uat_ui")
    form.locator("input[name='login']").fill("uat.admin@example.test")
    form.locator("input[name='password']").fill("UatAdminPassword!2026")
    form.locator("input[name='phone']").fill("0600000000")
    form.locator("input[name='demo']").uncheck()
    form.locator("input[type='submit']").click()
    page.wait_for_timeout(12000)
    Path("reports/test-artifacts").mkdir(parents=True, exist_ok=True)
    page.screenshot(path="reports/test-artifacts/uat-database-created.png", full_page=True)
    print(page.url)
    print(page.locator("body").inner_text()[:1500])
    browser.close()
