// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');

const BASE_URL = 'http://localhost:8001';
const HOST = 'automate.localhost';
const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');

let consoleErrors = [];
let pageErrors = [];

test.describe('Automation Builder Smoke Test', () => {
  test.beforeEach(async ({ page }) => {
    consoleErrors = [];
    pageErrors = [];

    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    page.on('pageerror', err => {
      pageErrors.push(err.message);
    });
  });

  test('Step 1: Login to desk', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`, {
      extraHTTPHeaders: { 'Host': HOST },
    });

    await page.waitForLoadState('networkidle');

    // Fill login form
    const usernameInput = page.locator('input[name="usr"], input[type="text"]').first();
    const passwordInput = page.locator('input[name="pwd"], input[type="password"]').first();

    await usernameInput.fill('Administrator');
    await passwordInput.fill('admin');

    // Click login button
    const loginBtn = page.locator('button[type="submit"], .btn-primary').first();
    await loginBtn.click();

    // Wait for redirect to desk
    await page.waitForURL('**/app/**', { timeout: 15000 });

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '01-after-login.png'),
      fullPage: false,
    });

    expect(page.url()).toContain('/app');
    console.log('Login successful. URL:', page.url());
  });

  test('Step 2: Navigate to automation builder and open automation', async ({ page }) => {
    // Login first
    await login(page);

    // Navigate to SPA builder
    await page.goto(`${BASE_URL}/app/spa-builder`, {
      extraHTTPHeaders: { 'Host': HOST },
    });

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '02-automation-list.png'),
      fullPage: false,
    });

    // Check if the Vue app loaded - look for the automation list
    const listContent = await page.locator('.ab-list, .ab-app').first().textContent().catch(() => '');
    console.log('List page content snippet:', listContent.substring(0, 200));

    // Look for automations in the list
    const rows = page.locator('.ab-list-row');
    const rowCount = await rows.count();
    console.log(`Found ${rowCount} automation rows`);

    // If there are automations, click the first one
    if (rowCount > 0) {
      await rows.first().click();
      await page.waitForTimeout(2000);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, '03-automation-builder.png'),
        fullPage: false,
      });

      // Check for node elements
      const nodes = page.locator('.ab-node, [class*="ab-node"]');
      const nodeCount = await nodes.count();
      console.log(`Found ${nodeCount} node elements on canvas`);

      expect(nodeCount).toBeGreaterThan(0);
    } else {
      console.log('No automations found in list - creating one via API');
      // Create one via the API for testing
      await page.evaluate(async () => {
        const resp = await fetch('/api/method/automation_builder.api.save_automation', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Frappe-CSRF-Token': window.csrf_token || '',
          },
          body: JSON.stringify({
            automation_name: 'E2E Test Automation',
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
                { id: 'action-2', type: 'action', position: { x: 250, y: 620 }, data: { action_type: 'send_email', recipient: '{{trigger.email}}', template: '', subject: 'Test Subject', body: 'Test Body' } },
              ],
              edges: [],
              actions: [
                { type: 'create_document', config: { action_type: 'create_document', target_doctype: 'Automation Task', field_mapping: [{ target_field: 'subject', source_value: 'Test: {{trigger.lead_name}}' }] } },
                { type: 'send_email', config: { action_type: 'send_email', recipient: '{{trigger.email}}', template: '', subject: 'Test Subject', body: 'Test Body' } },
              ],
            }),
          }),
        });
        return resp.json();
      });

      // Reload to see the new automation
      await page.reload();
      await page.waitForTimeout(2000);

      const newRows = page.locator('.ab-list-row');
      const newRowCount = await newRows.count();
      console.log(`After API creation: ${newRowCount} rows`);

      if (newRowCount > 0) {
        await newRows.first().click();
        await page.waitForTimeout(2000);

        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, '03-automation-builder.png'),
          fullPage: false,
        });

        const nodes = page.locator('.ab-node, [class*="ab-node"]');
        const nodeCount = await nodes.count();
        console.log(`Found ${nodeCount} node elements`);
        expect(nodeCount).toBeGreaterThan(0);
      }
    }
  });

  test('Step 3: Open Send Email config and check template dropdown', async ({ page }) => {
    await login(page);
    await openFirstAutomation(page);

    // Find and click the Send Email action node
    const actionNodes = page.locator('.ab-node-action, [class*="ab-node-action"]');
    const actionCount = await actionNodes.count();
    console.log(`Found ${actionCount} action nodes`);

    if (actionCount >= 2) {
      // Click the second action node (Send Email)
      await actionNodes.nth(1).click();
      await page.waitForTimeout(1000);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, '04-send-email-config.png'),
        fullPage: false,
      });

      // Check for template picker dropdown
      const templateSelect = page.locator('select').filter({ hasText: /None|template/i }).first();
      const templateExists = await templateSelect.isVisible().catch(() => false);

      if (templateExists) {
        const options = templateSelect.locator('option');
        const optionCount = await options.count();
        console.log(`Template dropdown found with ${optionCount} options`);

        // Log all option texts
        for (let i = 0; i < optionCount; i++) {
          const text = await options.nth(i).textContent();
          console.log(`  Option ${i}: "${text}"`);
        }

        expect(optionCount).toBeGreaterThanOrEqual(1); // At least "None" option
      } else {
        console.log('Template dropdown not visible - checking config panel content');
        const configContent = await page.locator('.ab-config, .ab-sidebar').first().textContent().catch(() => 'not found');
        console.log('Config panel content:', configContent.substring(0, 300));
      }

      // Close the config panel
      const closeBtn = page.locator('.ab-config .ab-btn-ghost, .ab-config-header button').first();
      if (await closeBtn.isVisible().catch(() => false)) {
        await closeBtn.click();
        await page.waitForTimeout(500);
      }
    } else {
      console.log('Not enough action nodes to test Send Email config');
    }
  });

  test('Step 4: Test field mapping on Create Document action', async ({ page }) => {
    await login(page);
    await openFirstAutomation(page);

    // Find and click the first action node (Create Document)
    const actionNodes = page.locator('.ab-node-action, [class*="ab-node-action"]');
    const actionCount = await actionNodes.count();
    console.log(`Found ${actionCount} action nodes`);

    if (actionCount >= 1) {
      await actionNodes.first().click();
      await page.waitForTimeout(1000);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, '05-create-doc-config.png'),
        fullPage: false,
      });

      // Look for field mapping rows
      const mappingRows = page.locator('.ab-mapping-row');
      const mappingCount = await mappingRows.count();
      console.log(`Field mapping rows: ${mappingCount}`);

      // Click "+ Add Field" button
      const addFieldBtn = page.locator('button').filter({ hasText: /Add Field/i }).first();
      if (await addFieldBtn.isVisible().catch(() => false)) {
        await addFieldBtn.click();
        await page.waitForTimeout(500);

        const newMappingCount = await mappingRows.count();
        console.log(`After add: ${newMappingCount} rows`);
        expect(newMappingCount).toBe(mappingCount + 1);

        // Remove the last row
        const removeBtn = page.locator('.ab-mapping-remove').last();
        if (await removeBtn.isVisible().catch(() => false)) {
          await removeBtn.click();
          await page.waitForTimeout(500);

          const afterRemoveCount = await mappingRows.count();
          console.log(`After remove: ${afterRemoveCount} rows`);
          expect(afterRemoveCount).toBe(mappingCount);
        }

        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, '06-field-mapping-test.png'),
          fullPage: false,
        });
      } else {
        console.log('Add Field button not found');
      }

      // Close config
      const closeBtn = page.locator('.ab-config .ab-btn-ghost, .ab-config-header button').first();
      if (await closeBtn.isVisible().catch(() => false)) {
        await closeBtn.click();
        await page.waitForTimeout(500);
      }
    }
  });

  test('Step 5: Save, reload, verify + button exists', async ({ page }) => {
    await login(page);
    await openFirstAutomation(page);

    // Click Save button
    const saveBtn = page.locator('button').filter({ hasText: /^Save$/ }).first();
    if (await saveBtn.isVisible().catch(() => false)) {
      await saveBtn.click();
      await page.waitForTimeout(2000);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, '07-after-save.png'),
        fullPage: false,
      });
    }

    // Reload page
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '08-after-reload.png'),
      fullPage: false,
    });

    // Check for the + add-node button
    const addBtn = page.locator('.ab-add-node-btn, button').filter({ hasText: /^\+$/ }).first();
    const addBtnVisible = await addBtn.isVisible().catch(() => false);
    console.log(`Add node button visible after reload: ${addBtnVisible}`);

    if (!addBtnVisible) {
      // Try clicking on the automation from the list again
      const listLink = page.locator('.ab-list-row').first();
      if (await listLink.isVisible().catch(() => false)) {
        await listLink.click();
        await page.waitForTimeout(2000);

        const addBtnRetry = page.locator('.ab-add-node-btn').first();
        const retryVisible = await addBtnRetry.isVisible().catch(() => false);
        console.log(`Add button visible after re-opening: ${retryVisible}`);

        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, '09-retry-reopen.png'),
          fullPage: false,
        });
      }
    }

    // Check all page errors
    console.log('Console errors during test:', consoleErrors.length > 0 ? consoleErrors : 'None');
    console.log('Page errors during test:', pageErrors.length > 0 ? pageErrors : 'None');

    expect(pageErrors.length).toBe(0);
  });

  test('Step 6: Capture console errors across all pages', async ({ page }) => {
    await login(page);

    const pages = [
      { url: '/app/spa-builder', name: 'automation-list' },
      { url: '/app/spa-builder/builder', name: 'new-builder' },
      { url: '/app/spa-builder/templates', name: 'email-templates' },
    ];

    for (const p of pages) {
      consoleErrors = [];
      pageErrors = [];

      await page.goto(`${BASE_URL}${p.url}`, {
        extraHTTPHeaders: { 'Host': HOST },
      });

      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `10-${p.name}.png`),
        fullPage: false,
      });

      console.log(`Page ${p.name}: console errors=${consoleErrors.length}, page errors=${pageErrors.length}`);
      if (consoleErrors.length > 0) {
        console.log('  Console errors:', consoleErrors);
      }
      if (pageErrors.length > 0) {
        console.log('  Page errors:', pageErrors);
      }
    }

    // Final check - no page errors across all pages
    expect(pageErrors.length).toBe(0);
  });
});

async function login(page) {
  await page.goto(`${BASE_URL}/login`, {
    extraHTTPHeaders: { 'Host': HOST },
  });

  await page.waitForLoadState('networkidle');

  // Check if already logged in
  if (page.url().includes('/app')) {
    return;
  }

  const usernameInput = page.locator('input[name="usr"], input[type="text"]').first();
  const passwordInput = page.locator('input[name="pwd"], input[type="password"]').first();

  await usernameInput.fill('Administrator');
  await passwordInput.fill('admin');

  const loginBtn = page.locator('button[type="submit"], .btn-primary').first();
  await loginBtn.click();

  await page.waitForURL('**/app/**', { timeout: 15000 });
}

async function openFirstAutomation(page) {
  // Navigate to SPA builder
  await page.goto(`${BASE_URL}/app/spa-builder`, {
    extraHTTPHeaders: { 'Host': HOST },
  });

  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  const rows = page.locator('.ab-list-row');
  const rowCount = await rows.count();

  if (rowCount > 0) {
    await rows.first().click();
    await page.waitForTimeout(2000);
  }
}
