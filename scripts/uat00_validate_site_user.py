from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8070"
DB = "soloodoo_uat_ui"
OUT = Path("reports/test-artifacts")


def login(page):
    page.goto(f"{BASE}/web/login?db={DB}", wait_until="domcontentloaded")
    page.locator("input[name=login]").fill("uat.site@example.test")
    page.locator("input[name=password]").fill("UatSitePassword!2026")
    page.get_by_role("button", name="Log in", exact=True).click(no_wait_after=True)
    page.locator(".o_navbar_apps_menu").wait_for(timeout=60000)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(60000)
    login(page)
    page.locator(".o_navbar_apps_menu").click()
    page.get_by_text("EL MOKRIF", exact=True).wait_for(timeout=60000)
    app_text = page.locator("body").inner_text()
    print("APPS", app_text[:1000], flush=True)
    assert "Project" in app_text
    assert "EL MOKRIF" in app_text
    assert "Settings" not in app_text
    assert "Purchase" not in app_text
    assert "Inventory" not in app_text
    assert "Dashboards" not in app_text
    assert "Apps" not in app_text
    page.screenshot(path=str(OUT / "uat00-site-user-apps-pass.png"), full_page=True)

    page.get_by_text("EL MOKRIF", exact=True).click(no_wait_after=True)
    page.get_by_text("Material Requests", exact=True).wait_for()
    menu_text = page.locator("body").inner_text()
    print("CHANTIER_MENU", menu_text[:1000], flush=True)
    assert "Chantiers" in menu_text
    assert "Material Requests" in menu_text
    assert "Construction Estimates" in menu_text
    assert "Daily Site Reports" in menu_text
    assert "New Chantier" not in menu_text
    page.screenshot(path=str(OUT / "uat00-site-user-elmokrif-menu-pass.png"), full_page=True)

    page.goto(f"{BASE}/web#action=69&model=res.users&view_type=list&cids=1&menu_id=1", wait_until="commit")
    page.wait_for_timeout(4000)
    denied = page.locator("body").inner_text()
    print("DIRECT_USERS", denied[:700].encode("ascii", "replace").decode(), flush=True)
    exposed_users = "UAT Site User" in denied or "Users & Companies" in denied
    print("DIRECT_USERS_EXPOSED", exposed_users, flush=True)
    page.screenshot(path=str(OUT / "uat00-site-user-direct-users-access.png"), full_page=True)

    mobile = browser.new_page(viewport={"width": 390, "height": 844})
    mobile.set_default_timeout(60000)
    login(mobile)
    mobile.screenshot(path=str(OUT / "uat00-site-user-mobile-pass.png"), full_page=True)
    print("MOBILE", mobile.url, flush=True)
    browser.close()
