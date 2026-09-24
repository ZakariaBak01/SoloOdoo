const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const base = 'http://localhost:8069';
const db = 'test';
const out = path.resolve('reports/client-demo-screenshots');
fs.mkdirSync(out, { recursive: true });

const screens = [
  ['00-management-dashboard', 'elmokrif.dashboard', 1, 630],
  ['01-chantier-master', 'project.project', 166, 555],
  ['02-approved-estimate', 'chantier.estimation', 120, 632],
  ['03-crm-opportunity', 'crm.lead', 7, 383],
  ['04-confirmed-sale', 'sale.order', 15, 619],
  ['05-material-request', 'chantier.material.request', 8, 588],
  ['06-purchase-order', 'purchase.order', 9, 572],
  ['07-contract-boq', 'construction.boq', 10, 641],
  ['08-supply-tender', 'construction.tender', 1, 642],
  ['09-work-package', 'construction.work.package', 1, 649],
  ['10-rfi', 'construction.rfi', 3, 647],
  ['11-technical-submittal', 'construction.submittal', 1, 648],
  ['12-change-event', 'construction.change.event', 1, 650],
  ['13-variation-order', 'construction.variation.order', 1, 651],
  ['14-controlled-document', 'elmokrif.document', 1, 589],
  ['15-finance-readiness', 'chantier.finance.readiness', 1, 634],
  ['16-bank-import', 'elmokrif.bank.import', 2, 635],
  ['17-hr-appraisal', 'elmokrif.hr.appraisal', 2, 558],
];

async function blurBrand(page) {
  await page.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const elements = new Set();
    while (walker.nextNode()) {
      if (/EL\s*MOKRIF/i.test(walker.currentNode.nodeValue || '')) {
        const parent = walker.currentNode.parentElement;
        if (parent) elements.add(parent);
      }
    }
    for (const element of elements) {
      element.style.setProperty('filter', 'blur(8px)', 'important');
      element.style.setProperty('display', 'inline-block', 'important');
      element.style.userSelect = 'none';
    }
    for (const element of document.querySelectorAll('input, textarea')) {
      if (/EL\s*MOKRIF/i.test(element.value || '')) {
        element.style.setProperty('filter', 'blur(8px)', 'important');
      }
    }
  });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const loginPage = await context.newPage();
  loginPage.setDefaultTimeout(30000);
  await loginPage.goto(`${base}/web/login?db=${db}`, { waitUntil: 'domcontentloaded' });
  await loginPage.locator('input[name=login]').fill('client.demo@elmokrif.local');
  await loginPage.locator('input[name=password]').fill('Demo2026!');
  await loginPage.locator('button[type=submit]').click();
  await loginPage.waitForSelector('.o_navbar');
  await loginPage.close();

  const start = Number(process.env.SCREEN_START || 0);
  const end = Number(process.env.SCREEN_END || screens.length);
  for (const [name, model, id, action] of screens.slice(start, end)) {
    const page = await context.newPage();
    page.setDefaultTimeout(30000);
    const url = `${base}/web?db=${db}#id=${id}&model=${model}&view_type=form&action=${action}`;
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.o_form_view');
    await page.waitForTimeout(1500);
    await page.keyboard.press('Escape');
    await blurBrand(page);
    await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true });
    await page.close();
  }
  await browser.close();
})();
