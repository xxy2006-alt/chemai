"""
chemistry-improvement Metrics Collector
指标自动收集器
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import json
import logging

logger = logging.getLogger("chemistry-improvement")

# 存储目录
METRICS_ROOT = Path(__file__).parent / "metrics_data"
METRICS_ROOT.mkdir(exist_ok=True)


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self.metrics_dir = METRICS_ROOT

    def _get_metric_file(self, metric_type: str) -> Path:
        """获取指标文件路径"""
        return self.metrics_dir / f"{metric_type}.jsonl"

    async def record_metric(
        self,
        metric_type: str,
        entity_id: str,
        metric_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        记录单个指标

        Args:
            metric_type: 指标类型 (review/answer/learning/exam)
            entity_id: 关联实体ID
            metric_data: 指标数据

        Returns:
            记录结果
        """
        logger.info(f"记录指标: type={metric_type}, entity={entity_id}")

        record = {
            "metric_type": metric_type,
            "entity_id": entity_id,
            "data": metric_data,
            "recorded_at": datetime.now().isoformat()
        }

        # 追加到文件
        metric_file = self._get_metric_file(metric_type)
        with open(metric_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return {
            "success": True,
            "metric_id": f"{metric_type}_{entity_id}_{datetime.now().timestamp()}",
            "recorded_at": record["recorded_at"]
        }

    async def get_metrics(
        self,
        metric_type: str,
        time_window: str = "7d",
        entity_filter: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        获取指标数据

        Args:
            metric_type: 指标类型
            time_window: 时间窗口 (1d/7d/30d)
            entity_filter: 过滤条件

        Returns:
            指标数据和摘要
        """
        metric_file = self._get_metric_file(metric_type)
        if not metric_file.exists():
            return {"metrics": [], "summary": {}}

        # 解析时间窗口
        days = int(time_window.rstrip("d"))
        cutoff = datetime.now().timestamp() - (days * 86400)

        metrics = []
        with open(metric_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    record_time = datetime.fromisoformat(record["recorded_at"]).timestamp()
                    if record_time >= cutoff:
                        # 应用过滤
                        if entity_filter:
                            if not self._matches_filter(record, entity_filter):
                                continue
                        metrics.append(record)
                except json.JSONDecodeError:
                    continue

        # 计算摘要
        summary = self._calculate_summary(metric_type, metrics)

        return {
            "metrics": metrics,
            "summary": summary,
            "count": len(metrics),
            "time_window": time_window
        }

    def _matches_filter(self, record: Dict, filter_cond: Dict) -> bool:
        """检查记录是否匹配过滤条件"""
        for key, value in filter_cond.items():
            if key in record.get("data", {}) and record["data"][key] != value:
                return False
            if key in record and record[key] != value:
                return False
        return True

    def _calculate_summary(self, metric_type: str, metrics: List[Dict]) -> Dict:
        """计算指标摘要"""
        if not metrics:
            return {}

        if metric_type == "review":
            approved = sum(1 for m in metrics if m["data"].get("status") == "approved")
            return {
                "total": len(metrics),
                "approved": approved,
                "approval_rate": approved / len(metrics) if metrics else 0
            }
        elif metric_type == "learning":
            lifts = [m["data"].get("learning_lift", 0) for m in metrics]
            return {
                "total": len(metrics),
                "avg_learning_lift": sum(lifts) / len(lifts) if lifts else 0
            }
        else:
            return {"total": len(metrics)}

    # ===== 便捷方法 =====

    async def on_question_reviewed(
        self,
        question_id: str,
        action: str,
        rejection_reasons: List[str] = None,
        teacher_modifications: str = None,
        knowledge_points: List[str] = None,
        difficulty: str = None
    ) -> Dict[str, Any]:
        """题目审核完成事件"""
        metric_data = {
            "question_id": question_id,
            "status": action,
            "rejection_reasons": rejection_reasons or [],
            "teacher_modifications": teacher_modifications,
            "knowledge_points": knowledge_points or [],
            "difficulty": difficulty
        }
        return await self.record_metric("review", question_id, metric_data)

    async def on_question_used(
        self,
        question_id: str,
        practice_id: str,
        student_count: int,
        correct_count: int
    ) -> Dict[str, Any]:
        """题目被使用事件"""
        metric_data = {
            "practice_id": practice_id,
            "student_count": student_count,
            "correct_count": correct_count,
            "accuracy_rate": correct_count / student_count if student_count > 0 else 0
        }
        return await self.record_metric("answer", question_id, metric_data)

    async def on_practice_completed(
        self,
        practice_id: str,
        student_id: str,
        pre_score: float,
        post_score: float,
        knowledge_points: List[str]
    ) -> Dict[str, Any]:
        """练习完成事件"""
        metric_data = {
            "practice_id": practice_id,
            "student_id": student_id,
            "pre_score": pre_score,
            "post_score": post_score,
            "learning_lift": post_score - pre_score,
            "knowledge_points": knowledge_points
        }
        for kp in knowledge_points:
            await self.record_metric("learning", f"{student_id}_{kp}", metric_data)
        return {"success": True}

    async def on_exam_completed(
        self,
        exam_record_id: str,
        class_avg_score: float,
        question_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """考试完成事件"""
        metric_data = {
            "exam_record_id": exam_record_id,
            "class_avg_score": class_avg_score,
            "question_scores": question_scores
        }
        return await self.record_metric("exam", exam_record_id, metric_data)
