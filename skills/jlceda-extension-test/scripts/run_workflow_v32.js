// scripts/run_workflow_v32.js
// V3.2-specific E2E runner. Differences vs run_workflow.js:
//   - Connects to mcp-launched Edge (port from `dev_plugin`, e.g. 9269), not user's 9224
//   - Skips the "advanced menu → 扩展管理器 → 导入" import flow (mcp dev_plugin already did it)
//   - Uses `window._EXTAPI_SCRIPT_SPACES_[uuid].eda` instead of blob-frame walk
//   - dblclicks left-tree sch tab + handles "另有一个标签页" modal
//   - Top menu is `.top-bar-menu_JIQpX > *` (not arbitrary depth walk)
//   - Catches V3.2 "获取所有器件失败" or "请先框选" as a known-broken indicator
//   - Supports `--scenario settings|savetoggle|ai-chat` for sub-flows:
//       (default)   full e2e: sch tab + box select + menu click + dialog/iframe read
//       `settings`  open settings iframe, toggle saveToDisk, verify storage
//       `savetoggle` re-run analyzeSelection with saveToDisk=true/false/missing
//       `ai-chat`   open chat iframe, send a prefill, poll for assistant reply
//
// Usage:
//   node scripts/run_workflow_v32.js --eext "..." --menu "AI 分析局部网表" --cdp http://localhost:9269
//   node scripts/run_workflow_v32.js --eext "..." --scenario settings --cdp http://localhost:9269
//   node scripts/run_workflow_v32.js --eext "..." --scenario savetoggle --cdp http://localhost:9269
//   node scripts/run_workflow_v32.js --eext "..." --scenario ai-chat --cdp http://localhost:9269
//
// Outputs to <workspace>/outputs/eda-tests/ (PNG screenshots + txt innerText dumps).

'use strict';

var path = require('path');
var fs = require('fs');
var { chromium } = require('C:/Users/13963/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core');

function arg(name, fallback) {
    var i = process.argv.indexOf('--' + name);
    return i >= 0 ? process.argv[i + 1] : fallback;
}

var EEXT = arg('eext', '');
var MENU_TEXT = arg('menu', 'AI 分析局部网表');
var SUBMENU_TEXT = arg('submenu', MENU_TEXT);
var CDP = arg('cdp', 'http://localhost:9269');
var OUTDIR = arg('out', 'C:/Users/13963/WorkBuddy/2026-07-12-00-12-10/outputs/eda-tests');
var BASELINE = arg('baseline', null);  // when set, save as vXYZ- files; else vABC-
var SCENARIO = arg('scenario', 'default');  // default | settings | savetoggle | ai-chat

if (!EEXT) { console.error('ERROR: --eext <abs path> required'); process.exit(1); }
if (!fs.existsSync(EEXT)) { console.error('ERROR: file not found: ' + EEXT); process.exit(1); }
fs.mkdirSync(OUTDIR, { recursive: true });
var prefix = BASELINE || path.basename(EEXT, '.eext').replace(/^local-netlist-analyzer_/, '');

(async () => {
    console.log('=== V3.2 E2E runner ===');
    console.log('CDP:', CDP, '| .eext:', EEXT, '| menu:', MENU_TEXT, '| submenu:', SUBMENU_TEXT, '| scenario:', SCENARIO);
    console.log('Output prefix:', prefix);

    var b = await chromium.connectOverCDP(CDP);
    var ctx = b.contexts()[0];
    var p = ctx.pages()[0];
    if (!p || !p.url().includes('pro.lceda.cn/editor')) {
        p = await ctx.newPage();
        await p.goto('https://pro.lceda.cn/editor');
        await p.waitForTimeout(5000);
    }
    console.log('Page title:', await p.title());

    // --- Step: discover sandbox ---
    var spaceKey = await p.evaluate(() => {
        var spaces = window._EXTAPI_SCRIPT_SPACES_;
        return spaces ? Object.keys(spaces)[0] : null;
    });
    if (!spaceKey) { console.log('NO sandbox — extension not loaded'); await b.close(); return; }
    console.log('Sandbox key:', spaceKey);

    // --- Step: navigate to a sch tab ---
    var sch = await p.evaluate(() => {
        var all = document.querySelectorAll('li .tree-title_4dmpt, li');
        for (var el of all) {
            var t = (el.textContent || '').trim();
            if (/Schematic\d+_\d+/.test(t)) {
                var r = el.getBoundingClientRect();
                if (r.width > 0) return { x: r.x + r.width / 2, y: r.y + r.height / 2, txt: t };
            }
        }
        return null;
    });
    if (sch) {
        console.log('Opening sch tab:', sch.txt);
        await p.mouse.dblclick(sch.x, sch.y);
        await p.waitForTimeout(2000);
        // Handle "另有一个标签页" modal
        for (var i = 0; i < 10; i++) {
            var yes = await p.evaluate(() => {
                var dlg = document.querySelector('.lc_modal_dialog, [class*="modal"]');
                if (!dlg) return null;
                var all = dlg.querySelectorAll('button, .lc_btn, [class*="btn"]');
                for (var el of all) {
                    if ((el.textContent || '').trim() === '是') {
                        var r = el.getBoundingClientRect();
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

    // --- Step: wait for sch canvas ---
    var canvasBox = null;
    for (var t = 0; t < 20; t++) {
        var cs = await p.locator('canvas').count();
        if (cs >= 2) {
            var bx = await p.locator('canvas').nth(1).boundingBox();
            if (bx && bx.width > 800) { canvasBox = bx; break; }
        }
        await p.waitForTimeout(1000);
    }
    if (!canvasBox) { console.log('NO sch canvas after 20s'); await p.screenshot({ path: path.join(OUTDIR, prefix + '-no-sch.png') }); await b.close(); return; }
    console.log('Canvas:', JSON.stringify(canvasBox));
    await p.screenshot({ path: path.join(OUTDIR, prefix + '-A-sch.png') });

    // --- Step: box select ---
    var sx = canvasBox.x + canvasBox.width * 0.15, sy = canvasBox.y + canvasBox.height * 0.20;
    var ex = canvasBox.x + canvasBox.width * 0.60, ey = canvasBox.y + canvasBox.height * 0.55;
    await p.mouse.move(sx, sy);
    await p.mouse.down();
    for (var s = 1; s <= 20; s++) {
        await p.mouse.move(sx + (ex - sx) * s / 20, sy + (ey - sy) * s / 20);
        await p.waitForTimeout(20);
    }
    await p.mouse.up();
    await p.waitForTimeout(800);
    await p.screenshot({ path: path.join(OUTDIR, prefix + '-B-box-select.png') });

    // --- Step: click top menu (parent .top-bar-menu_JIQpX) ---
    var menuPos = await p.evaluate((t) => {
        var items = document.querySelectorAll('.top-bar-menu_JIQpX > *');
        for (var el of items) {
            if ((el.textContent || '').trim() === t) {
                var r = el.getBoundingClientRect();
                if (r.width > 0) return { x: r.x + r.width / 2, y: r.y + r.height / 2, found: true };
            }
        }
        return { found: false };
    }, MENU_TEXT);
    console.log('top menu:', JSON.stringify(menuPos));
    if (!menuPos.found) { await b.close(); return; }
    await p.mouse.click(menuPos.x, menuPos.y);
    await p.waitForTimeout(700);
    await p.screenshot({ path: path.join(OUTDIR, prefix + '-C-menu-open.png') });

    // --- Step: click submenu item ---
    var subPos = await p.evaluate((t) => {
        var all = document.querySelectorAll('*');
        for (var el of all) {
            if ((el.textContent || '').trim() === t && el.children.length <= 2) {
                var r = el.getBoundingClientRect();
                if (r.width > 0) return { x: r.x + r.width / 2, y: r.y + r.height / 2, found: true };
            }
        }
        return { found: false };
    }, SUBMENU_TEXT);
    console.log('submenu:', JSON.stringify(subPos));
    if (subPos.found) {
        await p.mouse.click(subPos.x, subPos.y);
        await p.waitForTimeout(4000);
    }
    await p.screenshot({ path: path.join(OUTDIR, prefix + '-D-after-click.png') });

    // --- Step: read dialog text + IFrame content ---
    var dialog = await p.evaluate(() => {
        var d = document.querySelector('.lc_modal_dialog_box_5wCN6, .lc_modal_dialog_zvEgQ');
        return d ? d.textContent.trim().slice(0, 500) : null;
    });
    console.log('dialog:', dialog);
    fs.writeFileSync(path.join(OUTDIR, prefix + '-dialog.txt'), dialog || '(no dialog)');

    // IFrame find by title
    var chatFrame = null;
    for (var t2 = 0; t2 < 15; t2++) {
        await p.waitForTimeout(500);
        for (var f of p.frames()) {
            var title = await f.title();
            if (title && (title.indexOf('AI') >= 0 || title.indexOf('网表') >= 0 || title.indexOf('分析') >= 0)) {
                chatFrame = f; break;
            }
        }
        if (chatFrame) break;
    }
    if (chatFrame) {
        var body = await chatFrame.evaluate(() => document.body.innerText);
        fs.writeFileSync(path.join(OUTDIR, prefix + '-iframe.txt'), body);
        console.log('iframe body length:', body.length);
    } else {
        console.log('NO iframe found');
    }

    // Close any modal
    await p.keyboard.press('Escape');
    await p.waitForTimeout(500);

    // --- Step: baseline-vs-after regression check ---
    if (dialog) {
        if (dialog.indexOf('请先框选') >= 0 || dialog.indexOf('请先在原理图中框选') >= 0) {
            console.log('❌ FAIL: dialog indicates the extension thinks nothing is selected');
            console.log('   Hint: this is usually the V3.2 string-enum bug (pt === "COMPONENT" not "Component")');
        } else if (dialog.indexOf('API') >= 0) {
            console.log('❌ FAIL: dialog indicates the sch API is not available in this environment');
        } else {
            console.log('✓ dialog text looks healthy: "' + dialog.slice(0, 80) + '"');
        }
    }

    await b.close();
    console.log('=== Default scenario done. Outputs in', OUTDIR, '===');

    // sub-scenario dispatch
    if (SCENARIO === 'settings') {
        await scenarioSettings(prefix, spaceKey);
    } else if (SCENARIO === 'savetoggle') {
        await scenarioSaveToggle(prefix, spaceKey);
    } else if (SCENARIO === 'ai-chat') {
        await scenarioAIChat(prefix, spaceKey);
    }
})();

// ---- sub-scenarios ----

async function scenarioSettings(prefix, spaceKey) {
    console.log('=== Scenario: settings iframe + saveToDisk toggle ===');
    var b = await chromium.connectOverCDP(CDP);
    var ctx = b.contexts()[0];
    var p = ctx.pages()[0];

    // 1. read current __file_config from storage
    var before = await p.evaluate((sk) => {
        const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
        var raw = eda.sys_Storage.getExtensionUserConfig('__file_config');
        return raw ? JSON.parse(raw) : null;
    }, spaceKey);
    console.log('Before:', before);

    // 2. open settings iframe
    await p.evaluate((sk) => {
        const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
        eda.sys_IFrame.openIFrame('/iframe/settings.html', 520, 480, 'ai-settings', { title: '设置' });
    }, spaceKey);
    await p.waitForTimeout(2000);

    // 3. find settings iframe and toggle the saveToDisk checkbox
    var settingsFrame = null;
    for (var t = 0; t < 15; t++) {
        await p.waitForTimeout(500);
        for (var f of p.frames()) {
            var title = await f.title();
            if (title && (title.indexOf('设置') >= 0 || title.indexOf('AI') >= 0)) { settingsFrame = f; break; }
        }
        if (settingsFrame) break;
    }
    if (!settingsFrame) { console.log('NO settings iframe'); await b.close(); return; }

    await p.screenshot({ path: path.join(OUTDIR, prefix + '-settings-open.png') });
    var beforeCheck = await settingsFrame.evaluate(() => {
        var cb = document.getElementById('saveToDisk');
        return cb ? { exists: true, checked: cb.checked } : { exists: false };
    });
    console.log('Checkbox before:', beforeCheck);

    // click the checkbox + click 保存
    await settingsFrame.evaluate(() => {
        var cb = document.getElementById('saveToDisk');
        if (cb && !cb.checked) cb.click();
    });
    await settingsFrame.evaluate(() => {
        var btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent || '').indexOf('保存') >= 0);
        if (btn) btn.click();
    });
    await p.waitForTimeout(1500);

    var after = await p.evaluate((sk) => {
        const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
        var raw = eda.sys_Storage.getExtensionUserConfig('__file_config');
        return raw ? JSON.parse(raw) : null;
    }, spaceKey);
    console.log('After:', after);
    await p.screenshot({ path: path.join(OUTDIR, prefix + '-settings-saved.png') });

    var pass = (after && after.saveToDisk === true);
    console.log(pass ? '✓ settings toggle works' : '❌ settings toggle broken');
    await b.close();
}

async function scenarioSaveToggle(prefix, spaceKey) {
    console.log('=== Scenario: saveToDisk end-to-end (3 cases) ===');
    var b = await chromium.connectOverCDP(CDP);
    var ctx = b.contexts()[0];
    var p = ctx.pages()[0];

    // hook saveFile
    await p.evaluate((sk) => {
        const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
        var orig = eda.sys_FileSystem.saveFile;
        window._saveCount = 0;
        window._lastSaved = null;
        eda.sys_FileSystem.saveFile = async function(blob, name) {
            window._saveCount++;
            window._lastSaved = name + ':' + blob.size;
            return orig.call(this, blob, name);
        };
    }, spaceKey);

    async function resetAndRun(label, fcfgValue) {
        await p.evaluate((args) => {
            const eda = window._EXTAPI_SCRIPT_SPACES_[args.sk].eda;
            eda.sys_Storage.setExtensionUserConfig('__file_config', args.val === null ? null : JSON.stringify({ saveToDisk: args.val }));
            window._saveCount = 0;
            window._lastSaved = null;
        }, { sk: spaceKey, val: fcfgValue });
        // call analyzeSelection directly via the registered export
        await p.evaluate((sk) => {
            const eda = window._EXTAPI_SCRIPT_SPACES_[sk].eda;
            return eda.sys_ExtensionManager.activate(eda.sys_ExtensionManager.getAllExtensions().find(e => e.uuid === sk));
        }, spaceKey);
        await p.waitForTimeout(500);
        // better: click the top menu directly
        var menuPos = await p.evaluate((t) => {
            var items = document.querySelectorAll('.top-bar-menu_JIQpX > *');
            for (var el of items) {
                if ((el.textContent || '').trim() === t) {
                    var r = el.getBoundingClientRect();
                    if (r.width > 0) return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
                }
            }
            return null;
        }, '分析选中区域网表');
        if (menuPos) {
            await p.mouse.click(menuPos.x, menuPos.y);
            await p.waitForTimeout(2500);
        }
        var c = await p.evaluate(() => window._saveCount);
        console.log(label, '→ saveCount =', c, '| lastSaved =', await p.evaluate(() => window._lastSaved));
        return c;
    }

    var c1 = await resetAndRun('CASE 1 (saveToDisk=true)', true);
    var c2 = await resetAndRun('CASE 2 (saveToDisk=false)', false);
    var c3 = await resetAndRun('CASE 3 (storage=null, new install)', null);

    var pass = (c1 === 2 || c1 === 1) && c2 === 0 && c3 === 0;
    console.log(pass
        ? '✓ savetoggle: true→writes, false→none, new→none'
        : `❌ savetoggle broken: c1=${c1} c2=${c2} c3=${c3} (expect c1>=1, c2=0, c3=0)`);
    await p.screenshot({ path: path.join(OUTDIR, prefix + '-savetoggle.png') });
    await b.close();
}

async function scenarioAIChat(prefix, spaceKey) {
    console.log('=== Scenario: AI chat IFrame + prefill auto-send ===');
    var b = await chromium.connectOverCDP(CDP);
    var ctx = b.contexts()[0];
    var p = ctx.pages()[0];

    // open chat via top menu
    var menuPos = await p.evaluate((t) => {
        var items = document.querySelectorAll('.top-bar-menu_JIQpX > *');
        for (var el of items) {
            if ((el.textContent || '').trim() === t) {
                var r = el.getBoundingClientRect();
                if (r.width > 0) return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
            }
        }
        return null;
    }, 'AI 分析局部网表');
    if (!menuPos) { console.log('menu not found'); await b.close(); return; }
    await p.mouse.click(menuPos.x, menuPos.y);
    await p.waitForTimeout(4000);

    var chatFrame = null;
    for (var t = 0; t < 20; t++) {
        await p.waitForTimeout(500);
        for (var f of p.frames()) {
            var title = await f.title();
            if (title && (title.indexOf('AI') >= 0 || title.indexOf('分析') >= 0)) { chatFrame = f; break; }
        }
        if (chatFrame) break;
    }
    if (!chatFrame) { console.log('NO chat iframe'); await p.screenshot({ path: path.join(OUTDIR, prefix + '-no-chat.png') }); await b.close(); return; }
    await p.screenshot({ path: path.join(OUTDIR, prefix + '-chat-open.png') });

    // poll for assistant reply (reasoning models need up to 180s)
    var start = Date.now();
    var lastLen = 0, stable = 0;
    while (Date.now() - start < 200000) {  // 200s ceiling for reasoning models
        await p.waitForTimeout(2000);
        var info = await chatFrame.evaluate(() => {
            var body = document.body.innerText;
            var hasAssistant = !!Array.from(document.querySelectorAll('*')).find(el =>
                (el.textContent || '').trim().length > 0 && (el.className || '').indexOf('assistant') >= 0
            );
            return { len: body.length, isSending: typeof isSending !== 'undefined' ? isSending : null, hasAssistant };
        });
        if (info.len !== lastLen) { lastLen = info.len; stable = 0; console.log('  t=' + Math.floor((Date.now() - start) / 1000) + 's len=' + info.len + ' sending=' + info.isSending); }
        else stable++;
        if (info.isSending === false && stable >= 3) break;
    }
    var body = await chatFrame.evaluate(() => document.body.innerText);
    fs.writeFileSync(path.join(OUTDIR, prefix + '-ai-chat.txt'), body);
    await p.screenshot({ path: path.join(OUTDIR, prefix + '-ai-chat.png') });
    console.log('Final body length:', body.length);
    await b.close();
}
