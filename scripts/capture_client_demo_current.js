const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const base = 'http://localhost:8069';
const db = 'test';
const out = path.resolve('reports/client-demo-screenshots');
fs.mkdirSync(out, { recursive: true });

const screens = [
  ['00-chantier-list', 'project.project', 0, 555, 'list'],
  ['01-chantier', 'project.project', 0, 555, 'list'],
  ['02-estimations', 'chantier.estimation', 0, 632, 'list'],
  ['03-crm-opportunity', 'crm.lead', 7, 383],
  ['04-confirmed-sale', 'sale.order', 15, 609],
  ['05-material-request', 'chantier.material.request', 8, 588],
  ['06-purchase-order', 'purchase.order', 9, 571],
  ['07-contract-boq', 'construction.boq', 0, 641, 'list'],
  ['08-supply-tender', 'construction.tender', 0, 642, 'list'],
  ['09-work-package', 'construction.work.package', 1, 649],
  ['10-rfi', 'construction.rfi', 3, 647],
  ['11-technical-submittal', 'construction.submittal', 1, 648],
  ['12-change-event', 'construction.change.event', 1, 650],
  ['13-variation-order', 'construction.variation.order', 1, 651],
  ['14-controlled-documents', 'elmokrif.document', 0, 589, 'list'],
  ['15-bank-import', 'elmokrif.bank.import', 2, 635],
  ['16-hr-appraisals', 'elmokrif.hr.appraisal', 0, 558, 'list'],
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
  });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const login = await context.newPage();
  login.setDefaultTimeout(30000);
  await login.goto(`${base}/web/login?db=${db}`, { waitUntil: 'domcontentloaded' });
  await login.locator('input[name=login]').fill('uat.admin');
  await login.locator('input[name=password]').fill('UAT2026!');
  await login.locator('button[type=submit]').click();
  await login.waitForSelector('.o_navbar');
  await login.close();

  const start = Number(process.env.SCREEN_START || 0);
  const end = Number(process.env.SCREEN_END || screens.length);
  for (const [name, model, id, action, viewType = 'form'] of screens.slice(start, end)) {
    const page = await context.newPage();
    page.setDefaultTimeout(30000);
    const actionParam = action ? `&action=${action}` : '';
    const idParam = id ? `id=${id}&` : '';
    const url = `${base}/web?db=${db}#${idParam}model=${model}&view_type=${viewType}${actionParam}`;
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    await page.waitForSelector('.o_web_client');
    await page.keyboard.press('Escape');
    await blurBrand(page);
    await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true });
    await page.close();
    console.log(`captured ${name}`);
  }
  await browser.close();
})();
