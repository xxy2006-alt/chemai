"""
chemistry-improvement Analysis Engine
自改进分析引擎
"""
from typing import Dict, List
from pathlib import Path
import json
import logging

from .models import LearningInsight, AnalysisResult

logger = logging.getLogger("chemistry-improvement")

# 存储目录
METRICS_ROOT = Path(__file__).parent / "metrics_data"
INSIGHTS_DIR = METRICS_ROOT / "insights"
INSIGHTS_DIR.mkdir(exist_ok=True, parents=True)


class AnalysisEngine:
    """分析引擎"""

    def __init__(self, metrics_collector=None):
        self.metrics = metrics_collector
        self.insights_dir = INSIGHTS_DIR

        # 分析阈值配置
        self.thresholds = {
            "min_sample_size": 10,
            "approval_rate_warning": 0.70,
            "approval_rate_target": 0.85,
            "learning_lift_min": 5.0,
            "difficulty_deviation_max": 0.15,
        }

    async def analyze(
        self,
        analysis_type: str,
        time_window_days: int = 7,
        force_refresh: bool = False
    ) -> AnalysisResult:
        """
        执行分析

        Args:
            analysis_type: 分析类型 (review_feedback/learning_effect/difficulty_calibration/all)
            time_window_days: 时间窗口（天）
            force_refresh: 强制刷新

        Returns:
            分析结果
        """
        logger.info(f"执行分析: type={analysis_type}, window={time_window_days}天")

        if analysis_type == "review_feedback":
            return await self._analyze_review_feedback(time_window_days)
        elif analysis_type == "learning_effect":
            return await self._analyze_learning_effect(time_window_days)
        elif analysis_type == "difficulty_calibration":
            return await self._analyze_difficulty_calibration(time_window_days)
        elif analysis_type == "all":
            results = []
            results.append(await self._analyze_review_feedback(time_window_days))
            results.append(await self._analyze_learning_effect(time_window_days))
            results.append(await self._analyze_difficulty_calibration(time_window_days))
            return self._merge_results(results)
        else:
            return AnalysisResult(
                analysis_type=analysis_type,
                insights=[],
                metrics_summary={"error": "Unknown analysis type"},
                recommended_actions=[]
            )

    async def _analyze_review_feedback(self, days: int) -> AnalysisResult:
        """分析审核反馈"""
        metrics_data = await self._load_metrics("review", days)

        if len(metrics_data) < self.thresholds["min_sample_size"]:
            return AnalysisResult(
                analysis_type="review_feedback",
                insights=[],
                metrics_summary={"insufficient_data": True, "sample_size": len(metrics_data)},
                recommended_actions=["数据不足，建议收集更多样本"]
            )

        # 统计拒绝原因分布
        rejection_distribution = self._calculate_rejection_distribution(metrics_data)

        # 按知识点分组分析
        kp_analysis = await self._analyze_by_knowledge_point(metrics_data)

        # 生成洞察
        insights = []

        # 洞察1: 高频拒绝原因
        if rejection_distribution:
            top_rejection = max(rejection_distribution.items(), key=lambda x: x[1])
            percentage = top_rejection[1] / len(metrics_data)
            if percentage > 0.3:
                insights.append(LearningInsight(
                    insight_id=f"insight_rejection_{top_rejection[0]}",
                    category="rejection_pattern",
                    title=f"高频拒绝原因: {top_rejection[0]}",
                    description=f"最近{top_rejection[1]}道题目因此原因被拒绝，占比{percentage*100:.1f}%",
                    evidence={"count": top_rejection[1], "percentage": percentage},
                    confidence=0.85,
                    recommended_action=f"需要在 Prompt 中强调检查{top_rejection[0]}相关问题"
                ))

        # 洞察2: 某知识点题目通过率低
        for kp, stats in kp_analysis.items():
            if "approval_rate" in stats and stats["approval_rate"] < self.thresholds["approval_rate_warning"]:
                insights.append(LearningInsight(
                    insight_id=f"insight_kp_{kp}",
                    category="knowledge_point",
                    title=f"知识点「{kp}」出题质量需改进",
                    description=f"该知识点题目通过率仅{stats['approval_rate']*100:.1f}%，低于目标",
                    evidence=stats,
                    confidence=0.80,
                    recommended_action=f"生成{kp}相关题目时需要更严格的审核标准"
                ))

        # 计算整体通过率
        approved = sum(1 for m in metrics_data if m["data"].get("status") == "approved")
        approval_rate = approved / len(metrics_data)

        return AnalysisResult(
            analysis_type="review_feedback",
            insights=insights,
            metrics_summary={
                "total_reviews": len(metrics_data),
                "approval_rate": approval_rate,
                "rejection_distribution": rejection_distribution,
            },
            recommended_actions=[i.recommended_action for i in insights]
        )

    async def _analyze_learning_effect(self, days: int) -> AnalysisResult:
        """分析学习效果"""
        metrics_data = await self._load_metrics("learning", days)

        if len(metrics_data) < self.thresholds["min_sample_size"]:
            return AnalysisResult(
                analysis_type="learning_effect",
                insights=[],
                metrics_summary={"insufficient_data": True, "sample_size": len(metrics_data)},
                recommended_actions=[]
            )

        # 计算平均提升度
        lifts = [m["data"].get("learning_lift", 0) for m in metrics_data]
        avg_lift = sum(lifts) / len(lifts) if lifts else 0

        insights = []

        if avg_lift < self.thresholds["learning_lift_min"]:
            insights.append(LearningInsight(
                insight_id="insight_learning_lift_low",
                category="learning_effectiveness",
                title="整体学习效果不佳",
                description=f"平均提升度仅{avg_lift:.1f}%，低于目标{self.thresholds['learning_lift_min']}%",
                evidence={"avg_lift": avg_lift, "sample_size": len(metrics_data)},
                confidence=0.85,
                recommended_action="建议调整整体出题策略和练习难度"
            ))

        return AnalysisResult(
            analysis_type="learning_effect",
            insights=insights,
            metrics_summary={
                "total_records": len(metrics_data),
                "avg_learning_lift": avg_lift,
                "lift_distribution": self._categorize_lift(metrics_data),
            },
            recommended_actions=[i.recommended_action for i in insights]
        )

    async def _analyze_difficulty_calibration(self, days: int) -> AnalysisResult:
        """分析难度校准"""
        metrics_data = await self._load_metrics("answer", days)

        # 按难度分组分析
        difficulty_stats = {}
        for record in metrics_data:
            difficulty = record["data"].get("difficulty", "unknown")
            if difficulty not in difficulty_stats:
                difficulty_stats[difficulty] = []
            accuracy = record["data"].get("accuracy_rate", 0)
            if accuracy > 0:
                difficulty_stats[difficulty].append(accuracy)

        calibration_results = {}
        expected_accuracy = {"easy": 0.80, "medium": 0.60, "hard": 0.40}

        insights = []
        for difficulty, accuracies in difficulty_stats.items():
            if not accuracies:
                continue

            actual_accuracy = sum(accuracies) / len(accuracies)
            expected = expected_accuracy.get(difficulty, 0.60)
            deviation = actual_accuracy - expected

            calibration_results[difficulty] = {
                "expected_accuracy": expected,
                "actual_accuracy": actual_accuracy,
                "deviation": deviation,
                "sample_size": len(accuracies),
                "is_calibrated": abs(deviation) < self.thresholds["difficulty_deviation_max"]
            }

            if abs(deviation) >= self.thresholds["difficulty_deviation_max"]:
                insights.append(LearningInsight(
                    insight_id=f"insight_difficulty_{difficulty}",
                    category="difficulty_calibration",
                    title=f"「{difficulty}」难度预测偏差过大",
                    description=f"预测正确率{expected*100:.0f}%，实际{actual_accuracy*100:.0f}%，偏差{deviation*100:.1f}%",
                    evidence=calibration_results[difficulty],
                    confidence=0.80,
                    recommended_action=f"调整{difficulty}难度题目的生成标准"
                ))

        return AnalysisResult(
            analysis_type="difficulty_calibration",
            insights=insights,
            metrics_summary=calibration_results,
            recommended_actions=[i.recommended_action for i in insights]
        )

    def _merge_results(self, results: List[AnalysisResult]) -> AnalysisResult:
        """合并多个分析结果"""
        all_insights = []
        all_actions = []
        merged_summary = {}

        for result in results:
            all_insights.extend(result.insights)
            all_actions.extend(result.recommended_actions)
            merged_summary[result.analysis_type] = result.metrics_summary

        return AnalysisResult(
            analysis_type="all",
            insights=all_insights,
            metrics_summary=merged_summary,
            recommended_actions=list(set(all_actions))
        )

    async def _load_metrics(self, metric_type: str, days: int) -> List[Dict]:
        """加载指标数据"""
        from .metrics_collector import MetricsCollector
        collector = MetricsCollector()

        time_window = f"{days}d"

        result = await collector.get_metrics(metric_type, time_window)
        return result.get("metrics", [])

    def _calculate_rejection_distribution(self, reviews: List[Dict]) -> Dict[str, int]:
        """计算拒绝原因分布"""
        distribution = {}
        for review in reviews:
            reasons = review.get("data", {}).get("rejection_reasons", [])
            for reason in reasons:
                distribution[reason] = distribution.get(reason, 0) + 1
        return distribution

    async def _analyze_by_knowledge_point(self, reviews: List[Dict]) -> Dict[str, Dict]:
        """按知识点分析"""
        kp_stats = {}
        for review in reviews:
            kps = review.get("data", {}).get("knowledge_points", [])
            status = review.get("data", {}).get("status", "")
            for kp in kps:
                if kp not in kp_stats:
                    kp_stats[kp] = {"total": 0, "approved": 0, "rejected": 0}
                kp_stats[kp]["total"] += 1
                if status == "approved":
                    kp_stats[kp]["approved"] += 1
                elif status == "rejected":
                    kp_stats[kp]["rejected"] += 1

        # 计算通过率
        for kp in kp_stats:
            total = kp_stats[kp]["total"]
            if total > 0:
                kp_stats[kp]["approval_rate"] = kp_stats[kp]["approved"] / total

        return kp_stats

    def _categorize_lift(self, data: List[Dict]) -> Dict[str, int]:
        """将提升度分类统计"""
        categories = {
            "significant_improvement": 0,
            "slight_improvement": 0,
            "no_change": 0,
            "declined": 0
        }
        for d in data:
            lift = d["data"].get("learning_lift", 0)
            if lift > 10:
                categories["significant_improvement"] += 1
            elif lift > 0:
                categories["slight_improvement"] += 1
            elif lift == 0:
                categories["no_change"] += 1
            else:
                categories["declined"] += 1
        return categories

    async def save_insight(self, insight: LearningInsight) -> None:
        """保存洞察"""
        insight_file = self.insights_dir / f"{insight.insight_id}.json"
        with open(insight_file, "w", encoding="utf-8") as f:
            json.dump({
                "insight_id": insight.insight_id,
                "category": insight.category,
                "title": insight.title,
                "description": insight.description,
                "evidence": insight.evidence,
                "confidence": insight.confidence,
                "recommended_action": insight.recommended_action,
                "auto_applied": insight.auto_applied,
                "teacher_approved": insight.teacher_approved,
                "created_at": insight.created_at.isoformat()
            }, f, ensure_ascii=False, indent=2)
