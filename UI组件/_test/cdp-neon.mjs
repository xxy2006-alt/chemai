/* 验证霓虹拖尾:渲染 + 消散 */
import { spawn } from 'child_process';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9234;
const URL = 'file:///D:/%E5%8C%96%E5%AD%A6/UI%E7%BB%84%E4%BB%B6/%E7%99%BB%E5%BD%95%E9%A1%B5%20v1.html';

const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu', '--remote-debugging-port=' + PORT,
  '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Temp\\dsh-cdp-profile12',
  '--window-size=1920,1080', '--force-device-scale-factor=1', URL
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  let wsUrl = null;
  for (let i = 0; i < 40; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:' + PORT + '/json')).json();
      const p = list.find(t => t.type === 'page');
      if (p) { wsUrl = p.webSocketDebuggerUrl; break; }
    } catch (e) {}
    await sleep(250);
  }
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pend = new Map();
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  };
  const send = (method, params = {}) => new Promise(r => {
    const i = ++id; pend.set(i, r);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  await new Promise(r => ws.onopen = r);
  await sleep(6000);
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return r.result?.result?.value;
  };
  const litPixels = () => ev("(() => { const c = document.getElementById('fx'); const d = c.getContext('2d'); const data = d.getImageData(600, 380, 620, 40).data; let lit = 0; for (let i = 3; i < data.length; i += 4) { if (data[i] > 10) lit++; } return lit; })()");

  for (let i = 0; i < 30; i++) {
    await ev("window.dispatchEvent(new PointerEvent('pointermove', { clientX: " + (600 + i * 20) + ", clientY: 400 }))");
    await sleep(16);
  }
  await sleep(120);
  console.log('trail pixels after move =', await litPixels());
  await sleep(3200);
  console.log('trail pixels after 3.4s idle =', await litPixels());

  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); chrome.kill(); process.exit(1); });
