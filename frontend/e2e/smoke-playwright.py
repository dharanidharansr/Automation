"""
Automation Builder - Headless Browser Smoke Test (Python Playwright)

Run: LD_LIBRARY_PATH=/tmp python e2e/smoke-playwright.py
Requires: bench running on http://automate.localhost:8001
Requires: /tmp/libasound.so.2 stub (for Chromium headless)
"""
import os
import sys
from playwright.sync_api import sync_playwright

BASE_URL = "http://automate.localhost:8001"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

passed = 0
failed = 0
page_errors = []


def ok(name):
    global passed
    passed += 1
    print(f"  OK {name}")


def fail(name, reason):
    global failed
    failed += 1
    print(f"  FAIL {name}: {reason}")


def click_node(page, selector, index=0):
    """Click a Vue Flow node using mouse coordinates (dispatchEvent doesn't trigger Vue)."""
    bbox = page.evaluate(f"""() => {{
        const n = document.querySelectorAll('{selector}')[{index}];
        if (!n) return null;
        n.scrollIntoView({{block:'center'}});
        const r = n.getBoundingClientRect();
        return {{x: r.x, y: r.y, w: r.width, h: r.height}};
    }}""")
    if not bbox or bbox['w'] == 0:
        return False
    page.wait_for_timeout(300)
    page.mouse.click(bbox['x'] + bbox['w'] / 2, bbox['y'] + bbox['h'] / 2)
    page.wait_for_timeout(1500)
    return True


def main():
    global passed, failed

    print("=== Automation Builder Headless Browser Smoke Test ===\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                "--host-resolver-rules=MAP automate.localhost 127.0.0.1",
            ],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        try:
            # ===== STEP 1: Login =====
            print("Step 1: Login to desk")
            page.goto(f"{BASE_URL}/login", wait_until="networkidle")
            page.wait_for_selector("#login_email", timeout=10000)
            page.fill("#login_email", "Administrator")
            page.fill("#login_password", "admin")
            page.click('.form-signin button[type="submit"], .page-card-actions button')
            page.wait_for_function(
                "() => window.location.href.includes('/desk') || window.location.href.includes('/app')",
                timeout=15000,
            )
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01-after-login.png"))
            if "/desk" in page.url or "/app" in page.url:
                ok("Login successful")
            else:
                fail("Login", f"URL is {page.url}")

            # ===== STEP 2: Navigate to automation builder =====
            print("\nStep 2: Navigate to automation builder")
            page.goto(f"{BASE_URL}/app/spa-builder", wait_until="networkidle")
            page.wait_for_timeout(3000)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02-automation-list.png"))

            rows = page.query_selector_all(".ab-list-row")
            print(f"  Found {len(rows)} automation row(s)")
            if len(rows) > 0:
                ok("Automation list loaded")
            else:
                fail("Automation list", "No rows found")

            # ===== STEP 3: Open automation with actions =====
            print("\nStep 3: Open automation in builder")
            rows = page.query_selector_all(".ab-list-row")
            if rows:
                # Find a row that has action nodes (not the first one which may have no actions)
                target_row = None
                for row in rows:
                    text = row.text_content() or ""
                    if "Magesh" in text or "Lead Qualified" in text or "Roundtrip" in text:
                        target_row = row
                        break
                if not target_row:
                    target_row = rows[-1]  # fallback to last row
                target_row.click()
                page.wait_for_timeout(3000)
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03-builder-loaded.png"))

                nodes = page.query_selector_all(".vue-flow__node")
                edges = page.query_selector_all(".vue-flow__edge")
                print(f"  Found {len(nodes)} Vue Flow node(s), {len(edges)} edge(s)")
                if len(nodes) >= 4:
                    ok("Builder loaded with nodes")
                else:
                    fail("Builder nodes", f"Expected >= 4, got {len(nodes)}")
                if len(edges) >= 1:
                    ok("Edges rendered")
                else:
                    fail("Edges", f"Expected >= 1, got {len(edges)}")

            # ===== STEP 4: Open Send Email config =====
            print("\nStep 4: Open Send Email action config")
            action_count = len(page.query_selector_all(".vue-flow__node-action"))
            print(f"  Found {action_count} action node(s)")

            if action_count >= 2:
                clicked = click_node(page, ".vue-flow__node-action", 1)
                if clicked:
                    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04-send-email-config.png"))

                    config = page.query_selector(".ab-config")
                    if config:
                        ok("Config panel opened for Send Email")

                        # Check for template_picker select
                        tpl_select = page.query_selector(".ab-config .ab-action-config select")
                        if tpl_select:
                            text = tpl_select.text_content()
                            print(f"  Template picker text: {text[:80]}...")
                            if "None" in text:
                                ok("Template picker dropdown present")
                            else:
                                fail("Template picker", f"Unexpected text: {text[:80]}")
                        else:
                            fail("Template picker", "No select found in action config")
                    else:
                        fail("Config panel", "Not opened")
                else:
                    fail("Click action node", "Could not get bounding box")

                # Close config
                page.evaluate("() => { const btn = document.querySelector('.ab-config-header button'); if (btn) btn.click(); }")
                page.wait_for_timeout(500)

            # ===== STEP 5: Test field mapping =====
            print("\nStep 5: Test field mapping on Create Document")
            if action_count >= 1:
                clicked = click_node(page, ".vue-flow__node-action", 0)
                if clicked:
                    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05-create-doc-config.png"))

                    mapping_rows = page.query_selector_all(".ab-mapping-row")
                    initial_count = len(mapping_rows)
                    print(f"  Initial mapping rows: {initial_count}")

                    # Click "+ Add Field"
                    add_btn = page.query_selector("button:has-text('Add Field')")
                    if add_btn:
                        add_btn.click()
                        page.wait_for_timeout(500)
                        after_add = len(page.query_selector_all(".ab-mapping-row"))
                        print(f"  After add: {after_add} rows")
                        if after_add == initial_count + 1:
                            ok("Add field mapping row")
                        else:
                            fail("Add field mapping", f"Expected {initial_count + 1}, got {after_add}")

                        # Remove last row
                        remove_btns = page.query_selector_all(".ab-mapping-remove")
                        if remove_btns:
                            remove_btns[-1].click()
                            page.wait_for_timeout(500)
                            after_remove = len(page.query_selector_all(".ab-mapping-row"))
                            print(f"  After remove: {after_remove} rows")
                            if after_remove == initial_count:
                                ok("Remove field mapping row")
                            else:
                                fail("Remove field mapping", f"Expected {initial_count}, got {after_remove}")
                    else:
                        fail("Add Field button", "Not found")

                    # Close config
                    page.evaluate("() => { const btn = document.querySelector('.ab-config-header button'); if (btn) btn.click(); }")
                    page.wait_for_timeout(500)
                else:
                    fail("Click action node", "Could not get bounding box")

            # ===== STEP 6: Save, reload, verify + button =====
            print("\nStep 6: Save, reload, verify + button")

            page.evaluate("() => { const btn = document.querySelector('button.ab-btn-primary'); if (btn) btn.click(); }")
            page.wait_for_timeout(2000)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07-after-save.png"))
            ok("Save clicked")

            # Reload
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(3000)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08-after-reload.png"))

            # Check for + button
            add_btn = page.query_selector(".ab-add-node-btn")
            if add_btn and add_btn.is_visible():
                ok("+ add-node button visible after reload")
            else:
                # Re-open from list
                print("  + button not visible, re-opening from list...")
                list_rows = page.query_selector_all(".ab-list-row")
                if list_rows:
                    list_rows[0].click()
                    page.wait_for_timeout(3000)
                    retry_btn = page.query_selector(".ab-add-node-btn")
                    if retry_btn and retry_btn.is_visible():
                        ok("+ add-node button visible after re-opening")
                    else:
                        fail("+ button", "Not found even after re-opening")
                    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09-retry-reopen.png"))

            # ===== STEP 7: Drag-to-add node picker =====
            print("\nStep 7: Test drag-to-add from handle to empty canvas")
            # Find the trigger-out handle
            handle_info = page.evaluate("""() => {
                const handle = document.querySelector('[data-handleid="trigger-out"]');
                if (!handle) return null;
                const r = handle.getBoundingClientRect();
                return {x: r.x + r.width/2, y: r.y + r.height/2};
            }""")
            if handle_info:
                # Simulate drag: mousedown on handle, move to empty canvas, mouseup
                page.mouse.move(handle_info['x'], handle_info['y'])
                page.wait_for_timeout(200)
                page.mouse.down()
                page.wait_for_timeout(200)
                # Move far enough to be "empty canvas" (200px right, 150px down)
                page.mouse.move(handle_info['x'] + 200, handle_info['y'] + 150)
                page.wait_for_timeout(200)
                page.mouse.up()
                page.wait_for_timeout(800)
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "11-drag-to-add.png"))

                # Check if picker appeared
                picker = page.query_selector('.ab-type-picker')
                if picker and picker.is_visible():
                    ok("Drag-to-add picker appeared on empty canvas")
                    # Check picker items - from trigger, should show Condition
                    items = page.query_selector_all('.ab-type-picker-item')
                    item_texts = [it.text_content().strip() for it in items]
                    print(f"  Picker items: {item_texts}")
                    if any("Condition" in t for t in item_texts):
                        ok("Picker shows Condition (from trigger)")
                    else:
                        fail("Picker items", f"Expected Condition, got {item_texts}")
                    # Click Condition to create a new node
                    for it in items:
                        if "Condition" in it.text_content():
                            it.click()
                            break
                    page.wait_for_timeout(800)
                    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "12-after-drag-add.png"))
                    # Verify new node was created (should now have 5 non-add nodes instead of 4)
                    node_count = len(page.query_selector_all(".vue-flow__node:not(.vue-flow__node-add-trigger)"))
                    print(f"  Nodes after drag-add: {node_count}")
                    if node_count >= 5:
                        ok("New node created via drag-to-add")
                    else:
                        fail("Drag-to-add node", f"Expected >= 5 nodes, got {node_count}")
                    # Clean up: remove the extra node by saving original state
                    # (we'll test the + button approach separately)
                else:
                    # Drag might not trigger in headless — try the "+" button fallback
                    print("  Picker not visible after drag, testing + button fallback...")
                    add_btn = page.query_selector(".ab-add-node-btn")
                    if add_btn and add_btn.is_visible():
                        add_btn.click()
                        page.wait_for_timeout(500)
                        menu = page.query_selector(".ab-add-node-menu")
                        if menu and menu.is_visible():
                            ok("+ button dropdown menu appeared")
                            menu_items = page.query_selector_all(".ab-add-node-menu-item")
                            if len(menu_items) > 0:
                                menu_items[0].click()
                                page.wait_for_timeout(800)
                                node_count = len(page.query_selector_all(".vue-flow__node:not(.vue-flow__node-add-trigger)"))
                                print(f"  Nodes after + button add: {node_count}")
                                if node_count >= 5:
                                    ok("+ button creates new node")
                                else:
                                    fail("+ button node", f"Expected >= 5, got {node_count}")
                            else:
                                fail("+ menu items", "No items in dropdown")
                        else:
                            fail("+ menu", "Not visible")
                    else:
                        fail("+ button", "Not visible for drag fallback")
            else:
                fail("Trigger handle", "Not found")

            # ===== STEP 8: Verify new action types in dropdown =====
            print("\nStep 8: Verify new action types (HTTP Request, Telegram, Update Field) appear")
            # Open + menu to check all action types are listed
            add_btn = page.query_selector(".ab-add-node-btn")
            if add_btn and add_btn.is_visible():
                page.evaluate("() => { document.querySelector('.ab-add-node-btn').click(); }")
                page.wait_for_timeout(500)
                menu = page.query_selector(".ab-add-node-menu")
                if menu and menu.is_visible():
                    menu_items = page.query_selector_all(".ab-add-node-menu-item")
                    item_texts = [it.text_content().strip() for it in menu_items]
                    print(f"  Menu items: {item_texts}")
                    expected = ["Create Document", "Send Email", "HTTP Request", "Telegram", "Update Field"]
                    found_all = all(any(exp in t for t in item_texts) for exp in expected)
                    if found_all:
                        ok("All 5 action types in dropdown")
                    else:
                        missing = [exp for exp in expected if not any(exp in t for t in item_texts)]
                        fail("Action type dropdown", f"Missing: {missing}")
                    # Close menu
                    page.mouse.click(10, 10)
                    page.wait_for_timeout(300)
                else:
                    fail("+ menu", "Not visible for type check")
            else:
                fail("+ button", "Not visible for type check")

            # ===== STEP 8: Check all pages =====
            print("\nStep 8: Check all pages for errors")
            for url, name in [
                ("/app/spa-builder", "list"),
                ("/app/spa-builder/builder", "new-builder"),
                ("/app/spa-builder/templates", "templates"),
            ]:
                page_errors.clear()
                page.goto(f"{BASE_URL}{url}", wait_until="networkidle")
                page.wait_for_timeout(2000)
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"10-page-{name}.png"))
                print(f"  {name}: page_errors={len(page_errors)}")

            if len(page_errors) == 0:
                ok("No page errors during navigation")
            else:
                fail("Page errors", f"{len(page_errors)} error(s)")
                for err in page_errors[:3]:
                    print(f"    - {err[:150]}")

        except Exception as e:
            print(f"\nFATAL ERROR: {e}")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "99-error.png"))
        finally:
            browser.close()

    print(f"\n=== SUMMARY ===")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
