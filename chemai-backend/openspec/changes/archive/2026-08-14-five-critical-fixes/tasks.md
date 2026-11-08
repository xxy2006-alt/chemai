## 1. 家长登录 token

- [x] 1.1 `app/api/parent.py` login_parent — 调 `create_access_token()` 生成 JWT, 返回 token + refresh_token
- [x] 1.2 `app/main.py` PUBLIC_PREFIXES — 追加 `"/api/parent/"`
- [x] 1.3 验证: lijg/123456 登录 → 获取 token → 家长 Dashboard 正常加载

## 2. Agent 找学生

- [x] 2.1 `agent/tools/diagnosis.py` show_students — 加 `student_name` 参数 + LIKE 模糊搜索
- [x] 2.2 验证: Agent Chat "找下李雨萱" → 返回学生卡片
- [x] 2.3 评测: `python -m pytest evals/test_unit_tools.py -q` 无回归

## 3. 学习计划链

- [x] 3.1 `app/api/diagnosis.py` GET /learning-plan/{sid} — 加 SqliteStore 读取 (cache → store → LLM)
- [x] 3.2 `app/api/diagnosis.py` POST /apply/{sid} — 改同步 await store.aput
- [x] 3.3 验证: 教师发送计划 → 重启服务器 → 学生端刷新可看到

## 4. 学生数据随机化

- [x] 4.1 新建 `tools/randomize_students.py` — 随机障碍 + 练习数 + 答题记录
- [x] 4.2 运行脚本生成差异化数据
- [x] 4.3 验证: 抽查 5 个学生, barrier 分布各不相同

## 5. 学生设置面板

- [x] 5.1 `frontend/m/report.html` — 替换 alert 为设置面板(改密码/绑定码/信息/关于)
- [x] 5.2 改密码对接 `POST /api/auth/change-password`
- [x] 5.3 验证: 学生端"我的"→ 设置 → 各功能正常

## 6. 回归验证

- [x] 6.1 评测: `python -m pytest evals/ -q` 全量无回归
- [x] 6.2 打包: 三端 exe 重建
