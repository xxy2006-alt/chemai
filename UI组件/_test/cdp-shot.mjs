/* CDP 截图:打开 drawer / bottom sheet 后截图验证 */
import { spawn } from 'child_process';
import { writeFileSync } from 'fs';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9224;
const URL = 'file:///D:/%E5%8C%96%E5%AD%A6/UI%E7%BB%84%E4%BB%B6/UI%E7%BB%84%E4%BB%B6.html#slide-3';

const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu',
  '--remote-debugging-port=' + PORT,
  '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Temp\\dsh-cdp-profile2',
  '--window-size=1920,1080', '--force-device-scale-factor=1',
  URL
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  let wsUrl = null;
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch('http://127.0.0.1:' + PORT + '/json');
      const list = await res.json();
      const page = list.find(t => t.type === 'page');
      if (page) { wsUrl = page.webSocketDebuggerUrl; break; }
    } catch (e) {}
    await sleep(250);
  }
  if (!wsUrl) { console.log('NO CDP'); process.exit(1); }

  const ws = new WebSocket(wsUrl);
  let msgId = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  };
  const send = (method, params = {}) => new Promise(res => {
    const id = ++msgId;
    pending.set(id, res);
    ws.send(JSON.stringify({ id, method, params }));
  });
  await new Promise(r => ws.onopen = r);
  await send('Runtime.enable');
  await sleep(2500);

  const ev = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return r.result?.result?.value;
  };
  const shot = async (file) => {
    const r = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync('D:\\化学\\UI组件\\_shots\\' + file, Buffer.from(r.result.data, 'base64'));
    console.log('saved', file);
  };

  await ev("document.getElementById('btnDrawer').click()");
  await sleep(700);
  await shot('drawer-open.png');

  await ev("document.getElementById('drawerMask').classList.remove('show')");
  await sleep(500);
  await ev("document.getElementById('btnSheet').click()");
  await sleep(700);
  await shot('sheet-open.png');

  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); chrome.kill(); process.exit(1); });
