/* CDP 交互测试:真实模拟点击,验证 drawer / bottom sheet / modal */
import { spawn } from 'child_process';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9223;
const URL = 'file:///D:/%E5%8C%96%E5%AD%A6/UI%E7%BB%84%E4%BB%B6/UI%E7%BB%84%E4%BB%B6.html#slide-3';

const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu',
  '--remote-debugging-port=' + PORT,
  '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Temp\\dsh-cdp-profile',
  '--window-size=1920,1080',
  URL
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  // 等 CDP endpoint
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
  if (!wsUrl) { console.log('NO CDP ENDPOINT'); process.exit(1); }

  const ws = new WebSocket(wsUrl);
  let msgId = 0;
  const pending = new Map();
  const issues = [];

  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method === 'Runtime.exceptionThrown') {
      issues.push('EXCEPTION: ' + (msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text));
    }
    else if (msg.method === 'Runtime.consoleAPICalled') {
      issues.push('CONSOLE: ' + msg.params.args.map(a => a.value ?? a.description ?? '').join(' '));
    }
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
    if (r.result?.exceptionDetails) {
      issues.push('EVAL ERROR: ' + r.result.exceptionDetails.text);
      return null;
    }
    return r.result?.result?.value;
  };

  console.log('--- 页面状态 ---');
  console.log('btnModal:', await ev("!!document.getElementById('btnModal')"));
  console.log('btnDrawer:', await ev("!!document.getElementById('btnDrawer')"));
  console.log('btnSheet:', await ev("!!document.getElementById('btnSheet')"));

  console.log('\n--- 点击 Modal ---');
  await ev("document.getElementById('btnModal').click()");
  await sleep(500);
  console.log('modalMask.show =', await ev("document.getElementById('modalMask').classList.contains('show')"));
  console.log('modal-box opacity =', await ev("getComputedStyle(document.querySelector('#modalMask .modal-box')).opacity"));

  console.log('\n--- 点击 Drawer ---');
  await ev("document.getElementById('drawerMask').classList.remove('show')");
  await ev("document.getElementById('modalMask').classList.remove('show')");
  await ev("document.getElementById('btnDrawer').click()");
  await sleep(500);
  console.log('drawerMask.show =', await ev("document.getElementById('drawerMask').classList.contains('show')"));
  console.log('drawer transform =', await ev("getComputedStyle(document.querySelector('#drawerMask .drawer')).transform"));
  console.log('drawer rect.right =', await ev("document.querySelector('#drawerMask .drawer').getBoundingClientRect().right"));

  console.log('\n--- 点击 Bottom Sheet ---');
  await ev("document.getElementById('drawerMask').classList.remove('show')");
  await ev("document.getElementById('btnSheet').click()");
  await sleep(500);
  console.log('sheetMask.show =', await ev("document.getElementById('sheetMask').classList.contains('show')"));
  console.log('sheet rect.bottom =', await ev("document.querySelector('#sheetMask .sheet').getBoundingClientRect().bottom"));
  console.log('sheet rect.top =', await ev("document.querySelector('#sheetMask .sheet').getBoundingClientRect().top"));

  console.log('\n--- 遮罩点击关闭 ---');
  await ev("document.getElementById('sheetMask').dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 100, clientY: 100 }))");
  await sleep(300);
  console.log('sheetMask.show after mask click =', await ev("document.getElementById('sheetMask').classList.contains('show')"));

  console.log('\n--- 问题记录 ---');
  console.log(issues.length ? issues.join('\n') : '无 JS 异常/报错');

  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); chrome.kill(); process.exit(1); });
