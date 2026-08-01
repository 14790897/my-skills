---
name: jlceda-extension-test
description: This skill should be used when testing or debugging a JLCEDA Pro extension (.eext) against a live JLCEDA project page. Covers the full workflow: (1) restarting Edge via mcp__extension-dev-mcp-tools__dev_plugin to reimport the .eext, (2) connecting to the user's already-logged-in Edge/Chrome via CDP, (3) navigating to a project tab and waiting for the sch canvas to render, (4) handling V3.2-specific dialogs ("另有一个标签页" / "导入扩展"), (5) mouse-drag selecting components on the schematic canvas, (6) clicking the extension's toolbar menu and verifying the resulting IFrame, (7) capturing screenshots + dialog text for comparison, (8) verifying settings-page toggles (e.g. saveToDisk) end-to-end, (9) running a 3-case saveToDisk regression (true / false / new-install), (10) polling the AI chat IFrame through reasoning-model timeouts (deepseek-v4-pro etc.). **MUST use mcp `dev_plugin` (NOT `import_plugin` — that one fails on V3.2 UI).** Use this skill whenever the user says "test the extension in Edge", "verify the menu triggers", "run the workflow end-to-end", "重开浏览器验证", "截图对比", "check the AI chat reply", "verify saveToDisk", or "打开 settings 测试开关". Do NOT use this skill for unit-testing the extension's source code with mocks — use the project's existing mock-test.js / ai-e2e-test.js for that.
agent_created: true
disable: false
---

# JLCEDA Extension E2E Test Workflow

Test a JLCEDA Pro extension (.eext) against the user's real, already-logged-in browser through CDP. This is the only reliable way to verify menu wiring, IFrame popups, and AI API calls — mock tests cannot cover the JLCEDA extension-host layer.

## When to use

- The user has a built `.eext` (e.g. `build/dist/local-netlist-analyzer_v1.1.0.eext`).
- The user wants to confirm the extension works in their real JLCEDA project (e.g. "测试", "在 Edge 里跑一下", "AI 回答对了没", "重开浏览器验证", "截图对比").
- The user wants to verify that clicking a specific toolbar menu item triggers the correct IFrame and that the IFrame's content matches expectation.

## When NOT to use

- Pure unit / mock testing of the extension's TypeScript → use the project's `test/mock-test.js` and `test/ai-e2e-test.js`.
- Verifying build output structure (`dist/index.js` IIFE shape) → use a `node` import check.
- The user only wants to read source code or commit changes — do not spin up a browser.
- Driving EDA APIs from a headless script (no browser UI) → use the WebSocket reverse bridge instead, see [references/ws-bridge.md](references/ws-bridge.md).

## Critical environment facts (read first)

1. **JLCEDA V3.0**: `eda.*` is injected into a hidden `blob:` frame. Walk `page.frames()` to find the frame with `window.eda && window.eda.sch_SelectControl`.
   **JLCEDA V3.2+** (V3.2.148+): `eda` lives in `window._EXTAPI_SCRIPT_SPACES_[extensionUuid].eda` (a sandbox object whose methods are on the prototype chain, not own properties). `page.frames()` walk does NOT work. Use `Object.getPrototypeOf(eda.sch_SelectControl)` to enumerate methods. See [references/v3.2-sandbox-api.md](references/v3.2-sandbox-api.md).
2. **The blob frame (V3.0) is on the same origin (`https://pro.lceda.cn`)** as the main page, so any code that touches blob iframes can also disturb sch iframes. NEVER remove/`.remove()` blob iframes that have not been opened by your extension — closing one can unload the sch API.
3. **The user's Edge runs with `--remote-debugging-port=9224` (default mcp profile) or `9269` (older mcp profile)**, already logged in. Use `chromium.connectOverCDP('http://localhost:9224')` or `9269`. Reuse, do not relaunch.
4. **mcp tools**: `mcp__extension-dev-mcp-tools__import_plugin` is **broken on V3.2** (it tries to find a `.tool-bottom-menu-more_SoDfO` locator that no longer exists in V3.2 UI, 30s timeout). **Use `mcp__extension-dev-mcp-tools__dev_plugin` instead** — it auto-starts Edge on a hashed port (9222-9321 range), imports the .eext, and listens for console errors. The user may need to re-scan QR. After `dev_plugin` returns, the Edge is on a new port — use `netstat -ano | findstr LISTENING | findstr :9` to discover it.
5. **Under `cll=debug` URL, re-importing the extension (高级 → 扩展管理器 → 导入) can break the sch API injection**. If `window.eda` (or `_EXTAPI_SCRIPT_SPACES_`) disappears after importing, ask the user to F5 the project page and wait ~15s. Reloading via `page.reload()` does NOT recover it; the user must press F5 in the browser.
6. **`playwright-core` location**: NOT in the project's `node_modules` by default. Two locations:
   - `C:/Users/13963/WorkBuddy/2026-07-12-00-12-10/extension-dev-mcp-tools/node_modules/playwright-core` (V3.0 era)
   - `C:/Users/13963/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core` (V3.2 era, bundled with `@playwright/cli`)
   Use the absolute path in every script: `require('<above path>')`.
7. **V3.2 sch canvas rendering is slow** — after dblclick on a sch tab, wait for the modal "另有一个浏览器标签页" to appear, click 是, then wait ~10s for the second canvas (the main sch drawing surface, >1000px wide) to appear. Do not assume `page.locator('canvas').nth(1)` exists immediately.

## Workflow

### Step 0 — Decide: reuse logged-in Edge, or restart?

- If the user's Edge (9224) is open with the right project already loaded AND the new `.eext` has not been imported yet, you can either:
  - (A) Import directly via Playwright clicking 高级 → 扩展管理器 → 导入 (see Step 2 V3.0 path below).
  - (B) Restart with `mcp dev_plugin` — auto-imports but forces QR re-scan. Preferred when you also want to test the import UX.
- If the user explicitly says "重开浏览器验证" / "重启 Edge", go with (B).
- Otherwise prefer (A) to avoid QR scan.

### Step 1 — Probe the browser

```js
var { chromium } = require('C:/Users/13963/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core');
var b = await chromium.connectOverCDP('http://localhost:9224');  // or 9269
// Reuse the first page; if none, open one.
var ctx = b.contexts()[0];
var p = ctx.pages()[0];
if (!p || !p.url().includes('pro.lceda.cn')) {
  p = await ctx.newPage();
  await p.goto('https://pro.lceda.cn/editor');
  await p.waitForTimeout(5000);
}
console.log('Title:', await p.title());
```

If no JLCEDA page is open, the user must navigate to a project URL ending in `#id=<uuid>,tab=*<tabid>` first. As a fallback, just `goto('https://pro.lceda.cn/editor')` and dblclick on the project in the left tree.

### Step 2 — Navigate to a sch tab (V3.2)

```js
// dblclick the sch tab in the left tree
const sch = await p.evaluate(() => {
  const all = document.querySelectorAll('li .tree-title_4dmpt, li');
  for (const el of all) {
    const t = (el.textContent || '').trim();
    if (/Schematic\d+_\d+/.test(t)) {
      const r = el.getBoundingClientRect();
      if (r.width > 0) return { x: r.x + r.width / 2, y: r.y + r.height / 2, txt: t };
    }
  }
  return null;
});
if (sch) {
  await p.mouse.dblclick(sch.x, sch.y);
  await p.waitForTimeout(2000);
  // Handle the "另有一个浏览器标签页" modal — search for [class*="modal"] containing 是
  for (let i = 0; i < 10; i++) {
    const yes = await p.evaluate(() => {
      const dlg = document.querySelector('.lc_modal_dialog, [class*="modal"]');
      if (!dlg) return null;
      const all = dlg.querySelectorAll('button, .lc_btn, [class*="btn"]');
      for (const el of all) {
        if ((el.textContent || '').trim() === '是') {
          const r = el.getBoundingClientRect();
          if (r.width > 0) return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        }
      }
      return null;
    });
    if (yes) { await p.mouse.click(yes.x, yes.y); break; }
    await p.waitForTimeout(500);
  }
  await p.waitForTimeout(8000);
}

// Wait for the main sch canvas (index 1, >1000px wide) to render
let canvasBox = null;
for (let i = 0; i < 20; i++) {
  const cs = await p.locator('canvas').count();
  if (cs >= 2) {
    const b = await p.locator('canvas').nth(1).boundingBox();
    if (b && b.width > 800) { canvasBox = b; break; }
  }
  await p.waitForTimeout(1000);
}
```

If `canvasBox` is still null after 20s, the sch worker is broken or the sch tab is not active. Dump `await p.screenshot(...)` and inspect.

### Step 2a — Find the EDA sch frame (V3.0 only — for V3.2 use the sandbox API path below)

```js
// V3.0 only: blob frame walk
var schFrame = null;
for (var f of p.frames()) {
    var has = await f.evaluate(() => !!(window.eda && window.eda.sch_SelectControl));
    if (has) { schFrame = f; break; }
}
if (!schFrame) {
    // wait up to 30s for EDA to mount (debug mode is slow)
    for (var t = 0; t < 30; t++) {
        await p.waitForTimeout(1000);
        for (var f of p.frames()) {
            var has = await f.evaluate(() => !!(window.eda && window.eda.sch_SelectControl));
            if (has) { schFrame = f; break; }
        }
        if (schFrame) break;
    }
}
```

If still not found after 30s, the EDA worker is broken — usually because the user previously closed a blob iframe. Ask them to F5.

### Step 2b — Access eda API in V3.2 sandbox (from main page)

```js
// V3.2: eda lives in _EXTAPI_SCRIPT_SPACES_[extensionUuid]
const spaceKey = await p.evaluate(() => {
  const spaces = window._EXTAPI_SCRIPT_SPACES_;
  if (!spaces) return null;
  // The uuid in extension.json — usually there's only one extension
  return Object.keys(spaces)[0];
});
const sandbox = await p.evaluate((k) => {
  const sp = window._EXTAPI_SCRIPT_SPACES_[k];
  if (!sp) return null;
  return {
    hasEda: !!sp.eda,
    sch_SelectControl_type: typeof sp.eda?.sch_SelectControl,
    protoMethods: Object.getOwnPropertyNames(Object.getPrototypeOf(sp.eda.sch_SelectControl)),
  };
}, spaceKey);
console.log('sandbox:', sandbox);
```

For full V3.2 API reference, see [references/v3.2-sandbox-api.md](references/v3.2-sandbox-api.md).

### Step 3 — Import the .eext (skip if already installed and visible in top menu)

If the toolbar menu ("局部网表" or whatever the extension's name is) is **not visible**, the extension is not active. Two options:

**Option A — Use mcp `dev_plugin` (PREFERRED for V3.2; `import_plugin` is broken)**:
```
mcp__extension-dev-mcp-tools__dev_plugin pluginPath=<abs path to .eext>
```
This auto-starts Edge on a hashed port (9222-9321) and imports the .eext.
After the tool returns, discover the new debug port:
```js
// netstat -ano | findstr LISTENING | findstr :9  →  pick the one with msedge
```
Then connect Playwright to that port and proceed. User may need to scan QR.

**Option B — Reuse logged-in Edge via Playwright** (V3.0 only):
```js
// 1. click 高级
var advanced = p.locator('span[data-test="Advanced"]');
try { await advanced.click({ timeout: 2000 }); }
catch {
    await p.locator('.tool-bottom-menu-more_SoDfO').click();
    await p.waitForTimeout(500);
    await p.locator('.tool-bottom-menu-more-container_NmJv7 span[data-test="Advanced"]')
        .evaluate(el => el.click());
}
await p.waitForTimeout(300);

// 2. open 扩展管理器
await p.getByText('扩展管理器', { exact: false }).click({ timeout: 10000 });
var modal = p.locator("[class*='lc_modal_dialog']").first();
await modal.waitFor({ state: 'visible', timeout: 10000 });

// 3. click 导入 → handle filechooser
var [chooser] = await Promise.all([
    p.waitForEvent('filechooser', { timeout: 10000 }),
    modal.locator('button', { hasText: '导入' }).click()
]);
await chooser.setFiles('<abs path to .eext>');
await p.waitForTimeout(2000);

// 4. close modal
await modal.locator("[class*='close']").first().click().catch(() => p.keyboard.press('Escape'));
```

**Caveat**: under `cll=debug`, after this import the sch API is lost. Tell the user to F5 the project page before continuing.

### Step 4 — Mouse-drag select a region

```js
// use the canvas box from Step 2 (V3.2 path) or canvasInfo[0] (V3.0)
var c = canvasBox;
var sx = c.x + c.w * 0.2, sy = c.y + c.h * 0.2;
var ex = c.x + c.w * 0.7, ey = c.y + c.h * 0.7;
await p.mouse.move(sx, sy);
await p.mouse.down();
for (var t = 0; t <= 20; t++) {
    await p.mouse.move(sx + (ex - sx) * t / 20, sy + (ey - sy) * t / 20);
    await p.waitForTimeout(20);
}
await p.mouse.up();
await p.waitForTimeout(800);

// verify selection count via EDA API
// V3.0:
var sel = await schFrame.evaluate(async () => {
    var ids = await eda.sch_SelectControl.getAllSelectedPrimitives_PrimitiveId();
    return { count: ids ? ids.length : 0 };
});
// V3.2:
var sel = await p.evaluate(async (sk) => {
  const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
  const ids = await eda.sch_SelectControl.getAllSelectedPrimitives_PrimitiveId();
  return { count: ids ? ids.length : 0 };
}, spaceKey);
```

### Step 5 — Click the extension's toolbar menu

Find the menu by its visible text. The menu's `<span>` is usually inside a wrapper that has the click handler. Prefer the parent `.top-bar-menu_JIQpX` to disambiguate from sidebar tree items with the same text:

```js
var menuPos = await p.evaluate(() => {
    // top menu only (not sidebar)
    const items = document.querySelectorAll('.top-bar-menu_JIQpX > *');
    for (const el of items) {
        const t = (el.textContent || '').trim();
        if (t === '<menu text>') {
            const r = el.getBoundingClientRect();
            if (r.width > 0) return { x: r.x + r.width/2, y: r.y + r.height/2, found: true };
        }
    }
    return { found: false };
});
if (!menuPos.found) throw new Error('Top menu not found: <menu text>');
await p.mouse.click(menuPos.x, menuPos.y);
await p.waitForTimeout(800);

// find the submenu item by exact text
var subPos = await p.evaluate(() => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
        const t = (el.textContent || '').trim();
        if (t === '<submenu text>' && el.children.length <= 2) {
            const r = el.getBoundingClientRect();
            if (r.width > 0) return { x: r.x + r.width/2, y: r.y + r.height/2, found: true };
        }
    }
    return { found: false };
});
if (subPos.found) {
    await p.mouse.click(subPos.x, subPos.y);
    await p.waitForTimeout(3500);
}
```

If the submenu cannot be located, dump all visible items in the viewport to debug:
```js
var items = await p.evaluate(() => {
    var list = [];
    function walk(root, depth) {
        if (depth > 10) return;
        var b = root.getBoundingClientRect();
        var t = (root.textContent || '').trim();
        if (b.width > 30 && b.width < 400 && b.height > 5 && b.y > 0 && b.y < 800
            && t.length > 0 && t.length < 30 && root.children.length < 3) {
            list.push({ t, x: b.x, y: b.y, w: b.width, h: b.height });
        }
        for (var c of (root.children || [])) walk(c, depth + 1);
    }
    walk(document.body, 0);
    return list;
});
```

### Step 6 — Verify the resulting IFrame / dialog

The extension typically opens an IFrame via `eda.sys_IFrame.openIFrame(...)` AND/OR a dialog via `eda.sys_Dialog.showInformationMessage(...)`. Check both:

```js
// dialog
var dialog = await p.evaluate(() => {
    const d = document.querySelector('.lc_modal_dialog_box_5wCN6, .lc_modal_dialog_zvEgQ');
    if (d) return d.textContent.trim().slice(0, 500);
    return null;
});
console.log('dialog:', dialog);

// iframe
var chatFrame = null;
for (var t = 0; t < 30; t++) {
    await p.waitForTimeout(500);
    for (var f of p.frames()) {
        var title = await f.title();
        if (title && title.indexOf('<expected keyword>') >= 0) { chatFrame = f; break; }
    }
    if (chatFrame) break;
}
```

Read the visible content:
```js
var text = await chatFrame.evaluate(() => document.body.innerText);
fs.writeFileSync('<output path>.txt', text, 'utf-8');
```

For chat IFrames that also accept user input:
```js
await chatFrame.fill('textarea', '<question>');
await chatFrame.evaluate(() => {
    var b = Array.from(document.querySelectorAll('button')).find(x => (x.textContent || '').indexOf('发送') >= 0);
    if (b) b.click();
});
```

### Step 7 — Wait for async content (e.g. AI response)

A single click-then-snapshot is not enough. Poll until the IFrame stops changing and exposes a final answer or error:
```js
var lastLen = 0, stableRounds = 0;
var start = Date.now();
while (Date.now() - start < 60000) {
    await p.waitForTimeout(1500);
    var info = await chatFrame.evaluate(() => ({
        len: document.body.innerText.length,
        isSending: typeof isSending !== 'undefined' ? isSending : null,
        hasError: !!document.querySelector('.error-msg')
    }));
    if (info.len !== lastLen) { lastLen = info.len; stableRounds = 0; }
    else stableRounds++;
    if (info.isSending === false && stableRounds >= 4) break;
}
```

The 4-round stable check absorbs the typing-indicator oscillation. 60s ceiling covers OpenAI-compatible reasoning tokens (deepseek-v4-pro takes 15-20s).

### Step 8 — Capture evidence

Take a full-page screenshot for the human reviewer, plus the innerText dump:
```js
await p.screenshot({ path: '<output path>.png' });
fs.writeFileSync('<output path>.txt', await chatFrame.evaluate(() => document.body.innerText), 'utf-8');
```

For baseline-vs-after comparison, save two screenshots with different prefixes (e.g. `v134-...` and `v135-...`).

## Validation rules (what "pass" looks like)

- Sch API discovered within 30s after F5 → EDA worker healthy.
- `getAllSelectedPrimitives_PrimitiveId().length > 0` after mouse drag → drag works.
- The clicked submenu opens a new IFrame whose `document.title` matches what `eda.sys_IFrame.openIFrame` was called with → menu wiring works.
- Dialog text after click is NOT the generic "请先框选" / "请先在原理图中框选" — those indicate a bug (e.g. string enum mismatch in V3.2).
- `document.body.innerText` of the IFrame contains a non-trivial analysis referencing the schematic's designators (e.g. `U1`, `U4`, `FPC1`) → AI API call succeeded.
- A 60s timeout with no `assistant` message → API key / network problem; check `eda.sys_Storage.getExtensionUserConfig('__ai_config')` from inside the IFrame.

## Common pitfalls

- **Closing the sch blob iframe** (V3.0) while doing unrelated IFrame cleanup → sch API disappears. Always filter by src content (`chat.html` / `result.html`) before calling `.remove()`.
- **Reusing the Playwright `textarea.fill` twice in a row** → second send can fire while first fetch is still pending, producing `AbortError: signal is aborted without reason`. Wait for `isSending === false` between sends.
- **Assuming `page.frames()[0]` is the sch frame** → it's the main editor page; sch is a sibling.
- **Forgetting to call `await p.waitForTimeout(3000+)` after import** → the menu shows up immediately, but the sch frame is reloading in the background.
- **Hardcoding 9224** when the user's debug port is different → probe `netstat -an | findstr LISTENING | findstr :9` first, or use `mcp dev_plugin` and discover the new port after.
- **`p.reload()` does NOT recover EDA under `cll=debug`** → only a real F5 in the user's browser fixes it.
- **V3.2: `Object.keys(eda.sch_SelectControl)` returns `[]`** — methods are on the prototype. Use `Object.getPrototypeOf` to enumerate.
- **V3.2: `getState_OwnerComponentDesignator` does not exist** — use `eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(primitiveId)` to reverse-lookup pin→component.
- **V3.2: `getState_PrimitiveType()` returns `'Component'` (string) not `'COMPONENT'` or `6`** — use string enum check.
- **V3.2: sch API throws "获取所有器件失败"** when called from main page proxy while sch canvas is not active (e.g. user is on home page, or just opened a non-sch tab). Make sure the user dblclicked into the sch tab.
- **`mcp import_plugin` 30s timeout** on V3.2 UI → always use `mcp dev_plugin` instead.
- **Assuming an "AI 思考中" state means success** — also check the dialog text and IFrame body. A hung fetch can leave "AI 思考中" up forever.

## Diagnosing "AI chat does not reply"

When the user opens the AI chat IFrame, types a question, clicks 发送, and nothing happens (no typing indicator, no reply, send button stays grey forever), the most common cause is **a global variable name collision inside the IFrame's own JS**. The IFrame is a `blob:` URL with its own `window`, but it still inherits many browser globals; redeclaring one as a `var` silently overwrites it.

Symptom fingerprint (what to look for in `chatFrame.evaluate`):
- `typeof chatMessages === 'undefined'` (or whatever the array variable should be named) — suspicious.
- `typeof history === 'undefined'` **but** the IFrame shows "已加载网表" → the script crashed mid-init but UI still rendered the welcome message.
- Click 发送 → `addMsg('user', text)` runs, then nothing — call to `history.push` (or similar) threw a TypeError; `try`/`catch`/`finally` for the fetch never reached.

Diagnostic path (proven on local-netlist-analyzer v1.2.0):
```js
// 1. confirm fetch endpoint is reachable from the IFrame
var r = await chatFrame.evaluate(async () => {
    var r = await fetch('https://<api>/v1/chat/completions', { method: 'POST', ... });
    return { status: r.status, body: (await r.text()).length };
});
// → if status=200 and body>0, network/API is fine

// 2. replace window.fetch and addMsg to see what doSend actually does
await chatFrame.evaluate(() => {
    var origFetch = window.fetch;
    window.fetch = function(...a) { console.log('FETCH', a[0]); return origFetch.apply(this, a); };
    var origAddMsg = window.addMsg;
    window.addMsg = function(role, c) { console.log('ADDMSG', role, (c||'').length); return origAddMsg(role, c); };
});

// 3. then click 发送 and read console output
// → if you see "ADDMSG user" but NEVER "FETCH ..." → doSend crashed between
// → if you see "FETCH ..." but no "ADDMSG assistant" → response parsing crashed
```

The fix is mechanical: rename the conflicting global to a non-reserved name (e.g. `history` → `chatMessages`, `location` → `myLocation`, `navigator` → `myNavigator`). Then rebuild and re-import via the MCP import_plugin tool.

Safe names for in-iframe state: `msgs`, `chatMessages`, `conversation`, `messages`, `dialogState`, `pendingTool`. Avoid: `history`, `location`, `navigator`, `status`, `name`, `length`, `top`, `parent`, `self`, `frames`, `document`, `event`.

## V3.2-specific debugging recipes

### Reasoning-model timeout map (verified on local-netlist-analyzer v1.3.5/3.6)

| Model | Real response time (16 器件 + 13 网络 prompt) | Recommended `setTimeout(controller.abort, ms)` |
|-------|-----------------------------------------------|------------------------------------------------|
| `gpt-4o-mini` / `gpt-3.5-turbo` | 2-4s | 60s (default) |
| `deepseek-chat` (non-reasoning) | 3-8s | 60s |
| `qwen2.5-72b-instruct` | 4-10s | 60s |
| `deepseek-v4-pro` (reasoning) | 60-120s (76s 实测) | 180s |
| `o1-preview` / `o1-mini` (reasoning) | 90-180s | 240s |
| `claude-3.7-sonnet-thinking` (reasoning) | 60-150s | 180-240s |

**Implementation tip**: store the per-model map in `cfg.timeoutMs` so users don't have to edit code:
```js
const MODEL_TIMEOUT = {
    'gpt-4o-mini': 60000,
    'deepseek-chat': 60000,
    'deepseek-v4-pro': 180000,
    'o1-preview': 240000,
};
var timeout = MODEL_TIMEOUT[cfg.model] || 180000;  // default 3min for safety
setTimeout(controller.abort, timeout);
```
The error message should mention the actual model and the time budget so users don't panic.

### "Save files" settings switch — verifying end-to-end (v1.3.8/3.9 pattern)

When the extension adds a `__file_config` checkbox in `settings.html` that gates file writes from `analyzeSelection`, the skill needs a 3-case test:

```js
// 0. Hook saveFile in the V3.2 sandbox, count invocations
const r = await p.evaluate((sk) => {
  const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
  const orig = eda.sys_FileSystem.saveFile;
  window._saveCount = 0;
  window._lastSaved = null;
  eda.sys_FileSystem.saveFile = async function(blob, name) {
    window._saveCount++;
    window._lastSaved = name + ':' + blob.size;
    return orig.call(this, blob, name);
  };
  return { hooked: true };
}, spaceKey);

// CASE 1: saveToDisk = true (after user checks the box)
await p.evaluate((sk) => {
  const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
  eda.sys_Storage.setExtensionUserConfig('__file_config', JSON.stringify({ saveToDisk: true }));
}, spaceKey);
// run analyzeSelection, then read _saveCount
// expect: _saveCount === 2  (csv + json)

// CASE 2: saveToDisk = false (default for new users)
await p.evaluate((sk) => {
  const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
  eda.sys_Storage.setExtensionUserConfig('__file_config', JSON.stringify({ saveToDisk: false }));
}, spaceKey);
// run analyzeSelection, then read _saveCount
// expect: _saveCount === 0  (no file IO)

// CASE 3: storage empty / new user install (simulate first run)
await p.evaluate((sk) => {
  const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
  eda.sys_Storage.setExtensionUserConfig('__file_config', null);
}, spaceKey);
// run analyzeSelection
// expect: _saveCount === 0  (defaults to false, no surprise file writes)
```

**Common bug shape** (v1.3.8 初版): only the HTML `checked` attribute was set; loadCfg() never re-syncs from storage. Result: checkbox shows checked but `__file_config.saveToDisk` is `undefined`, and `loadFileConfig()` falls back to its default. Always sync storage → UI explicitly:
```js
var fcfg = loadFileConfig();  // { saveToDisk: false }  default
cb.checked = (fcfg.saveToDisk === true);  // explicit ===, not truthy
```

**Why a separate `__file_config` key** (not nested under `__ai_config`): resetting AI config should not reset file save preference, and JSON parse failures in one config should not poison the other. Future config groups (theme, shortcuts) follow the same pattern.

### "Object.keys(eda.sch_SelectControl) returns [] — is eda broken?"

It is NOT broken. Methods are on the prototype. Confirm with:
```js
const r = await p.evaluate((sk) => {
  const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
  const sc = eda.sch_SelectControl;
  return {
    type: typeof sc,
    ownKeys: Object.keys(sc),
    protoMethods: Object.getOwnPropertyNames(Object.getPrototypeOf(sc)),
  };
}, spaceKey);
console.log(r);
// → protoMethods should include 'getAllSelectedPrimitives' etc.
```

### "AI 分析 always shows '请先框选' even after I selected 62 elements"

This is the V3.2 string-enum bug. Your code probably does:
```js
if (pt === 'COMPONENT' || pt === 6) {  // ❌ V3.0 style
```
V3.2 returns `'Component'`. Fix:
```js
if (pt === 'Component' || pt === 'COMPONENT' || pt === 6) {  // ✓ accept all
```

### "Pin reverse-lookup fails / owner is undefined"

V3.2 removed `pin.getState_OwnerComponentDesignator()`. Use:
```js
const allComps = await eda.sch_PrimitiveComponent.getAll();
for (const c of allComps) {
  const d = c.getState_Designator();
  const cp = c.getState_PrimitiveId();
  const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(cp);
  for (const p of pins) {
    if (selectedPinPrimIds.has(p.getState_PrimitiveId())) {
      // pin belongs to component with designator `d`
    }
  }
}
```

### "Right-click menu is missing"

You probably only have `extension.json.headerMenus` (V3.0 style). V3.2 also needs:
```json
{
  "contextMenus": {
    "sch": [
      {
        "id": "my-ctx",
        "title": "我的菜单",
        "menuItems": [
          { "id": "analyze", "title": "分析", "registerFn": "analyzeSelection" }
        ]
      }
    ]
  }
}
```
Or register at runtime via `eda.sys_RightClickMenu.changeMenu(menuId, items)`.

### "How do I confirm v1.X is the version currently loaded in Edge?"

Take a screenshot of the top-menu and the resulting dialog. The dialog text format includes the summary count, e.g. "AI 分析: 16元件 13网络" for v1.3.5. Comparing dialog text across runs is the cheapest regression check.

### Font-rendering trap: ASCII `|` looks like 「中」 in JLCEDA dialogs (v1.3.7 fix)

**Symptom**: Your dialog says "37选中中 54元件 40网络" — the separator between summary and detail looks like a Chinese character instead of a pipe.

**Root cause**: JLCEDA dialogs render text in the page's monospace CJK fallback font. ASCII `|` (U+007C) has no dedicated glyph in many CJK fonts and is silently substituted with the visually similar 「中」.

**Fix**: use a separator that has an explicit CJK glyph, in order of preference:
- `·` (U+00B7 MIDDLE DOT) — universal, works everywhere
- `｜` (U+FF5C FULLWIDTH VERTICAL BAR) — explicit CJK
- ` | ` (space-pipe-space) — only if the font renders pipe correctly (rare)

Verify by taking a screenshot and looking at the dialog pixel — text-based `innerText` won't catch the glyph substitution.

### `doSelectAll` fallback when the mouse drag selects zero (V3.0/V3.2)

If the sch canvas geometry is awkward and the drag reliably misses the canvas, the script can drive selection via API directly:
```js
// V3.0
await schFrame.evaluate(async () => {
  await eda.sch_SelectControl.doSelectAll();
  return eda.sch_SelectControl.getAllSelectedPrimitives_PrimitiveId();
});
// V3.2
await p.evaluate(async (sk) => {
  const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
  await eda.sch_SelectControl.doSelectAll();
  return eda.sch_SelectControl.getAllSelectedPrimitives_PrimitiveId();
}, spaceKey);
```
This is less authentic (no real "drag" gesture) but unblocks the rest of the E2E. Add a screenshot after to make the provenance clear.

### Three-tier `installV32Shim` decision (V3.0 / V3.2 sandbox / V3.2 main page)

The extension's `activate()` must handle three independent code paths without breaking each other:

| Environment | `window.eda` | `eda.sch_SelectControl.getAllSelectedPrimitives_PrimitiveId` | Action |
|-------------|--------------|-------------------------------------------------------------|--------|
| V3.0/3.1 (any) | populated, has sch_SelectControl | returns array | **No-op** — already compatible |
| V3.2 sandbox (extension runs in worker) | populated, V3.0-compatible shim already in place | returns array | **No-op** — the sandbox proxy wraps V3.2 plain properties back to getters |
| V3.2 main page (extension bundle accidentally lands there) | **missing**, only `_EXTAPI_ROOT_` exists | n/a | **Alias `eda = _EXTAPI_ROOT_`** + wrap 4 selection methods (`getAllSelectedPrimitives` / `getSelectedPrimitives` / `getPrimitivesByPrimitiveId` / `getPrimitiveByPrimitiveId`) to add legacy `getState_*` getters on each returned primitive |

Common bug (v1.3.3): the v1.3.3 shim aliased `eda = _EXTAPI_ROOT_` in the V3.2 sandbox, which already has its own V3.0-compatible eda — the alias overwrote a working object and broke things. v1.3.4 fixed by tier-based detection: only shim when both `eda` is missing AND `_EXTAPI_ROOT_` is present (i.e. main page only).

```ts
function installV32Shim() {
  if (g.eda && g.eda !== root && g.eda.sch_SelectControl) return;  // V3.0/3.1
  if (g.eda && g.eda.sch_SelectControl) { g.__edaShimInstalled = true; return; }  // V3.2 sandbox
  if (!root) return;                                                 // neither
  g.eda = root;                                                      // V3.2 main page
  // wrap 4 primitive-returning methods
}
```

### esbuild + V3.2 extension bundle output shape (verified)

The V3.2 extension bundle is shipped as an IIFE wrapped by EDA's bundle loader. Three gotchas when iterating on the build:

- **`__toCommonJS(src_exports)`** wraps ESM `export`s into a CommonJS shim. The resulting `src_exports` is an object with `default` and named keys, NOT a real CJS module. Top-level `export function foo()` is fine, but if you write `module.exports = ...` it collides.
- **All `eda` references inside the bundle run inside the worker**, not the main page — so `var eda = _EXTAPI_ROOT_` would refer to the worker's window, where eda is already the V3.0-compatible shim. Don't try to import `eda` from outside; the bundle captures it as a global.
- **Build must be IIFE**, not ESM, because EDA loads the bundle via `<script>` injection, not `import()`. Set `format: 'iife'` in `esbuild.config.js`.
- **Bundle must include the `iframe/*.html` assets** under the `iframe/` subpath of the .eext (which is a zip). The path passed to `eda.sys_IFrame.openIFrame` is `/iframe/chat.html`, relative to the bundle root.

Verify a fresh build with:
```js
var zip = new (require('adm-zip'))(eextPath);
console.log(zip.getEntries().map(e => e.entryName).sort());
// expect: index.js, extension.json, iframe/chat.html, iframe/settings.html
```

## Scripts bundled with this skill

- `scripts/run_workflow.js` — single-file runner that executes Steps 1-8 against a given `.eext` and a given menu label, with a configurable question. Output goes to `<workspace>/outputs/eda-tests/`.
- `references/eda-api-cheatsheet.md` — concise reference of the EDA API calls used by this skill (V3.0 + V3.2 note).
- `references/v3.2-sandbox-api.md` — **V3.2-specific** reference: sandbox location, prototype-chain methods, string enums, pin reverse-lookup, debug recipes.
- `references/common-failures.md` — debug cookbook for when something goes wrong.
- `references/ws-bridge.md` — WebSocket reverse bridge for headless EDA control.

## See also

- The project's `test/eda-*.js` scripts in `pro-api-sdk/test/` are prior runs of this workflow; they are the canonical examples of how to drive each step. When in doubt, copy one and adapt the menu name + question.
- For V3.2 enum/type verification, install `@jlceda/pro-api-types` and look at `ISCH_Primitive*` interfaces.
- For "what's the official example doing", see https://github.com/easyeda/eext-extension-demo (5 working extensions covering dialog, button, primitive add/delete/modify).
