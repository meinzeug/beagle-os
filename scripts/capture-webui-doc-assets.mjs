import { mkdirSync } from 'node:fs';
import { writeFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { resolve } from 'node:path';
import { chromium } from '../website/node_modules/playwright/index.mjs';

const BASE_URL = process.env.BEAGLE_WEBUI_BASE_URL || 'https://srv1.beagle-os.com';
const OUTPUT_DIR = resolve(process.cwd(), process.env.BEAGLE_DOCS_WEBUI_DIR || 'public-site/assets/img/docs/webui');
const VIEWPORT = { width: 1600, height: 1200 };
const ADMIN_USER = process.env.BEAGLE_DOCS_ADMIN_USER || 'docs-admin';

function ensureDir(path) {
  mkdirSync(path, { recursive: true });
}

function fileName(name) {
  return resolve(OUTPUT_DIR, name);
}

function randomPassword() {
  return randomBytes(12).toString('base64url');
}

async function waitVisible(page, selector, timeout = 30000) {
  await page.locator(selector).waitFor({ state: 'visible', timeout });
}

async function screenshotElement(page, selector, name) {
  await page.locator(selector).screenshot({ path: fileName(name) });
}

async function setPanel(page, panelId) {
  await page.evaluate((next) => {
    window.location.hash = 'panel=' + encodeURIComponent(next);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }, panelId);
}

async function selectedVmidFromHash(page) {
  return page.evaluate(() => {
    const hash = String(window.location.hash || '');
    const match = /(?:^|[&#?])vmid=([0-9]+)/.exec(hash);
    return match ? Number(match[1]) : 0;
  });
}

async function loginWithUi(page, username, password) {
  await page.fill('#auth-username', username);
  await page.fill('#auth-password', password);
  await page.click('#connect-button');
  await page.waitForFunction(() => !document.body.classList.contains('auth-only'), null, { timeout: 45000 });
}

async function completeOnboarding(page, username, password) {
  const onboardingVisible = await page.locator('#onboarding-modal').isVisible({ timeout: 6000 }).catch(() => false);
  if (!onboardingVisible) {
    await waitVisible(page, '#auth-modal');
    await screenshotElement(page, '#auth-modal', 'onboarding.png');
    return;
  }
  await screenshotElement(page, '#onboarding-modal', 'onboarding.png');
  await page.fill('#onboarding-username', username);
  await page.fill('#onboarding-password', password);
  await page.fill('#onboarding-password-confirm', password);
  await page.click('#onboarding-complete');
  await waitVisible(page, '#auth-modal');
}

async function captureProvisioningForm(page) {
  await setPanel(page, 'provisioning');
  await page.waitForTimeout(1200);
  await page.waitForFunction(() => {
    const node = document.getElementById('prov-node');
    if (!node || !node.options || node.options.length === 0) {
      return false;
    }
    return Array.from(node.options).some((option) => String(option.value || '').trim().length > 0);
  }, null, { timeout: 45000 });
  await page.evaluate(() => {
    const node = document.getElementById('prov-node');
    if (!node) {
      return;
    }
    const firstRealOption = Array.from(node.options || []).find((option) => String(option.value || '').trim().length > 0);
    if (firstRealOption) {
      node.value = firstRealOption.value;
      node.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  await page.evaluate(() => {
    const bridge = document.getElementById('prov-bridge');
    if (!bridge) {
      return;
    }
    const firstRealOption = Array.from(bridge.options || []).find((option) => String(option.value || '').trim().length > 0);
    if (firstRealOption) {
      bridge.value = firstRealOption.value;
      bridge.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  const vmName = 'docs-thinclient-' + String(Date.now()).slice(-6);
  await page.fill('#prov-name', vmName);
  await page.fill('#prov-guest-password', String(process.env.BEAGLE_DOCS_ADMIN_PASS || 'BeagleDocs-2026!Run1'));
  await screenshotElement(page, '#provisioning-section', 'provisioning-form.png');
}

async function captureProvisioningCreateResult(page) {
  const createResponsePromise = page.waitForResponse((response) => {
    return response.url().includes('/api/v1/provisioning/vms') && response.request().method() === 'POST';
  }, { timeout: 180000 }).catch(() => null);
  await page.click('#provision-create');
  await page.waitForTimeout(2200);
  let vmid = 0;
  const createResponse = await createResponsePromise;
  if (createResponse) {
    try {
      const payload = await createResponse.json();
      vmid = Number((payload && payload.provisioned_vm && payload.provisioned_vm.vmid) || payload.vmid || 0);
    } catch (error) {
      void error;
    }
  }
  const progressVisible = await page.locator('#provision-progress-modal').isVisible().catch(() => false);
  if (progressVisible) {
    await screenshotElement(page, '#provision-progress-modal', 'provisioning-create-result.png');
  } else {
    await screenshotElement(page, '#provisioning-section', 'provisioning-create-result.png');
  }
  return vmid;
}

async function openVmUsbTab(page) {
  await setPanel(page, 'inventory');
  await page.waitForSelector('#inventory-body [data-vmid]', { timeout: 60000 });
  await page.locator('#inventory-body [data-vmid]').first().click();
  await page.waitForFunction(() => {
    const detail = document.getElementById('vm-detail-page');
    return Boolean(detail) && !detail.hasAttribute('hidden') && Boolean(document.getElementById('detail-title') && document.getElementById('detail-title').textContent.trim());
  }, null, { timeout: 60000 });
  await page.click('[data-detail-panel="usb"]');
  await page.waitForTimeout(1200);
  await screenshotElement(page, '#vm-detail-page', 'vm-usb-tab.png');
}

async function deleteVm(page, vmid) {
  if (!vmid) {
    return;
  }
  try {
    await setPanel(page, 'inventory');
    await page.waitForSelector('#inventory-body [data-vmid="' + String(vmid) + '"]', { timeout: 60000 });
    await page.click('#inventory-body [data-vmid="' + String(vmid) + '"]');
    await page.waitForFunction((selectedVmid) => {
      const detail = document.getElementById('vm-detail-page');
      return Boolean(detail) && !detail.hasAttribute('hidden') && String(window.location.hash || '').includes('vmid=' + String(selectedVmid));
    }, vmid, { timeout: 60000 });
    const deleteVisible = await page.locator('#vm-delete').isVisible().catch(() => false);
    if (!deleteVisible) {
      return;
    }
    await page.click('#vm-delete');
    await waitVisible(page, '#confirm-modal');
    await page.click('#confirm-accept');
    await page.waitForFunction((nextVmid) => {
      const selected = String(window.location.hash || '');
      const row = document.querySelector('#inventory-body [data-vmid="' + String(nextVmid) + '"]');
      return !row && selected.indexOf('vmid=' + String(nextVmid)) === -1;
    }, vmid, { timeout: 120000 });
  } catch (error) {
    void error;
  }
}

async function captureSecurity(page) {
  await setPanel(page, 'settings_security');
  await page.waitForTimeout(1000);
  await screenshotElement(page, '#settings-security-section', 'settings-security.png');
}

async function captureOverview(page) {
  await setPanel(page, 'overview');
  await page.waitForTimeout(1000);
  await screenshotElement(page, '#overview-section', 'dashboard-overview.png');
}

async function main() {
  ensureDir(OUTPUT_DIR);

  const adminPassword = process.env.BEAGLE_DOCS_ADMIN_PASS || randomPassword();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    ignoreHTTPSErrors: true
  });

  await context.addInitScript(() => {
    try {
      localStorage.setItem('beagle.darkMode', '1');
    } catch (error) {
      void error;
    }
  });

  const page = await context.newPage();
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 45000 });

  await completeOnboarding(page, ADMIN_USER, adminPassword);
  await loginWithUi(page, ADMIN_USER, adminPassword);

  await captureOverview(page);
  await captureSecurity(page);
  await captureProvisioningForm(page);
  const createdVmid = await captureProvisioningCreateResult(page);
  await openVmUsbTab(page);
  await deleteVm(page, createdVmid);

  const manifest = {
    base_url: BASE_URL,
    admin_user: ADMIN_USER,
    screenshots: [
      'onboarding.png',
      'dashboard-overview.png',
      'settings-security.png',
      'provisioning-form.png',
      'provisioning-create-result.png',
      'vm-usb-tab.png'
    ]
  };
  writeFileSync(fileName('manifest.json'), JSON.stringify(manifest, null, 2) + '\n', 'utf8');

  await context.close();
  await browser.close();
  process.stdout.write('Generated WebUI doc assets in ' + OUTPUT_DIR + '\n');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
