/* 实测登录流程:任意数字 → 登录 → shimmer → 成功提示 */
import { spawn } from 'child_process';
import { writeFileSync } from 'fs';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9233;
const URL = 'file:///D:/%E5%8C%96%E5%AD%A6/UI%E7%BB%84%E4%BB%B6/%E7%99%BB%E5%BD%95%E9%A1%B5%20v1.html';

const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu', '--remote-debugging-port=' + PORT,
  '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Temp\\dsh-cdp-profile11',
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
  const issues = [];
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    else if (m.method === 'Runtime.exceptionThrown') {
      issues.push('EXCEPTION: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
    }
  };
  const send = (method, params = {}) => new Promise(r => {
    const i = ++id; pend.set(i, r);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  await new Promise(r => ws.onopen = r);
  await send('Runtime.enable');
  await sleep(6000);
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return r.result?.result?.value;
  };

  console.log('canvas exists =', await ev("!!document.getElementById('fx')"));
  console.log('form fadeInUp =', await ev("getComputedStyle(document.querySelector('.form-box')).animationName"));

  // 输入任意数字并提交
  await ev("document.querySelectorAll('.form-side input')[0].value = '123456'");
  await ev("document.querySelectorAll('.form-side input')[1].value = '888888'");
  await ev("document.querySelector('.login-btn').click()");
  await sleep(400);
  console.log('after click: shimmering =', await ev("document.querySelector('.login-btn').classList.contains('shimmering')"));
  console.log('button text =', await ev("document.querySelector('.login-btn').textContent"));

  const shot1 = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('D:\\化学\\UI组件\\_shots\\login-loading.png', Buffer.from(shot1.result.data, 'base64'));

  await sleep(2400);
  console.log('after 2.8s: shimmering =', await ev("document.querySelector('.login-btn').classList.contains('shimmering')"));
  console.log('message shown =', await ev("!!document.querySelector('.ant-message')"));
  console.log('message text =', await ev("document.querySelector('.ant-message')?.textContent"));

  // 粒子:模拟 pointermove
  await ev("window.dispatchEvent(new PointerEvent('pointermove', { clientX: 800, clientY: 400 }))");
  await sleep(200);
  console.log('particles after move =', await ev("(function(){ const c = document.getElementById('fx'); const d = c.getContext('2d'); const data = d.getImageData(780, 380, 40, 40).data; let lit = 0; for (let i = 3; i < data.length; i += 4) if (data[i] > 0) lit++; return lit > 0; })()"));

  const shot2 = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('D:\\化学\\UI组件\\_shots\\login-success.png', Buffer.from(shot2.result.data, 'base64'));

  console.log('issues:', issues.length ? issues.join('\n') : '无');
  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); chrome.kill(); process.exit(1); });
