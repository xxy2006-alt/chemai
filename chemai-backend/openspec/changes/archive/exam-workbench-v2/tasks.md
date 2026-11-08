# Tasks: exam-workbench-v2

## T1: 新页面骨架 — 左右分栏

- [x] 1.1 左侧配置栏: 知识点chips + 难度select + 题型chips + 数量input + [AI出题]按钮
- [x] 1.2 右侧题目画布: v-for卡片列表 + 空状态 + 来源切换tab
- [x] 1.3 底部操作栏: 全部保存/全部删除+确认/全部重出 + 统计计数
- [x] 1.4 Vue 3 CDN + common.css 引入

## T2: 题目卡片

- [x] 2.1 状态: _saved=true→绿色左边框+'已保存', false→蓝色+'待保存'
- [x] 2.2 内容: renderChemistry() + options + tags + 四维审核badge
- [x] 2.3 [保存] → 未选文件夹提示 → API → toast → 状态变更
- [x] 2.4 [移除] → _removed=true + opacity:0 → 卡片消失
- [x] 2.5 [编辑] → inline展开编辑区 (textarea+input, 完成/取消)

## T3: 三个题目来源

- [x] 3.1 AI生成: 左侧配置驱动, 按题型分批生成, 追加到画布
- [x] 3.2 手动录入: inline表单 (题目/选项/答案/知识点/难度) → [添加到画布]
- [x] 3.3 从题库选择: 搜索框 + 列表checkbox多选 + [加入画布]

## T4: 考试管理入口

- [x] 4.1 顶部 "考试列表" / "出题工作台" 视图切换
- [x] 4.2 创建考试 + 列表 + 预览 + 发布 + 删除

## T5: 旧文件处理

- [x] 5.1 exam.html → exam-v1.bak.html
- [x] 5.2 exam.js → exam-v1.bak.js
- [x] 5.3 app.js 侧边栏 href → /pages/exam-v2.html
- [x] 5.4 main.py 路由兼容（/{page} 通配已处理）

## T6: 验证

- [x] 6.1-6.5 页面加载正常, Vue挂载成功, 0 JS errors, 所有组件就位
