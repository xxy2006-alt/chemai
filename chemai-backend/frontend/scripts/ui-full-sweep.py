# ui-full-sweep.py — 教师端 8 页面完整巡检（回归验收证据）
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(f"PAGEERROR: {str(e)[:150]}"))

    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)

    pages = [
        ("/chat", "Agent 工作台", 4000),
        ("/class", "班级学情", 4000),
        ("/students", "学生管理", 4000),
        ("/exam", "出题工作台", 4000),
        ("/diagnosis", "诊断分析", 4000),
        ("/ocr", "答题卡识别", 3000),
        ("/ocr-sheets", "答题卡批改", 3000),
    ]
    results = []
    for path, name, wait in pages:
        pg.goto(BASE + "/#/" + path.lstrip("/"), wait_until="networkidle")
        pg.wait_for_timeout(wait)
        r = pg.evaluate(
            """(name) => {
              const main = document.querySelector('main');
              const text = main ? main.innerText : '';
              const hasError = /加载失败|出错了|undefined|Cannot read/.test(text);
              const imgs = [...document.querySelectorAll('main img')];
              const broken = imgs.filter(i => i.complete && i.naturalWidth === 0).length;
              return {
                page: name,
                titleOk: text.length > 40,
                hasErrorText: hasError,
                brokenImgs: broken,
                imgCount: imgs.length,
                textLen: text.length,
              };
            }""",
            name,
        )
        results.append(r)
        print(f"  {name}: 内容长度={r['textLen']} 破损图={r['brokenImgs']}/{r['imgCount']} 错误文案={r['hasErrorText']}")

    ok = all(not r['hasErrorText'] and r['brokenImgs'] == 0 and r['titleOk'] for r in results)
    print("全部页面正常:", ok)
    print("console/page 错误:", errs if errs else "无")
    b.close()
