"""
Audit Logger — JSONL audit trail for skill execution.
"""
import json
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

SENSITIVE_FIELDS = {"password", "phone", "parent_phone", "token", "api_key", "secret"}


@dataclass
class AuditEntry:
    timestamp: str = ""
    persona: str = ""
    skill_name: str = ""
    args: dict = field(default_factory=dict)
    result_summary: str = ""
    duration_ms: float = 0
    error: Optional[str] = None


class AuditLogger:
    # 默认锚定后端根目录（audit.py 位于 agent/ 下），与启动 cwd 无关
    _DEFAULT_LOG_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "audit", "agent_audit.jsonl"
    )

    def __init__(self, log_path: str = _DEFAULT_LOG_PATH, ring_size: int = 100):
        self._log_path = log_path
        self._ring = deque(maxlen=ring_size)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, entry: AuditEntry):
        """Write audit entry to JSONL file and ring buffer."""
        entry.timestamp = datetime.now(timezone.utc).isoformat()
        self._ring.append(entry)
        try:
            line = json.dumps({
                "timestamp": entry.timestamp,
                "persona": entry.persona,
                "skill_name": entry.skill_name,
                "args": self._sanitize(entry.args),
                "result_summary": entry.result_summary[:200],
                "duration_ms": entry.duration_ms,
                "error": entry.error,
            }, ensure_ascii=False)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass  # audit failure should never break execution

    def recent(self, n: int = 20) -> list[AuditEntry]:
        return list(self._ring)[-n:]

    def _sanitize(self, args: dict) -> dict:
        """Replace sensitive field values with ***."""
        return {k: "***" if k in SENSITIVE_FIELDS else v for k, v in args.items()}


# Global singleton
audit_logger = AuditLogger()
