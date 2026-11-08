# P1-1 start.bat 删除数据库修复确认

## 修复日期
2026-04-25

## 问题描述
`start.bat:13` 每次启动执行 `del chemai.db 2>nul` 无条件删除数据库，导致所有配置和数据在重启后丢失。

## 修改内容

**文件：** `start.bat`

**修改前：**
```bat
echo 2. Removing old database...
del chemai.db 2>nul
echo Database reset.
```

**修改后：**
```bat
echo 2. Database check...
set /p RESET="Reset database? (y/N): "
if /i "%RESET%"=="y" (
    del chemai.db 2>nul
    echo Database reset.
) else (
    echo Keeping existing database.
)
```

### 逻辑说明
- 启动时交互式询问是否重置数据库，默认 `N`（不重置）
- 输入 `y` 或 `Y` 才执行删除
- 保留了重置能力，但不会无提示地丢失数据

## 验证方式
1. 运行 `start.bat` → 提示 `Reset database? (y/N):`
2. 直接回车 → 保留数据库，正常启动
3. 输入 `y` → 删除数据库后启动（完全重置）
