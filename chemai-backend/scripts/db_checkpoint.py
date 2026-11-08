"""提交含 chemai.db 的改动前，先把 WAL 日志落盘。

用法:
    python scripts/db_checkpoint.py

为什么需要:
    服务运行中的写入停在 chemai.db-wal（WAL 模式），主文件要等 checkpoint
    才更新。此时 git 提交/切换分支抓到的主文件可能是旧状态（极端情况下
    看起来像空库），而 gitignore 的 -wal/-shm 不会被 git 带走——下次检出
    后主文件与残留 WAL 失配，打开即报 "database disk image is malformed"
    （2026-09-20 实际发生过）。

因此约定: 任何要提交 chemai.db 的场合，先跑本脚本；切分支/stash 前同理。
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "chemai.db"

conn = sqlite3.connect(DB)
try:
    busy, wal_pages, checkpointed = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    print(f"checkpoint 完成: busy={busy}, wal_pages={wal_pages}, 已写回={checkpointed}")
finally:
    conn.close()
