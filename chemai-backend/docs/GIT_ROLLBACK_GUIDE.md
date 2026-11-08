# ChemAI Git 回滚指南

## 快速回滚

### 方法1: 使用回滚脚本

```bash
# 查看所有版本
../scripts/git_rollback.sh

# 回滚到v1.0.0
../scripts/git_rollback.sh v1.0.0

# 回滚到最新提交
../scripts/git_rollback.sh --latest
```

### 方法2: 手动Git命令

```bash
# 查看版本历史
git log --oneline

# 回滚到指定版本
git reset --hard <commit-hash>

# 回滚到v1.0.0
git reset --hard v1.0.0

# 回滚到上一个版本
git reset --hard HEAD~1
```

---

## 版本列表

| 版本 | 日期 | 说明 | 状态 |
|------|------|------|------|
| v1.0.0 | 2026-04-23 | 初始版本 - 学校初始化数据完成 | 当前最新 |

---

## 回滚场景

### 场景1: 发现新功能有严重bug

```bash
# 立即回滚到v1.0.0
git reset --hard v1.0.0

# 验证回滚
git log --oneline -3
```

### 场景2: 需要临时切换到旧版本查看问题

```bash
# 创建临时分支基于v1.0.0
git checkout -b temp-branch v1.0.0

# 在临时分支上工作...

# 完成后切换回主分支
git checkout master

# 删除临时分支
git branch -d temp-branch
```

### 场景3: 需要保留当前更改但先回到旧版本

```bash
# 先提交当前更改
git add -A
git commit -m "WIP: 临时保存"

# 创建备份分支
git branch backup-before-rollback

# 回滚
git reset --hard v1.0.0
```

---

## 注意事项

### 1. 回滚会丢失未提交的更改
```bash
# 警告: 回滚前确保所有更改已提交
git status  # 检查是否有未提交的更改
```

### 2. 已推送的代码回滚需要强制推送
```bash
git reset --hard v1.0.0
git push --force origin master
```

### 3. 多人协作时谨慎回滚
```bash
# 通知团队成员后再回滚
git push --force origin master
```

---

## 版本提交规范

每次重要更新后，执行以下命令创建新版本：

```bash
# 1. 提交代码
git add -A
git commit -m "描述本次更改"

# 2. 创建版本标签
git tag -a v1.1.0 -m "v1.1.0: 新增xxx功能"

# 3. 推送代码和标签
git push origin master
git push origin v1.1.0
```

---

## 回滚验证

回滚后运行以下命令验证：

```bash
# 1. 确认代码版本
git log --oneline -3

# 2. 确认数据库状态（可选，重置数据库）
python -m app.utils.init_db

# 3. 启动服务测试
python -m uvicorn app.main:app --reload
```

---

*最后更新: 2026-04-23*
