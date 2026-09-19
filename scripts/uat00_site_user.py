from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8070"
DB = "soloodoo_uat_ui"
EVIDENCE = Path("reports/test-artifacts")
EVIDENCE.mkdir(parents=True, exist_ok=True)


def login(page, username, password):
    page.goto(f"{BASE}/web/login?db={DB}", wait_until="domcontentloaded")
    page.locator("input[name=login]").fill(username)
    page.locator("input[name=password]").fill(password)
    page.locator("button[type=submit]").click(no_wait_after=True)
    page.locator(".o_navbar_apps_menu").wait_for(timeout=60000)


def open_users(page):
    page.locator(".o_navbar_apps_menu").click()
    page.get_by_text("Settings", exact=True).click(no_wait_after=True)
    page.get_by_text("Manage Users", exact=True).wait_for(timeout=60000)
    page.get_by_text("Manage Users", exact=True).click(no_wait_after=True)
    page.get_by_text("UAT Site User", exact=True).wait_for(timeout=60000)
    page.get_by_text("UAT Site User", exact=True).click(no_wait_after=True)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    admin = browser.new_page(viewport={"width": 1440, "height": 1000})
    admin.set_default_timeout(60000)
    login(admin, "uat.admin@example.test", "UatAdminPassword!2026")
    open_users(admin)
    admin.locator(".o_field_widget[name=sel_groups_54_56]:visible").click()
    admin.locator("button.o_form_button_save:visible").wait_for()

    desired = {
        "sel_groups_60_61_62": "false",  # Sales
        "sel_groups_31_32": "31",        # Project User
        "sel_groups_23_25": "false",     # Invoicing
        "sel_groups_41_42": "false",     # Inventory
        "sel_groups_63_64": "false",     # Purchase
        "sel_groups_30": "false",        # Bank validation
        "sel_groups_2_4": "false",       # Administration
        "sel_groups_38": "false",        # Dashboard
        "sel_groups_54_56": "54",        # Chantier User
        "sel_groups_70": "false",        # Chantier Buyer
        "sel_groups_71": "false",        # Purchase Approver
        "sel_groups_72": "false",        # Quality Inspector
    }
    observed = []
    for widget in admin.locator("[name^=sel_groups]:visible").all():
        select = widget.locator("select:visible")
        if not select.count():
            continue
        name = widget.get_attribute("name")
        if name in desired:
            select.select_option(desired[name])
        observed.append((name, widget.inner_text(), select.input_value()))
    admin.locator("button.o_form_button_save:visible").click(no_wait_after=True)
    admin.wait_for_timeout(1500)
    admin.screenshot(path=str(EVIDENCE / "uat00-site-user-corrected.png"), full_page=True)
    print("ADMIN_ACCESS", observed, flush=True)

    site = browser.new_page(viewport={"width": 1440, "height": 1000})
    site.set_default_timeout(60000)
    login(site, "uat.site@example.test", "UatSitePassword!2026")
    site.locator(".o_navbar_apps_menu").click()
    menus = site.locator("body").inner_text()
    print("SITE_MENUS", menus[:1200], flush=True)
    site.screenshot(path=str(EVIDENCE / "uat00-site-user-menus-retest.png"), full_page=True)
    assert "Project" in menus and "EL MOKRIF" in menus
    assert "Settings" not in menus
    assert "Purchase" not in menus
    assert "Inventory" not in menus
    assert "Dashboards" not in menus
    site.locator(".o_navbar_apps_menu").click()
    direct_url = f"{BASE}/web#action=69&model=res.users&view_type=list&cids=1&menu_id=1"
    site.goto(direct_url, wait_until="commit")
    site.wait_for_timeout(4000)
    direct_text = site.locator("body").inner_text()
    print("DIRECT_USERS", direct_text[:800], flush=True)
    site.screenshot(path=str(EVIDENCE / "uat00-site-user-direct-users-denied.png"), full_page=True)
    assert "Users & Companies" not in direct_text

    mobile = browser.new_page(viewport={"width": 390, "height": 844})
    mobile.set_default_timeout(60000)
    login(mobile, "uat.site@example.test", "UatSitePassword!2026")
    mobile.screenshot(path=str(EVIDENCE / "uat00-site-user-mobile.png"), full_page=True)
    print("MOBILE_OK", mobile.url, flush=True)
    browser.close()
