"""
学情预警检查任务
定时检查学生学情异常
"""

from app.services.early_warning import check_all_warnings


def check_warnings_job():
    """
    定时检查所有学生的预警情况
    """
    try:
        warnings = check_all_warnings()
        print(f"[预警检查] 已检查完成，创建 {len(warnings)} 条预警")
    except Exception as e:
        print(f"[预警检查] 任务执行失败: {e}")
