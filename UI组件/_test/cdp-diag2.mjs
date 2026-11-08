/* 诊断 loading 状态卡片布局 */
import { spawn } from 'child_process';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9229;
const URL = 'file:///D:/%E5%8C%96%E5%AD%A6/UI%E7%BB%84%E4%BB%B6/UI%E7%BB%84%E4%BB%B6.html#slide-7';

const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu', '--remote-debugging-port=' + PORT,
  '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Temp\\dsh-cdp-profile7',
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
  await sleep(3000);
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return r.result?.result?.value;
  };

  console.log('active =', await ev("document.querySelector('deck-stage > section.active')?.id"));
  console.log('card1 rect =', JSON.stringify(await ev("(() => { const r = document.querySelector('#s-load-skel .card').getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; })()")));
  console.log('skelDemo rect =', JSON.stringify(await ev("(() => { const r = document.getElementById('skelDemo01').getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; })()")));
  console.log('loading opacity =', await ev("getComputedStyle(document.querySelector('#skelDemo01 .skel-loading')).opacity"));
  console.log('skelDemo done =', await ev("document.getElementById('skelDemo01').classList.contains('done')"));
  console.log('card computed bg =', await ev("getComputedStyle(document.querySelector('#s-load-skel .card')).backgroundColor"));

  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); chrome.kill(); process.exit(1); });
