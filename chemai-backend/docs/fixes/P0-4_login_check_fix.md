# P0-4 前端页面登录校验修复确认

## 修复日期
2026-04-25

## 问题描述
直接访问 `teacher_v2.html`、`student_v2.html`、`parent_portal.html` 时未做登录校验，页面尝试渲染需要用户数据的内容，导致抛出异常显示空白页面。

## 修改内容

### 三个 HTML 文件
均添加了登录校验脚本（在 `<title>` 标签之后、`<head>` 内最前面）：

**文件列表：**
- `frontend/teacher_v2.html`
- `frontend/student_v2.html`
- `frontend/parent_portal.html`

**添加的代码：**
```html
<!-- 登录校验 -->
<script>
(function() {
    try {
        if (!sessionStorage.getItem('chemai_user')) {
            window.location.href = '/login.html';
        }
    } catch(e) {
        window.location.href = '/login.html';
    }
})();
</script>
```

### 逻辑说明
- 使用 IIFE 立即执行函数，在页面渲染前检查登录状态
- `try/catch` 包裹防止 `sessionStorage` 不可用时报错
- 未登录时直接 `window.location.href` 跳转，终止后续渲染

## 验证方式
1. 清除浏览器 sessionStorage → 直接访问 `http://localhost:8001/teacher_v2.html` → 自动跳转 `/login.html`
2. 正常登录后访问上述页面 → 正常渲染内容
