from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8070"
DB = "soloodoo_uat_ui"
OUT = Path("reports/test-artifacts")

modules = [
    "EL MOKRIF CRM",
    "EL MOKRIF Calendar Bridge",
    "EL MOKRIF Sale Chantier",
    "EL MOKRIF Stock Controls",
    "EL MOKRIF Documents Bridge",
    "EL MOKRIF Finance Readiness",
    "EL MOKRIF Finance Operations",
    "EL MOKRIF Management Dashboard",
    "EL MOKRIF HR Extension",
    "EL MOKRIF Tendering & BOQ",
    "EL MOKRIF Construction Control",
    "EL MOKRIF Integration Tests",
    "EL MOKRIF Browser Acceptance Tests",
]

def login(page):
    page.goto(f"{BASE}/web/login?db={DB}", wait_until="domcontentloaded")
    page.locator("input[name=login]").fill("uat.admin@example.test")
    page.locator("input[name=password]").fill("UatAdminPassword!2026")
    page.get_by_role("button", name="Log in", exact=True).click(no_wait_after=True)
    page.locator(".o_navbar_apps_menu").wait_for(timeout=90000)

def open_apps(page):
    page.locator(".o_navbar_apps_menu").click()
    icon = page.locator(".o_app[data-menu-xmlid='base.menu_management']")
    icon.wait_for()
    icon.click(no_wait_after=True)
    page.get_by_placeholder("Search...").wait_for()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(90000)
    login(page)
    open_apps(page)
    # Remove the default Apps facet so technical test modules are discoverable too.
    apps_facet = page.locator(".o_facet_values", has_text="Apps")
    if apps_facet.count():
        facet = apps_facet.first.locator("xpath=ancestor::*[contains(@class,'o_searchview_facet')]")
        close = facet.locator(".o_facet_remove")
        if close.count():
            close.click()
    for name in modules:
        search = page.get_by_placeholder("Search...")
        search.fill(name)
        search.press("Enter")
        page.wait_for_timeout(1200)
        card = page.locator(".o_kanban_record", has_text=name).first
        if not card.count():
            print("NOT_FOUND", name, flush=True)
            search.fill("")
            continue
        body = card.inner_text()
        if "Installed" in body or "Uninstall" in body or "Upgrade" in body:
            print("ALREADY", name, flush=True)
        else:
            activate = card.get_by_role("button", name="Activate", exact=True)
            if not activate.count():
                activate = card.get_by_text("Activate", exact=True)
            print("INSTALL", name, flush=True)
            activate.click(no_wait_after=True)
            page.locator(".o_web_client").wait_for(timeout=180000)
            page.wait_for_timeout(2500)
            # Re-open Apps after each installation redirect.
            open_apps(page)
            apps_facet = page.locator(".o_facet_values", has_text="Apps")
            if apps_facet.count():
                facet = apps_facet.first.locator("xpath=ancestor::*[contains(@class,'o_searchview_facet')]")
                close = facet.locator(".o_facet_remove")
                if close.count(): close.click()
        search = page.get_by_placeholder("Search...")
        search.fill("")
        page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "uat00-all-custom-modules-installed.png"), full_page=True)
    browser.close()
