# WebSocket Reverse Bridge (v1.2.0+)

The local-netlist-analyzer extension acts as a WebSocket **client** that
dials out to a local server on ws://127.0.0.1:9050 (or 9051..9059 if 9050
is taken). External scripts (LLM agents, CI jobs, websocat) run a
small WS server and send JSON-RPC requests to invoke any EDA API
through reflection — bypassing all Playwright / blob-frame issues
when EDA sch API is hidden.

## Why this exists

Playwright can fail to see `window.eda` in three situations:
1. URL has `?cll=debug` (returns `eda` but with 0 keys)
2. EDA is in a nested `blob:` frame Playwright's `frames()` cannot reach
3. mcp-launched Edge profile fails to render the sch editor entirely

The WebSocket bridge sidesteps all three: the extension code runs
**inside the page** (so it sees the real `eda` object) and exposes
the APIs over a localhost WebSocket that Playwright/Node can call
from outside.

## Protocol (matches jlc-eda-mcp convention)

### Server -> Client (request)
```json
{
  "type": "request",
  "id": "r1",
  "method": "sch_SelectControl.doSelectAll",
  "params": [],
  "closeAfterResponse": false
}
```

### Client -> Server (response)
```json
{
  "type": "response",
  "id": "r1",
  "ok": true,
  "result": ["gge1", "gge2", ...]
}
```

### Client -> Server (hello, on connect)
```json
{
  "type": "hello",
  "bridge": "local-netlist-analyzer",
  "version": "1.2.0",
  "app": { "version": "3.2.148" },
  "api": ["sch_SelectControl", "sch_ManufactureData", "sys_IFrame", ...],
  "project": { "uuid": "...", "name": "墨鱼AI墨水屏" }
}
```

## Method paths

Use dotted `Class.method` paths matching the JLCEDA namespace:

| Path | What it does |
|------|--------------|
| `sch_SelectControl.doSelectAll` | select all in schematic |
| `sch_SelectControl.getAllSelectedPrimitives_PrimitiveId` | list selected IDs |
| `sch_ManufactureData.getNetlistFile` | get netlist (returns File) |
| `dmt_DocumentManager.getCurrentDocument` | current doc info |
| `sys_IFrame.openIFrame` | open any extension IFrame |
| `sys_FileSystem.saveFile` | trigger a file save dialog |
| `sys_Dialog.showInformationMessage` | show toast |

## Server (Node + ws) example

```javascript
const { WebSocketServer } = require('ws');
const wss = new WebSocketServer({ port: 9050 });
let sock = null;
const pending = new Map();

wss.on('connection', (ws) => {
    sock = ws;
    ws.on('message', (data) => {
        const msg = JSON.parse(data);
        if (msg.type === 'response' && pending.has(msg.id)) {
            const p = pending.get(msg.id);
            pending.delete(msg.id);
            msg.ok ? p.resolve(msg.result) : p.reject(new Error(msg.error));
        }
    });
});

function call(method, params = [], timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
        if (!sock) return reject(new Error('No bridge'));
        const id = 'r' + Date.now();
        pending.set(id, { resolve, reject });
        setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error('timeout')); } }, timeoutMs);
        sock.send(JSON.stringify({ type: 'request', id, method, params }));
    });
}

// Usage:
(async () => {
    await call('sch_SelectControl.doSelectAll');
    const ids = await call('sch_SelectControl.getAllSelectedPrimitives_PrimitiveId');
    const file = await call('sch_ManufactureData.getNetlistFile', ['netlist', 'JLCEDA']);
})();
```

## Activation requirements

The bridge's WebSocket client is started by `activate()` which JLCEDA
calls only when the sch editor is the active view. In practice:
- **User-launched Edge** (port 9224, 9050): `activate()` is called
  when the sch tab is active. Bridge connects within ~2 seconds.
- **mcp-launched Edge** (port 9269, in `.browser-data/msedge`):
  `activate()` is **never** called because the sch editor never
  finishes init in that profile. Bridge does not connect.

For testing in mcp-launched Edge, you can verify `activate()` is
called by opening the home page (where `headerMenus.home` registers
a "局部网表" menu) and checking the page's console. The bridge code
runs regardless of which menu is active, so home-page activation
is enough to start the WS client.
