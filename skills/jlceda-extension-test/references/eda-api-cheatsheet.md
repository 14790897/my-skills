# EDA API cheatsheet

Only the calls actually used by this skill. Full reference: https://prodocs.lceda.cn/cn/api/guide/how-to-start.html

> **V3.2+ NOTE (V3.2.148+):** `eda` is **NOT** in the main page anymore. It lives
> inside an extension sandbox: `window._EXTAPI_SCRIPT_SPACES_[extensionUuid].eda`.
> All the methods are on the prototype chain, so `Object.keys(eda.sch_SelectControl)`
> returns `[]` — use `Object.getPrototypeOf(eda.sch_SelectControl)` to enumerate.
> See [references/v3.2-sandbox-api.md](v3.2-sandbox-api.md) for the full V3.2
> reference and the migration cheatsheet (string enums, `getAllPinsByPrimitiveId`
> instead of `getState_OwnerComponentDesignator`, etc.).

## Selection

```js
// After a JLCEDA mouse drag, the selection lives in sch_SelectControl
var ids = await eda.sch_SelectControl.getAllSelectedPrimitives_PrimitiveId();
// ids: string[] of primitive IDs (UUIDs), e.g. ["gge1", "gge2", ...]

var prims = await eda.sch_SelectControl.getAllSelectedPrimitives();
// prims: Primitive[] — each has .getState_Designator() and .getState_PrimitiveType()
```

If a drag did not select anything but you need data, use the fallback:
```js
// Select all in current schematic
await eda.sch_SelectControl.doSelectAll();
```
(Some JLCEDA versions expose only `getSelectedPrimitives_PrimitiveId`; if both are present, prefer `getAllSelectedPrimitives_PrimitiveId`.)

## Netlist (the gold)

```js
var file = await eda.sch_ManufactureData.getNetlistFile('netlist', 'JLCEDA');
var text = await file.text();
// text is JSON of shape:
// {
//   "version": "2.0.0",
//   "components": {
//     "gge1": {
//       "props": { "Designator": "U1", "Value": "ESP32-WROOM-32" },
//       "pinInfoMap": { "1": { "net": "GND", "number": "1" } }
//     }
//   }
// }
```

Older formats (text-only `Protel2`, `EasyEDA`) are tried in `getNetlistText()` if the JSON call returns empty. Default the new JSON path.

## Storage (cross-IFrame data share)

```js
eda.sys_Storage.setExtensionUserConfig('__ai_config', JSON.stringify({ ... }));
var raw = eda.sys_Storage.getExtensionUserConfig('__ai_config');
```

`sessionStorage` and `localStorage` are PER-IFRAME — the extension's main module and the IFrame inside `eda.sys_IFrame.openIFrame` have separate scopes. Always use `eda.sys_Storage`.

## IFrame (the popup)

```js
eda.sys_IFrame.openIFrame(
    '/iframe/chat.html',                              // path inside the extension .eext zip
    700,                                              // width px
    560,                                              // height px
    'ai-chat',                                        // unique id
    { title: 'AI 电路分析', maximizeButton: true }    // options
);
```

The resulting IFrame runs in the same origin as the editor, so it can call back into `eda.*`. It does NOT auto-receive data — pass it via `eda.sys_Storage` before opening, or via the URL query string.

## Dialog (notifications)

```js
eda.sys_Dialog.showInformationMessage('Hello');   // OK dialog
```

Useful for surfacing "select something first" or "imported OK" without writing a custom modal.
