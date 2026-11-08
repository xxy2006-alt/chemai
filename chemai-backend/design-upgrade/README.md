# design-upgrade · 三端视觉升级参考资料

> 目的：解决现有界面"过于普通"的问题。从 [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)（MIT）下载的 DESIGN.md 分析文件，作为三端升级的设计灵感源。
> ⚠️ 按[上游声明](https://github.com/VoltAgent/awesome-claude-design#license--disclaimer)：这些是"受公开设计模式启发的起点"，只作灵感融合进 ChemAI 自有系统，**不做 1:1 品牌克隆**。

## 文件与端的对应关系

| 端 | 本文件 | 备选（同目录 `备选/`） | 适配理由 |
|----|--------|--------|----------|
| 教师 Web 端（9 页 React） | `教师端-Linear.md` | `教师端-Stripe.md` | 数据密集工作台（KPI/表格/抽屉/AI 面板）需要精密层级感 |
| 学生移动端（6 页 H5） | `学生端-Spotify.md` | `学生端-Zapier.md` | 初高中生要"酷"与动力感；深色+高饱和强调+胶囊按钮，移动原生 |
| 家长移动端（2 页 H5） | `家长端-Wise.md` | `备选/家长端-Mastercard.md` | 报告与消息需要信任感与信息清晰度；亮绿方向与现有米白+墨绿底子相顺 |

## 关键事实（读文件前必知）

- **Linear 文件是深色系**：canvas `#010102` + 薰衣草蓝 `#5e6ad2`；其 YAML 内含 `inverse-*` 浅色 token（`#ffffff` / `#f5f6f6`），可推导浅色变体。教师端用深色还是浅色 → 待产品决策。
- **Spotify**：近黑 `#121212`~`#1f1f1f` + 绿 `#1ed760`，胶囊按钮 500px+ 圆角，粗字重 + 大写字距标签。
- **Wise**：亮绿 `#9fe870` + 白画布 + 绿调浅灰面，超重 display 无衬线（900 字重），北欧金融杂志感。

## 品牌锚点（升级时 MUST 保留，源自 chemai-backend/DESIGN.md）

1. **Oxford Blue `#002147`** —— 系统主色（教师端侧边栏/主按钮）
2. **Teal `#0d7377` = AI 的声音**（R-C2）—— 三端通用，AI 气泡/AI 按钮/AI 内容标记专属
3. **JetBrains Mono**（R-T1）—— 化学式/方程式/数据等宽，三端强制
4. 移动端 430×900 视口、KaTeX+mhchem 化学式渲染（R-H1/H2）、三态覆盖（R-S1/S2）

## 决议日志

- **2026-09-14 晚（v2.1）**：用户验收否决「深色 AI 嵌板 + Oxford Blue 实底侧边栏」，教师工作台恢复 main-bg/nav-bg 品牌底图 + 玻璃拟态卡片；主操作按钮启用品牌渐变（学术青→靛蓝，GAP-02 复活）；R-T-L1/L2 随之修订。

- **2026-09-14 晚**：登录页「深色时刻」经用户验收否决，恢复品牌插画背景 `login-bg.webp`（备选两张自绘 SVG 存于 assets/backgrounds，LoginPage 内 LOGIN_BG 一行切换）；R-T-F1 随之修订。

- **2026-09-14**：三端融合提案定案（教师端侧边栏保持 Oxford Blue 实底；登录页允许深色 moment；学生端提交按钮 = 亮青实底 A 案；游戏化首期做；家长端主 CTA = Wise 亮绿；AI 助教入口保留）。提案已升格为 `../design/` 三端分册，总册 `../DESIGN.md` 重写为 v2（三端分册制）；v1 单册版归档于 `归档/DESIGN-v1-学术催化剂-单册版.md`。移动端并入 SPA 的架构决策见 `../docs/adr/0017-mobile-into-react-spa.md`。
- **2026-09-14**：`docs/DESIGN.md`（36号"暖纸拟物"旧代规格，已被方向 A 取代）归档为 `../../docs/archive/DESIGN-v0-暖纸拟物-已废弃.md`。

## 用法（v2 时代）

1. 改界面代码前：读总册 `../DESIGN.md`（v2）+ 目标端分册 `../design/教师端|学生端|家长端.md`。
2. 本目录现在是**升级过程档案**：灵感源（各品牌分析文件）、备选方案（`备选/`）、融合提案与定案记录（`提案-*.md`）、历代归档（`归档/`）。
3. 灵感源文件仅作出处考证，NEVER 直接引用其色值——一切以总册+分册为准。
