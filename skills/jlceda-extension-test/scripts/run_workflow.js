// scripts/run_workflow.js
// End-to-end runner for the jlceda-extension-test skill.
// Usage: node scripts/run_workflow.js --eext "<abs path>" --menu "AI 分析局部网表" --question "..."
// Outputs to <workspace>/outputs/eda-tests/ if writable, else /tmp/eda-tests/.

'use strict';

var path = require('path');
var fs = require('fs');
var { chromium } = require('C:/Users/13963/WorkBuddy/2026-07-12-00-12-10/extension-dev-mcp-tools/node_modules/playwright-core');

// ---- args ----
function arg(name, fallback) {
    var i = process.argv.indexOf('--' + name);
    return i >= 0 ? process.argv[i + 1] : fallback;
}

var EEXT = arg('eext', '');
var MENU_TEXT = arg('menu', 'AI 分析局部网表');
var QUESTION = arg('question', '这是什么类型的电路?100 字内回答。');
var CDP = arg('cdp', 'http://localhost:9224');
var OUTDIR = arg('out', 'C:/Users/13963/WorkBuddy/2026-07-12-00-12-10/outputs/eda-tests');

if (!EEXT) {
    console.error('ERROR: --eext <abs path> required');
    process.exit(1);
}
if (!fs.existsSync(EEXT)) {
    console.error('ERROR: file not found: ' + EEXT);
    process.exit(1);
}
if (!fs.existsSync(OUTDIR)) fs.mkdirSync(OUTDIR, { recursive: true });

// ---- helpers ----
function shot(p, name) {
    return p.screenshot({ path: path.join(OUTDIR, name) })
        .then(() => console.log('  [shot]', name))
        .catch(e => console.log('  [shot-fail]', name, e.message.substring(0, 60)));
}

function findByText(p, text, opts) {
    opts = opts || {};
    var minW = opts.minW || 0;
    var maxW = opts.maxW || 1e9;
    return p.evaluate(function (args) {
        function walk(root, depth) {
            if (depth > 10 || !root) return null;
            try {
                var t = (root.textContent || '').trim();
                if (t === args.text && root.children.length < 3) {
                    var r = root.getBoundingClientRect();
                    if (r.width >= args.minW && r.width <= args.maxW && r.height > 0) {
                        return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height };
                    }
                }
                for (var c of (root.children || [])) {
                    var f = walk(c, depth + 1);
                    if (f) return f;
                }
            } catch (e) {}
            return null;
        }
        return walk(document.body, 0);
    }, { text: text, minW: minW, maxW: maxW });
}

function findSchFrame(p, timeoutMs) {
    timeoutMs = timeoutMs || 30000;
    return new Promise(function (resolve) {
        var start = Date.now();
        (function poll() {
            (async function () {
                for (var f of p.frames()) {
                    try {
                        var has = await f.evaluate(() => !!(window.eda && window.eda.sch_SelectControl));
                        if (has) return resolve(f);
                    } catch (e) {}
                }
                if (Date.now() - start > timeoutMs) return resolve(null);
                setTimeout(poll, 1000);
            })();
        })();
    });
}

// ---- main ----
(async function () {
    var b = await chromium.connectOverCDP(CDP);
    var p = b.contexts()[0].pages()[0];
    console.log('PAGE:', await p.title());

    // Step: import if menu not present
    console.log('\n--- Check menu visibility ---');
    var menuBefore = await findByText(p, MENU_TEXT, { minW: 30, maxW: 400 });
    if (!menuBefore) {
        console.log('  Menu not visible, importing ' + EEXT);
        // Click 高级
        try {
            await p.locator('span[data-test="Advanced"]').click({ timeout: 2000 });
        } catch (e) {
            await p.locator('.tool-bottom-menu-more_SoDfO').click();
            await p.waitForTimeout(500);
            await p.locator('.tool-bottom-menu-more-container_NmJv7 span[data-test="Advanced"]')
                .evaluate(el => el.click());
        }
        await p.waitForTimeout(300);
        await p.getByText('扩展管理器', { exact: false }).click({ timeout: 10000 });
        var modal = p.locator("[class*='lc_modal_dialog']").first();
        await modal.waitFor({ state: 'visible', timeout: 10000 });
        var [chooser] = await Promise.all([
            p.waitForEvent('filechooser', { timeout: 10000 }),
            modal.locator('button', { hasText: '导入' }).click()
        ]);
        await chooser.setFiles(EEXT);
        await p.waitForTimeout(2000);
        await modal.locator("[class*='close']").first().click().catch(() => p.keyboard.press('Escape'));
        await p.waitForTimeout(1500);
        console.log('  Imported. NOTE: sch API may be lost — user must F5 if next step fails.');
    } else {
        console.log('  Menu already visible at', menuBefore);
    }

    // Step: find sch frame
    console.log('\n--- Find EDA sch frame ---');
    var sch = await findSchFrame(p, 15000);
    if (!sch) {
        console.log('  sch frame NOT found. Tell user to F5 the project page and re-run.');
        await shot(p, 'no-sch.png');
        process.exit(2);
    }
    console.log('  sch frame found');

    // Step: mouse-drag select
    console.log('\n--- Mouse-drag select ---');
    var canvasInfo = await p.evaluate(() => {
        var list = [];
        for (var c of document.querySelectorAll('canvas')) {
            var b = c.getBoundingClientRect();
            if (b.width > 200 && b.height > 200) list.push({ x: b.x, y: b.y, w: b.width, h: b.height });
        }
        return list;
    });
    if (canvasInfo.length === 0) { console.log('  no canvas'); process.exit(3); }
    var c = canvasInfo[0];
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
    var sel = await sch.evaluate(async () => {
        var ids = await eda.sch_SelectControl.getAllSelectedPrimitives_PrimitiveId();
        return { count: ids ? ids.length : 0 };
    });
    console.log('  Selection count:', sel.count);
    await shot(p, 'after-drag.png');

    // Step: click menu
    console.log('\n--- Click menu: ' + MENU_TEXT + ' ---');
    var menuPos = await findByText(p, MENU_TEXT, { minW: 30, maxW: 400 });
    if (!menuPos) { console.log('  menu not found'); process.exit(4); }
    await p.mouse.click(menuPos.x, menuPos.y);
    await p.waitForTimeout(800);
    await shot(p, 'menu-open.png');

    // Find submenu item with same text and click
    var subPos = await findByText(p, MENU_TEXT, { minW: 30, maxW: 400 });
    if (subPos && (subPos.x !== menuPos.x || subPos.y !== menuPos.y)) {
        await p.mouse.click(subPos.x, subPos.y);
        console.log('  clicked submenu at', subPos);
    } else {
        // Dump items in viewport for diagnosis
        var items = await p.evaluate(() => {
            var list = [];
            function walk(root, depth) {
                if (depth > 10) return;
                var b = root.getBoundingClientRect();
                var t = (root.textContent || '').trim();
                if (b.width > 30 && b.width < 400 && b.height > 5 && b.y > 0 && b.y < 800
                    && t.length > 0 && t.length < 30 && root.children.length < 3) {
                    list.push({ t, x: Math.floor(b.x), y: Math.floor(b.y), w: b.width, h: b.height });
                }
                for (var c of (root.children || [])) walk(c, depth + 1);
            }
            walk(document.body, 0);
            return list;
        });
        console.log('  Submenu items in viewport:');
        items.forEach(i => console.log('   ', i.t, '|', i.x, i.y, i.w, 'x', i.h));
    }
    await p.waitForTimeout(1500);

    // Step: find AI IFrame
    console.log('\n--- Find AI IFrame ---');
    var chat = null;
    for (var t = 0; t < 30; t++) {
        await p.waitForTimeout(500);
        for (var f of p.frames()) {
            try {
                var title = await f.title();
                if (title && (title.indexOf('AI') >= 0 || title.indexOf('分析') >= 0)) {
                    chat = f; break;
                }
            } catch (e) {}
        }
        if (chat) break;
    }
    if (!chat) {
        console.log('  no AI IFrame found');
        await shot(p, 'no-iframe.png');
        process.exit(5);
    }
    console.log('  AI IFrame:', await chat.title());

    // Step: send question
    console.log('\n--- Send question ---');
    await chat.fill('textarea', QUESTION).catch(e => console.log('  fill err:', e.message));
    await p.waitForTimeout(500);
    await chat.evaluate(() => {
        var b = Array.from(document.querySelectorAll('button')).find(x => (x.textContent || '').indexOf('发送') >= 0);
        if (b) b.click();
    });
    console.log('  sent:', QUESTION);

    // Step: wait for response
    var start = Date.now();
    var lastLen = 0, stableRounds = 0;
    while (Date.now() - start < 60000) {
        await p.waitForTimeout(1500);
        var info = await chat.evaluate(() => ({
            len: document.body.innerText.length,
            isSending: typeof isSending !== 'undefined' ? isSending : null,
            hasError: !!document.querySelector('.error-msg')
        }));
        if (info.len !== lastLen) {
            console.log('   t=' + Math.floor((Date.now() - start) / 1000) + 's, len=' + info.len + ', sending=' + info.isSending);
            lastLen = info.len; stableRounds = 0;
        } else stableRounds++;
        if (info.isSending === false && stableRounds >= 4) break;
    }
    var finalText = await chat.evaluate(() => document.body.innerText);
    fs.writeFileSync(path.join(OUTDIR, 'final-chat.txt'), finalText, 'utf-8');
    await shot(p, 'final.png');
    console.log('\nFinal text length:', finalText.length);
    console.log('Saved to', OUTDIR);
    await b.close();
})();
