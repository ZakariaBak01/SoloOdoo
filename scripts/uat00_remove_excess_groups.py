from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8070"
DB = "soloodoo_uat_ui"
OUT = Path("reports/test-artifacts")

targets = [
    ("Inventory / Administrator", "Administrator"),
    ("Inventory / User", "User"),
    ("Purchase / Administrator", "Administrator"),
    ("Purchase / User", "User"),
    ("Extra Rights / Technical Features", "Technical Features"),
    ("Technical / Access to export feature", "Access to export feature"),
    ("Technical / Mail Template Editor", "Mail Template Editor"),
    (
        "Technical / Send an automatic reminder email to confirm delivery",
        "Send an automatic reminder email to confirm delivery",
    ),
]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(60000)
    page.goto(f"{BASE}/web/login?db={DB}&debug=1", wait_until="domcontentloaded")
    page.locator("input[name=login]").fill("uat.admin@example.test")
    page.locator("input[name=password]").fill("UatAdminPassword!2026")
    page.get_by_role("button", name="Log in", exact=True).click(no_wait_after=True)
    page.locator(".o_navbar_apps_menu").wait_for()
    page.locator(".o_navbar_apps_menu").click()
    page.get_by_text("Settings", exact=True).click(no_wait_after=True)
    page.get_by_text("Users & Companies", exact=True).wait_for()

    removed = []
    for display_name, query in targets:
        page.get_by_text("Users & Companies", exact=True).click()
        page.get_by_role("menuitem", name="Groups", exact=True).click(no_wait_after=True)
        search = page.get_by_placeholder("Search...")
        search.wait_for()
        search.fill(query)
        search.press("Enter")
        target = page.get_by_text(display_name, exact=True)
        target.wait_for()
        target.click(no_wait_after=True)
        page.get_by_text("Add a line", exact=True).wait_for()
        user = page.get_by_text("UAT Site User", exact=True)
        print("CHECK", display_name, user.count(), flush=True)
        if user.count():
            row = user.locator("xpath=ancestor::tr")
            delete = row.locator("button[name=delete]")
            if delete.count():
                delete.click()
                save = page.locator(".o_form_button_save:visible")
                if save.count():
                    save.click()
                    page.wait_for_timeout(500)
                removed.append(display_name)
    page.screenshot(path=str(OUT / "uat00-excess-groups-removed.png"), full_page=True)
    print("REMOVED", removed, flush=True)
    browser.close()
