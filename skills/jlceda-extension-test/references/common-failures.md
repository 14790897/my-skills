# Common failures and fixes

Symptoms are listed first; root cause follows; fix is the last paragraph.

## "sch frame NOT found. Tell user to F5."

`walk(p.frames())` returns no frame with `window.eda && window.eda.sch_SelectControl`, even after a 30s wait.

Most likely cause: the user previously closed a `blob:` iframe that was on the `https://pro.lceda.cn` origin, and that closed the sch blob frame too. Or, the extension was just re-imported under `cll=debug`, which causes JLCEDA to drop the sch API injection.

`page.reload()` does NOT fix this. The user must press F5 in the browser, then wait 10-15s for the sch worker to mount again.

## "AI chat NOT opened"

`page.frames()` never grew a new frame whose title contains "AI" or "分析". Most likely the menu click did not register, or the menu click registered but `eda.sys_IFrame.openIFrame` failed (catch swallowed the error).

Dump all visible menu items in the viewport right after the click to see what dropped down. If the dropdown did not appear, the click coordinates were wrong — re-scan with `findByText(p, MENU_TEXT)` and check that the parent `span` is actually clickable (vs a child).

## "AbortError: signal is aborted without reason"

`fetch` to the OpenAI-compatible API was aborted. Two real causes:

1. The user (or your test script) clicked "发送" twice within ~20s, and the first click's `AbortController` got aborted when the second send reset state.
2. The page reloaded (e.g. the IFrame itself was destroyed) while the request was in flight.

Fix: only click once, then poll `isSending` until it flips back to `false` before any further interaction. If a single send reproduces the abort, the API endpoint's CORS or network is the problem — verify with the project's `test/test-usage.js` direct-call script.

## Stuck "AI 思考中..." with no completion

`document.body.innerText` does not grow for 60s and the `history` array stays the same length. Three causes:

1. The fetch never fired — the user's `cfg` is missing a model or key. Open the IFrame DevTools console and check the value of `cfg` (a global var inside `chat.html`).
2. The fetch returned 200 but the response body has no `choices[0].message.content` (only `reasoning_tokens`). Increase `max_tokens` to 4000+ for deepseek-v4-pro.
3. The endpoint is reachable but the upstream model is overloaded — wait 30s and retry.

## "TypeError: Cannot read properties of undefined (reading 'role')"

You called `JSON.stringify(history[i])` and `i` is out of bounds, or the IFrame's `history` is a different variable than you think. Wrap with `try/catch` and bounds-check:

```js
var lastAssistant = '';
for (var i = (history || []).length - 1; i >= 0; i--) {
    if (history[i] && history[i].role === 'assistant') { lastAssistant = history[i].content || ''; break; }
}
```

## mcp `import_plugin` says "浏览器启动超时"

The tool wants to launch its own Chrome on a hashed port (9222-9321), but Chrome is already running on the user's main 9224 and there is no other instance. Either:

- Accept the new browser (the user must re-login via QR), or
- Skip the mcp tool and use the Playwright `doImport` flow in `../scripts/run_workflow.js` against 9224.

If you really want the mcp tool to work, the user must fully quit Chrome (and any auto-restored sessions) so the tool can spawn a fresh instance. This is rarely worth it.

## `page.evaluate` returns `ReferenceError: eda is not defined`

You are evaluating on the main `page`, not on the sch frame. Always use `schFrame.evaluate(...)` for any `eda.*` call. Use `p.evaluate(...)` only for the editor's own DOM (menu, canvas, modals).

## The drag selects zero primitives

`getAllSelectedPrimitives_PrimitiveId().length === 0` after a `mouse.move` + `mouse.down` + `mouse.move` + `mouse.up` sequence.

Most likely: the drag start point is outside the canvas, or the schematic is in a different viewport than the page. Re-check `canvasInfo` — if the canvas `x` is e.g. `0,0,300,150`, that's the placeholder main-page canvas, not the real schematic. Find the canvas whose `width > 200` and `height > 300`.

Fallback: skip the drag and call `await eda.sch_SelectControl.doSelectAll()` from inside the sch frame. This is less authentic but useful when verifying the rest of the pipeline.

## V3.2-specific failures

### "mcp `import_plugin` 30s timeout finding `.tool-bottom-menu-more_SoDfO`"

V3.2 UI removed that class. **Use `mcp dev_plugin` instead** — it auto-starts Edge on a hashed port and listens for errors. The user will need to re-scan QR.

### "AI 分析 always says '请先框选' even after selecting 62 elements"

V3.2 string-enum bug. Your code does:
```js
if (pt === 'COMPONENT' || pt === 6) { /* never matches */ }
```
V3.2 returns `'Component'` (string, capital C, no other cases). Fix:
```js
if (pt === 'Component' || pt === 'COMPONENT' || pt === 6) { /* works for both V3.0 and V3.2 */ }
```
Same applies to `'ComponentPin'`, `'Wire'`, `'Text'` (not `'WIRE'`, etc.).

### "Pin.getState_OwnerComponentDesignator is not a function"

V3.2 removed that method. Use `eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(primitiveId)` to find which component owns a pin via its primitiveId reverse-lookup. See [v3.2-sandbox-api.md](v3.2-sandbox-api.md#pin-to-component-reverse-lookup-v32-way).

### "Object.keys(eda.sch_SelectControl) returns [] — is eda broken?"

No. V3.2 puts methods on the prototype chain, not own properties. Verify with:
```js
Object.getOwnPropertyNames(Object.getPrototypeOf(eda.sch_SelectControl))
```
You should see `getAllSelectedPrimitives`, `clearSelected`, `getAllSelectedPrimitives_PrimitiveId`, etc.

### "sch_PrimitiveComponent.getAll() throws '获取所有器件失败'"

The sch canvas is not active — the user is on the home page or a non-sch tab. Tell them to double-click into the sch tab in the left tree, and wait for the second canvas (>1000px wide) to appear before retrying.

### "mcp `dev_plugin` returns but `netstat` shows no Edge listening on 9xxx"

Wait a bit longer (mcp has a 5-minute default timeout but the actual start usually takes 20-30s). Also confirm with `tasklist /FI "IMAGENAME eq msedge.exe"` that an Edge process is running. If it is but the port isn't bound, kill all msedge.exe and retry.

### "I clicked the top menu but the submenu items don't appear"

V3.2's top menu uses a single `class="eda-menu-btn_YzjIq"` wrapper. Click on the SPAN/inner text directly, not on the surrounding `DIV`. Use the `.top-bar-menu_JIQpX > *` selector to disambiguate from sidebar tree items that may share the same display text.

## "AI 请求超时(60s), 请检查网络或 API 配置" — but endpoint actually works

**Symptom**: User clicks "AI 分析局部网表", AI chat IFrame opens, prefill prompt sends, then a red error box "请求超时(60s), 请检查网络或 API 配置" appears. Curl on the same endpoint returns 200 in 1-2s.

**Root cause**: deepseek-v4-pro and other reasoning models spend 60-120s producing `reasoning_content` (the internal "thinking" before the visible answer). The chat.html's `AbortController` was set to 60s, so it aborts the request *just before* the server returns 200 OK. The actual network is fine; the model is just slow.

**Diagnostic**:
```js
// Inside the chat blob iframe:
const t0 = Date.now();
const resp = await fetch(cfg.endpoint + '/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + cfg.key },
    body: JSON.stringify({
        model: cfg.model,
        messages: chatMessages.slice(0, 2),  // system + first user
        max_tokens: 4000,                      // the actual budget that triggered the slowness
    })
});
const ms = Date.now() - t0;
console.log(ms, resp.status, (await resp.text()).length);
// If ms > 60000 and status === 200 → reasoning model slowness, NOT network
```

**Fix**:
- Bump AbortController timeout in `iframe/chat.html` from `60000` to `180000` (or higher for very deep reasoning).
- Update the error message accordingly: "请求超时(180s)。deepseek-v4-pro 等推理模型思考时间较长, 如频繁超时请检查网络或换更快的模型"
- If a user is on a non-reasoning model (gpt-4o-mini, etc.), they can keep the 60s default; consider a per-model config map: `{ 'gpt-4o-mini': 60000, 'deepseek-v4-pro': 180000, 'o1-preview': 240000 }`.

**Real example from local-netlist-analyzer v1.3.5 → v1.3.6**:
- v1.3.5: `setTimeout(controller.abort, 60000)` → always timed out on 16-element netlist analysis
- v1.3.6: `setTimeout(controller.abort, 180000)` → 76s response, full analysis delivered

## "Dialog text shows pipe character as 中 — visual confusion" (v1.3.7)

**Symptom**: User reports dialog text reads as "37选中中 54元件 40网络" — there appear to be two `中` characters in the summary, looking like a rendering bug.

**Root cause**: The dialog uses an ASCII `|` (U+007C) as a separator between summary and detail. JLCEDA's monospace CJK font has no glyph for U+007C, so the browser falls back to a visually similar CJK character (often 「中」). The `innerText` is correct; only the visual rendering is misleading.

**Diagnostic**:
```js
// Take a screenshot — text in screenshot will differ from text in DOM
var txt = await p.evaluate(() => {
  var d = document.querySelector('.lc_modal_dialog_box_5wCN6');
  return d ? d.textContent.trim() : null;
});
console.log('innerText:', JSON.stringify(txt));  // → "37选中 | 54元件 40网络"
// But screenshot shows "37选中中 54元件 40网络" — only visible in the image
```

**Fix**: replace ASCII `|` with a CJK-explicit separator. In order of preference:
- `·` (U+00B7 MIDDLE DOT) — recommended, works in all CJK fonts
- `｜` (U+FF5C FULLWIDTH VERTICAL BAR) — explicit CJK, but uglier
- `\u2022` (BULLET) — also good, but less common in CJK text

**Real example from local-netlist-analyzer v1.3.6 → v1.3.7**:
- v1.3.6: `r.summary + '  |  ' + detail.join(' | ')` → "37选中 | 54元件 40网络" rendered as "37选中中 54元件 40网络"
- v1.3.7: `r.summary + '  ·  ' + detail.join(' · ')` → "37选中 · 54元件 40网络" rendered correctly

Always take a screenshot to verify — never trust `innerText` for separator glyphs.

## "installV32Shim broke the V3.2 sandbox" (v1.3.3 regression, fixed v1.3.4)

**Symptom**: After upgrading to a new version that adds `installV32Shim`, the V3.2 sandbox reports "请先框选" even when components are selected. V3.0 still works.

**Root cause**: v1.3.3 unconditionally aliased `eda = _EXTAPI_ROOT_` in any environment where `_EXTAPI_ROOT_` was present, including the V3.2 sandbox. The V3.2 sandbox's own `eda` is **already V3.0-compatible** (it wraps the V3.2 plain-property primitives back to getters), so the alias overwrote a working shim with the raw `_EXTAPI_ROOT_` (which has plain properties, no getters).

**Diagnostic**:
```js
const r = await p.evaluate((sk) => {
  const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
  return {
    shimInstalled: !!window.__edaShimInstalled,
    // After v1.3.3, this would return undefined because the alias overwrote the shim
    hasGetStateOnPrim: typeof eda.sch_SelectControl.getAllSelectedPrimitives === 'function',
  };
}, spaceKey);
```

**Fix** (v1.3.4 — three-tier detection):
```ts
if (g.eda && g.eda !== root && g.eda.sch_SelectControl) return;  // V3.0/3.1 → no-op
if (g.eda && g.eda.sch_SelectControl) {                            // V3.2 sandbox → no-op (already shimmed)
  g.__edaShimInstalled = true;
  return;
}
if (!root) return;                                                 // neither → bail
g.eda = root;                                                      // V3.2 main page → real shim
// wrap 4 primitive-returning methods to add getState_* getters
```

The key insight: **the V3.2 sandbox is more compatible than the V3.2 main page**. The sandbox already gives you V3.0-style getters; only the main page needs help.

## "JLCEDA settings.html 加新配置项不生效" — 几个易错点

**Symptom**: 你在 settings.html 加了新输入框 (checkbox/select/text), 但 storage 里读不到值, 或者改完不存。

**根因**: settings.html 默认只有 AI 相关 4 个字段 (`endpoint/key/model/systemPrompt`)。加新字段时 3 处都要改:
1. HTML 加 `<input id="...">` 节点
2. JS `loadCfg()` 读 + 写到 input.value (默认要 fallback, 不要崩)
3. JS `doSave()` 从 input 读 + 写到 storage
4. JS `doReset()` 重置 input.value 到默认

**真错例子 (v1.3.8)**: 加 `__file_config.saveToDisk` 开关, 一开始只改了 HTML, 没改 JS, 结果 checkbox 显示 checked (HTML `checked` 属性), 但 `__file_config` storage 永远是 undefined。下次 read 时 `loadFileConfig()` fallback 到默认 true, 用户以为生效实际没存。

**修复**: loadCfg 一定要把 checkbox 状态从 storage 同步到 UI (`cb.checked = (fcfg.saveToDisk !== false)`), 不要只靠 HTML 默认值。

**独立 storage key**: 文件保存配置不要塞进 `__ai_config`, 用独立 `__file_config`。否则:
- 重置 AI 配置会顺便把文件保存也重置
- `__ai_config` 字段顺序/解析失败会影响文件保存
- 未来如果加更多独立配置(主题/快捷键),可以保持 storage 结构清晰

**测试方法**:
```js
// 1. patch saveFile in sandbox, 计数
eda.sys_FileSystem.saveFile = async function(blob, name) {
    window._saveCount = (window._saveCount || 0) + 1;
    window._lastSaved = name + ':' + blob.size;
    return orig.call(this, blob, name);
};

// 2. 跑 analyzeSelection, 看 _saveCount
// TEST 1 (saveToDisk=true): _saveCount = 2
// TEST 2 (saveToDisk=false): _saveCount = 0
```
