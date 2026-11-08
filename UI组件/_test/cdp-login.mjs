/* 验证登录页 v1 渲染 */
import { spawn } from 'child_process';
import { writeFileSync } from 'fs';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9230;
const URL = 'file:///D:/%E5%8C%96%E5%AD%A6/UI%E7%BB%84%E4%BB%B6/%E7%99%BB%E5%BD%95%E9%A1%B5%20v1.html';

const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu', '--remote-debugging-port=' + PORT,
  '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Temp\\dsh-cdp-profile8',
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
    else if (m.method === 'Runtime.consoleAPICalled') {
      issues.push('CONSOLE: ' + m.params.args.map(a => a.value ?? a.description ?? '').join(' '));
    }
  };
  const send = (method, params = {}) => new Promise(r => {
    const i = ++id; pend.set(i, r);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  await new Promise(r => ws.onopen = r);
  await send('Runtime.enable');
  await sleep(6000); // 等 CDN

  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return r.result?.result?.value;
  };

  console.log('window.antd =', await ev("!!window.antd"));
  console.log('React =', await ev("!!window.React"));
  console.log('root children =', await ev("document.getElementById('root').children.length"));
  console.log('brand h1 =', await ev("document.querySelector('.brand h1')?.textContent"));
  console.log('form inputs =', await ev("document.querySelectorAll('.form-side input').length"));
  console.log('login button =', await ev("document.querySelector('.login-btn')?.textContent"));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('D:\\化学\\UI组件\\_shots\\login-v1.png', Buffer.from(shot.result.data, 'base64'));
  console.log('screenshot saved');

  console.log('issues:', issues.length ? issues.join('\n') : '无');

  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); chrome.kill(); process.exit(1); });
