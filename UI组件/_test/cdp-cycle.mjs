/* 验证 skeleton/shimmer 循环:done/idle class 定时切换 */
import { spawn } from 'child_process';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9226;
const URL = 'file:///D:/%E5%8C%96%E5%AD%A6/UI%E7%BB%84%E4%BB%B6/UI%E7%BB%84%E4%BB%B6.html#slide-7';

const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu', '--remote-debugging-port=' + PORT,
  '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Temp\\dsh-cdp-profile4',
  '--window-size=1920,1080', URL
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
  await sleep(2500);
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return r.result?.result?.value;
  };

  const state = async () => ({
    t: Math.round(performance.now() / 100) / 10,
    skelDone: await ev("document.getElementById('skelDemo01').classList.contains('done')"),
    skelContentOp: await ev("getComputedStyle(document.querySelector('#skelDemo01 .skel-content')).opacity"),
    shimIdle: await ev("document.getElementById('shimDemo01').classList.contains('idle')")
  });

  console.log('t0', JSON.stringify(await state()));
  await sleep(1500);
  console.log('t1.5s', JSON.stringify(await state()));
  await sleep(1500);
  console.log('t3.0s', JSON.stringify(await state()));
  await sleep(1500);
  console.log('t4.5s', JSON.stringify(await state()));
  await sleep(1500);
  console.log('t6.0s', JSON.stringify(await state()));

  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); chrome.kill(); process.exit(1); });
