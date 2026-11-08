"""调度器兜底消费（ADR-0013）：注册进去的主观题扫描作业必须真的能跑。

零参直调 scan_semantic_pending 会撞上必填的 db 会话，每轮抛 TypeError —— 作业静默
失败，无 Redis 部署下 PENDING 行永远不被消费。这里断言的是注册进调度器的可调用对象
零参可调用，且落到自开会话的作业入口。
"""
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def test_semantic_scan_job_is_invocable(monkeypatch):
    from app import scheduler as sched_mod

    jobs = {}
    monkeypatch.setattr(AsyncIOScheduler, "add_job",
                        lambda self, fn, *a, **kw: jobs.__setitem__(kw.get("id"), fn))
    monkeypatch.setattr(AsyncIOScheduler, "start", lambda self: None)

    calls = []

    def fake_scan(exam_record_id=None):
        calls.append(exam_record_id)
        return {"scanned": 0, "judged": 0}

    monkeypatch.setattr("app.jobs.handlers.handle_semantic_scan", fake_scan)
    sched_mod.init_scheduler(None)

    assert "semantic_scan" in jobs
    asyncio.run(jobs["semantic_scan"]())     # 零参调用必须跑通（作业入口自开会话）
    assert calls == [None]
