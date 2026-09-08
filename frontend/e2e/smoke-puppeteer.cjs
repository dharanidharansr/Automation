/**
 * Automation Builder - Headless Browser Smoke Test (Puppeteer)
 *
 * Run: node e2e/smoke-puppeteer.cjs
 * Requires: bench running on http://localhost:8001 with Host: automate.localhost
 */
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:8001';
const HOST = 'automate.localhost';
const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');

// Ensure screenshots directory exists
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const consoleErrors = [];
const pageErrors = [];

let passed = 0;
let failed = 0;

function ok(name) {
  passed++;
  console.log(`  ✓ ${name}`);
}

function fail(name, reason) {
  failed++;
  console.log(`  ✗ ${name}: ${reason}`);
}

async function screenshot(page, name) {
  const filePath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: false });
  console.log(`    [screenshot: ${name}.png]`);
}

async function login(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle2' });
  await page.waitForSelector('input[name="usr"], input[type="text"]', { timeout: 10000 });

  // Fill and submit login form
  await page.type('input[name="usr"]', 'Administrator');
  await page.type('input[name="pwd"]', 'admin');
  await page.click('button[type="submit"]');

  // Wait for redirect to desk
  await page.waitForFunction(
    () => window.location.href.includes('/app'),
    { timeout: 15000 }
  );
}

async function main() {
  console.log('=== Automation Builder Headless Browser Smoke Test ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });

  // Set Host header for all requests
  await page.setExtraHTTPHeaders({ 'Host': HOST });

  // Capture console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('pageerror', err => {
    pageErrors.push(err.message);
  });

  try {
    // ===== STEP 1: Login =====
    console.log('Step 1: Login to desk');
    await login(page);
    await screenshot(page, '01-after-login');

    if (page.url().includes('/app')) {
      ok('Login successful');
    } else {
      fail('Login', `URL is ${page.url()}`);
    }

    // ===== STEP 2: Navigate to automation builder =====
    console.log('\nStep 2: Navigate to automation builder');
    await page.goto(`${BASE_URL}/app/spa-builder`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 3000)); // Wait for Vue app to load

    await screenshot(page, '02-automation-list');

    // Check if the Vue app loaded
    const listRows = await page.$$('.ab-list-row');
    console.log(`    Found ${listRows.length} automation row(s)`);

    if (listRows.length > 0) {
      ok('Automation list loaded with rows');
    } else {
      console.log('    No automations found - creating one via API...');
      // Create via API
      await page.evaluate(async () => {
        const resp = await fetch('/api/method/automation_builder.api.save_automation', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Frappe-CSRF-Token': window.csrf_token || '',
          },
          body: JSON.stringify({
            automation_name: 'E2E Test Auto',
            trigger_doctype: 'Lead',
            trigger_event: 'On Update',
            condition_field: 'status',
            condition_operator: '=',
            condition_value: 'Qualified',
            enabled: 1,
            workflow_json: JSON.stringify({
              nodes: [
                { id: 'trigger', type: 'trigger', position: { x: 250, y: 50 }, data: { trigger_doctype: 'Lead', trigger_event: 'On Update' } },
                { id: 'condition', type: 'condition', position: { x: 250, y: 250 }, data: { condition_field: 'status', condition_operator: '=', condition_value: 'Qualified' } },
                { id: 'action-1', type: 'action', position: { x: 250, y: 450 }, data: { action_type: 'create_document', target_doctype: 'Automation Task', field_mapping: [{ target_field: 'subject', source_value: 'Test: {{trigger.lead_name}}' }] } },
                { id: 'action-2', type: 'action', position: { x: 250, y: 620 }, data: { action_type: 'send_email', recipient: '{{trigger.email}}', template: '', subject: 'Test Email', body: 'Hello {{trigger.lead_name}}' } },
              ],
              edges: [],
              actions: [
                { type: 'create_document', config: { action_type: 'create_document', target_doctype: 'Automation Task', field_mapping: [{ target_field: 'subject', source_value: 'Test: {{trigger.lead_name}}' }] } },
                { type: 'send_email', config: { action_type: 'send_email', recipient: '{{trigger.email}}', template: '', subject: 'Test Email', body: 'Hello {{trigger.lead_name}}' } },
              ],
            }),
          }),
        });
        return resp.json();
      });
      console.log('    Created automation via API');

      // Reload list
      await page.goto(`${BASE_URL}/app/spa-builder`, { waitUntil: 'networkidle2' });
      await new Promise(r => setTimeout(r, 2000));

      const newRows = await page.$$('.ab-list-row');
      console.log(`    After creation: ${newRows.length} row(s)`);
      if (newRows.length > 0) ok('Automation created and visible');
      else fail('Automation creation', 'No rows after API creation');
    }

    // ===== STEP 3: Open first automation =====
    console.log('\nStep 3: Open automation in builder');
    const firstRow = (await page.$$('.ab-list-row'))[0];
    if (firstRow) {
      await firstRow.click();
      await new Promise(r => setTimeout(r, 3000));

      await screenshot(page, '03-builder-loaded');

      // Check for node elements
      const nodes = await page.$$('.vue-flow__node');
      const nodeCount = nodes.length;
      console.log(`    Found ${nodeCount} Vue Flow node(s)`);

      if (nodeCount >= 4) {
        ok('Builder loaded with nodes (trigger + condition + 2 actions)');
      } else {
        fail('Builder nodes', `Expected >= 4, got ${nodeCount}`);
      }
    }

    // ===== STEP 4: Open Send Email config - check template dropdown =====
    console.log('\nStep 4: Open Send Email action config');

    // Click the second action node (Send Email)
    const actionNodes = await page.$$('.vue-flow__node-action');
    console.log(`    Found ${actionNodes.length} action node(s)`);

    if (actionNodes.length >= 2) {
      await actionNodes[1].click();
      await new Promise(r => setTimeout(r, 2000));

      await screenshot(page, '04-send-email-config');

      // Check for template picker dropdown
      const selects = await page.$$('.ab-config select');
      let templateDropdown = null;

      for (const sel of selects) {
        const text = await sel.evaluate(el => el.textContent);
        if (text.includes('None') && text.includes('template')) {
          templateDropdown = sel;
          break;
        }
      }

      if (templateDropdown) {
        const options = await templateDropdown.$$('option');
        console.log(`    Template dropdown found with ${options.length} option(s)`);

        for (const opt of options) {
          const text = await opt.evaluate(el => el.textContent.trim());
          console.log(`      - "${text}"`);
        }

        if (options.length >= 1) {
          ok('Template dropdown populated');
        } else {
          fail('Template dropdown', 'No options');
        }
      } else {
        console.log('    Template dropdown not found by text match, checking all selects');
        for (const sel of selects) {
          const text = await sel.evaluate(el => el.textContent);
          console.log(`      select: "${text.substring(0, 80)}..."`);
        }
        fail('Template dropdown', 'Not found');
      }

      // Close config panel
      const closeBtn = await page.$('.ab-config-header button');
      if (closeBtn) await closeBtn.click();
      await new Promise(r => setTimeout(r, 500));
    }

    // ===== STEP 5: Test field mapping on Create Document =====
    console.log('\nStep 5: Test field mapping on Create Document action');

    if (actionNodes.length >= 1) {
      await actionNodes[0].click();
      await new Promise(r => setTimeout(r, 2000));

      await screenshot(page, '05-create-doc-config');

      // Count existing mapping rows
      const mappingRows = await page.$$('.ab-mapping-row');
      const initialCount = mappingRows.length;
      console.log(`    Initial mapping rows: ${initialCount}`);

      // Click "+ Add Field"
      const addFieldBtn = await page.evaluateHandle(() => {
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
          if (btn.textContent.includes('Add Field')) return btn;
        }
        return null;
      });

      if (addFieldBtn && addFieldBtn.asElement()) {
        await addFieldBtn.asElement().click();
        await new Promise(r => setTimeout(r, 500));

        const afterAddRows = await page.$$('.ab-mapping-row');
        console.log(`    After add: ${afterAddRows.length} rows`);

        if (afterAddRows.length === initialCount + 1) {
          ok('Add field mapping row');
        } else {
          fail('Add field mapping', `Expected ${initialCount + 1}, got ${afterAddRows.length}`);
        }

        // Click remove on last row
        const removeBtns = await page.$$('.ab-mapping-remove');
        if (removeBtns.length > 0) {
          await removeBtns[removeBtns.length - 1].click();
          await new Promise(r => setTimeout(r, 500));

          const afterRemoveRows = await page.$$('.ab-mapping-row');
          console.log(`    After remove: ${afterRemoveRows.length} rows`);

          if (afterRemoveRows.length === initialCount) {
            ok('Remove field mapping row');
          } else {
            fail('Remove field mapping', `Expected ${initialCount}, got ${afterRemoveRows.length}`);
          }
        }
      } else {
        fail('Add Field button', 'Not found');
      }

      await screenshot(page, '06-field-mapping-test');

      // Close config
      const closeBtn = await page.$('.ab-config-header button');
      if (closeBtn) await closeBtn.click();
      await new Promise(r => setTimeout(r, 500));
    }

    // ===== STEP 6: Save, reload, verify + button =====
    console.log('\nStep 6: Save, reload, verify + button');

    // Click Save
    const saveBtn = await page.evaluateHandle(() => {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent.trim() === 'Save') return btn;
      }
      return null;
    });

    if (saveBtn && saveBtn.asElement()) {
      await saveBtn.asElement().click();
      await new Promise(r => setTimeout(r, 2000));
      await screenshot(page, '07-after-save');
      ok('Save clicked');
    }

    // Reload
    await page.reload({ waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 3000));

    await screenshot(page, '08-after-reload');

    // Check for + button
    const addBtn = await page.$('.ab-add-node-btn');
    if (addBtn) {
      const isVisible = await addBtn.evaluate(el => {
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden';
      });

      if (isVisible) {
        ok('+ add-node button visible after reload');
      } else {
        fail('+ button', 'Exists but not visible');
      }
    } else {
      // Try re-opening from list
      console.log('    + button not found, trying to re-open from list...');
      const listRows = await page.$$('.ab-list-row');
      if (listRows.length > 0) {
        await listRows[0].click();
        await new Promise(r => setTimeout(r, 3000));

        const retryAddBtn = await page.$('.ab-add-node-btn');
        if (retryAddBtn) {
          ok('+ add-node button visible after re-opening');
        } else {
          fail('+ button', 'Not found even after re-opening');
        }
        await screenshot(page, '09-retry-reopen');
      }
    }

    // ===== STEP 7: Check console errors =====
    console.log('\nStep 7: Console error summary');
    console.log(`    Console errors: ${consoleErrors.length}`);
    for (const err of consoleErrors) {
      console.log(`      - ${err.substring(0, 150)}`);
    }
    console.log(`    Page errors: ${pageErrors.length}`);
    for (const err of pageErrors) {
      console.log(`      - ${err.substring(0, 150)}`);
    }

    if (pageErrors.length === 0) {
      ok('No page errors during entire test');
    } else {
      fail('Page errors', `${pageErrors.length} error(s) detected`);
    }

    // ===== STEP 8: Check all pages for errors =====
    console.log('\nStep 8: Check all pages for console errors');
    const testPages = [
      { url: '/app/spa-builder', name: 'list' },
      { url: '/app/spa-builder/builder', name: 'new-builder' },
      { url: '/app/spa-builder/templates', name: 'templates' },
    ];

    for (const p of testPages) {
      consoleErrors.length = 0;
      pageErrors.length = 0;

      await page.goto(`${BASE_URL}${p.url}`, { waitUntil: 'networkidle2' });
      await new Promise(r => setTimeout(r, 2000));

      await screenshot(page, `10-page-${p.name}`);

      console.log(`    ${p.name}: console=${consoleErrors.length} page=${pageErrors.length}`);
    }

  } catch (err) {
    console.error('\nFATAL ERROR:', err.message);
    await screenshot(page, '99-error').catch(() => {});
  } finally {
    await browser.close();
  }

  // Summary
  console.log('\n=== SUMMARY ===');
  console.log(`  Passed: ${passed}`);
  console.log(`  Failed: ${failed}`);

  if (failed > 0) {
    process.exit(1);
  }
}

main().catch(err => {
  console.error('Unhandled error:', err);
  process.exit(1);
});
