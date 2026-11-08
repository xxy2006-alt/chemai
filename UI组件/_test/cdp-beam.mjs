/* 连续截图验证光束边框旋转 */
import { spawn } from 'child_process';
import { writeFileSync } from 'fs';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9232;
const URL = 'file:///D:/%E5%8C%96%E5%AD%A6/UI%E7%BB%84%E4%BB%B6/%E7%99%BB%E5%BD%95%E9%A1%B5%20v1.html';

const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu', '--remote-debugging-port=' + PORT,
  '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Temp\\dsh-cdp-profile10',
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

  // 检查动画与渐变配置
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return r.result?.result?.value;
  };
  console.log('animation-name =', await ev("getComputedStyle(document.querySelector('.beam-card'), '::before').animationName"));
  console.log('bg has conic =', await ev("getComputedStyle(document.querySelector('.beam-card'), '::before').backgroundImage.includes('conic')"));

  // 连续截图找淡蓝光束
  let blueShots = 0;
  for (let i = 0; i < 12; i++) {
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(`D:\\化学\\UI组件\\_shots\\beam-${i}.png`, Buffer.from(shot.result.data, 'base64'));
    await sleep(350);
  }
  // 在 Node 里直接分析 PNG 太麻烦,让 PowerShell 分析
  console.log('12 shots saved, blueShots will be counted by pwsh');
  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); chrome.kill(); process.exit(1); });
