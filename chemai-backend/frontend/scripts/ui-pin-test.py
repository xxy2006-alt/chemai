# ui-pin-test.py — 验证：①导航改名 ②输入框钉底 ③切换对话不回跳
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    # 登录
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)

    # 1. 导航标签
    nav = pg.evaluate("() => [...document.querySelectorAll('nav button')].map(b => b.textContent.trim())")
    print("1. 导航项:", nav)

    # 2. 布局结构：main 不应滚动，消息区应内部滚动
    layout = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const msgList = document.querySelector('.chat-list, main > div > div:nth-child(2)');
          return { mainOverflow: main ? getComputedStyle(main).overflowY : null,
                   mainScrollH: main ? main.scrollHeight : 0,
                   mainClientH: main ? main.clientHeight : 0 };
        }"""
    )
    print("2. main 布局:", layout)

    # 3. 发送一条真实消息（后端 + Agent 流式）
    pg.fill("textarea", "请用一句话介绍你自己")
    pg.click("button:has-text('发送')")
    pg.wait_for_timeout(18000)  # 等流式回复
    msgs = pg.evaluate("() => document.querySelectorAll('.msg-ai, [class*=msg]').length")
    print("3. 消息数:", msgs)

    # 4. 输入框钉底：滚动消息区后输入框仍在视口底部
    pinned = pg.evaluate(
        """() => {
          const list = document.querySelector('main .overflow-y-auto');
          const inputBar = document.querySelector('main textarea')?.closest('.border-t');
          if (!list || !inputBar) return { err: 'not found' };
          list.scrollTop = list.scrollHeight;          // 滚到底
          const r1 = inputBar.getBoundingClientRect();
          list.scrollTop = 0;                          // 滚到顶
          const r2 = inputBar.getBoundingClientRect();
          return {
            inputBottomAtScrollBottom: Math.round(r1.bottom),
            viewportH: window.innerHeight,
            inputBottomAtScrollTop: Math.round(r2.bottom),
            listScrollable: list.scrollHeight > list.clientHeight,
            listScrollH: list.scrollHeight, listClientH: list.clientHeight,
          };
        }"""
    )
    print("4. 钉底检测:", pinned)

    # 5. 切换对话：新建一个对话再切回，验证输入框位置不变
    before = pg.evaluate("() => { const t = document.querySelector('main textarea'); return t.getBoundingClientRect().top }")
    pg.click("button:has-text('新建对话')")
    pg.wait_for_timeout(1200)
    after = pg.evaluate("() => { const t = document.querySelector('main textarea'); return t.getBoundingClientRect().top }")
    print("5. 切换对话输入框 top:", round(before), "->", round(after))

    pg.screenshot(path="docs/ui-review/11-agent-workbench-pinned.png")

    non502 = [e for e in errs if "502" not in e]
    print("console errors(非502):", non502[:5])
    b.close()
