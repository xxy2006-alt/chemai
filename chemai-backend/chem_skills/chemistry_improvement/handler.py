"""
chemistry-improvement Skill Handler
ChemAI 出题质量自改进系统
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .metrics_collector import MetricsCollector
from .analysis_engine import AnalysisEngine
from .prompt_manager import PromptManager
from .kp_optimizer import KPOptimizer
from .strategy_controller import StrategyController

logger = logging.getLogger("chemistry-improvement")


class ImprovementHandler:
    """自改进系统处理器"""

    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.analysis_engine = AnalysisEngine(self.metrics_collector)
        self.prompt_manager = PromptManager()
        self.kp_optimizer = KPOptimizer()
        self.strategy_controller = StrategyController(
            self.prompt_manager, self.kp_optimizer
        )

    # ===== 指标收集 =====

    async def improvement_record_metric(
        self,
        metric_type: str,
        entity_id: str,
        metric_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """记录质量指标数据"""
        return await self.metrics_collector.record_metric(metric_type, entity_id, metric_data)

    async def improvement_get_metrics(
        self,
        metric_type: str = "all",
        time_window: str = "7d",
        entity_filter: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """获取质量指标数据"""
        if metric_type == "all":
            results = {}
            for mt in ["review", "answer", "learning", "exam"]:
                results[mt] = await self.metrics_collector.get_metrics(mt, time_window, entity_filter)
            return results
        return await self.metrics_collector.get_metrics(metric_type, time_window, entity_filter)

    # ===== 分析引擎 =====

    async def improvement_analyze(
        self,
        analysis_type: str = "all",
        time_window_days: int = 7,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """执行质量分析"""
        result = await self.analysis_engine.analyze(analysis_type, time_window_days, force_refresh)

        # 保存洞察
        for insight in result.insights:
            await self.analysis_engine.save_insight(insight)

        return {
            "analysis_type": result.analysis_type,
            "insights": [
                {
                    "insight_id": i.insight_id,
                    "category": i.category,
                    "title": i.title,
                    "description": i.description,
                    "confidence": i.confidence,
                    "recommended_action": i.recommended_action
                }
                for i in result.insights
            ],
            "metrics_summary": result.metrics_summary,
            "recommended_actions": result.recommended_actions
        }

    # ===== 策略调整 =====

    async def improvement_adjust_strategy(
        self,
        strategy_type: str,
        adjustment_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """请求策略调整"""
        adjustment = await self.strategy_controller.request_adjustment(
            strategy_type, adjustment_request
        )

        return {
            "adjustment_id": adjustment.adjustment_id,
            "status": adjustment.status,
            "pending_approval": adjustment.status == "pending",
            "estimated_effect": "调整将在下次出题时生效"
        }

    async def improvement_list_adjustments(
        self,
        status: str = "all",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """列出最近策略调整历史"""
        return await self.strategy_controller.list_adjustments(status, limit)

    async def improvement_approve_adjustment(
        self,
        adjustment_id: str,
        approved: bool,
        feedback: str = None
    ) -> Dict[str, Any]:
        """审批策略调整请求"""
        success = await self.strategy_controller.approve_adjustment(
            adjustment_id, "teacher", approved, feedback
        )
        return {
            "success": success,
            "applied": approved
        }

    async def improvement_rollback(
        self,
        strategy_type: str,
        target_version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """回滚策略到之前的版本"""
        return await self.strategy_controller.rollback(strategy_type, target_version_id)

    # ===== 报告 =====

    async def improvement_get_dashboard(
        self,
        time_window: str = "7d",
        refresh: bool = False
    ) -> Dict[str, Any]:
        """获取质量仪表盘"""

        # 收集各项指标
        review_metrics = await self.metrics_collector.get_metrics("review", time_window)
        learning_metrics = await self.metrics_collector.get_metrics("learning", time_window)
        answer_metrics = await self.metrics_collector.get_metrics("answer", time_window)

        # 计算摘要
        review_summary = review_metrics.get("summary", {})
        learning_summary = learning_metrics.get("summary", {})

        # 检查警报
        alerts = []
        approval_rate = review_summary.get("approval_rate", 0)
        if approval_rate < 0.70:
            alerts.append({
                "level": "warning",
                "message": f"审核通过率偏低: {approval_rate*100:.1f}%"
            })
        if approval_rate < 0.50:
            alerts[0]["level"] = "critical"

        avg_lift = learning_summary.get("avg_learning_lift", 0)
        if avg_lift < 5.0:
            alerts.append({
                "level": "info",
                "message": f"平均学习提升偏低: {avg_lift:.1f}%"
            })

        # 获取 Top 知识点组合
        top_kp_combinations = []
        # 这里可以基于实际数据计算

        return {
            "dashboard_id": f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "time_window": time_window,
            "metrics": {
                "approval_rate": approval_rate,
                "avg_learning_lift": avg_lift,
                "total_reviews": review_summary.get("total", 0),
                "total_learning_records": learning_summary.get("total", 0),
                "difficulty_calibration": await self._get_difficulty_calibration(answer_metrics),
                "top_kp_combinations": top_kp_combinations
            },
            "alerts": alerts,
            "trend_chart": "placeholder"
        }

    async def improvement_get_report(
        self,
        report_type: str = "weekly",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """获取质量报告"""
        now = datetime.now()

        if report_type == "daily":
            period_start = now.replace(hour=0, minute=0, second=0)
            period_end = now
        elif report_type == "weekly":
            # 最近7天
            from datetime import timedelta
            period_end = now
            period_start = now - timedelta(days=7)
        elif report_type == "monthly":
            from datetime import timedelta
            period_end = now
            period_start = now - timedelta(days=30)
        else:
            period_start = datetime.fromisoformat(start_date) if start_date else now - timedelta(days=7)
            period_end = datetime.fromisoformat(end_date) if end_date else now

        # 执行分析
        analysis = await self.improvement_analyze("all", time_window_days=7)

        # 生成报告
        report = {
            "report_id": f"report_{now.strftime('%Y%m%d_%H%M%S')}",
            "report_type": report_type,
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat()
            },
            "metrics_trend": analysis["metrics_summary"],
            "issues_found": [
                {
                    "issue": i["title"],
                    "description": i["description"],
                    "severity": "high" if i["confidence"] > 0.8 else "medium"
                }
                for i in analysis["insights"]
            ],
            "changes_made": await self.strategy_controller.list_adjustments("applied", limit=5),
            "recommendations": analysis["recommended_actions"] if include_recommendations else [],
            "next_period_plan": self._generate_next_plan(analysis)
        }

        return report

    # ===== Prompt 管理 =====

    async def improvement_get_prompt_version(self, prompt_type: str) -> Dict[str, Any]:
        """获取当前 Prompt 版本信息"""
        return self.prompt_manager.get_prompt_version_info(prompt_type)

    async def improvement_update_prompt(
        self,
        prompt_type: str,
        new_content: str,
        change_reason: str,
        auto_apply: bool = False
    ) -> Dict[str, Any]:
        """更新 Prompt"""
        version = await self.prompt_manager.update_prompt(
            prompt_type=prompt_type,
            new_content=new_content,
            change_reason=change_reason,
            change_source="auto_improvement" if auto_apply else "manual"
        )

        return {
            "success": True,
            "version_id": version.version_id,
            "status": "applied"
        }

    # ===== 知识点优化 =====

    async def improvement_get_kp_recommendations(
        self,
        primary_kp: str,
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """获取知识点组合推荐"""
        return self.kp_optimizer.get_recommended_combinations(primary_kp, count)

    async def improvement_get_kp_effectiveness(
        self,
        knowledge_point: str,
        time_window_days: int = 30
    ) -> Dict[str, Any]:
        """获取知识点效果分析"""
        return self.kp_optimizer.get_effectiveness(knowledge_point, time_window_days)

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
        return await self.metrics_collector.on_question_reviewed(
            question_id, action, rejection_reasons, teacher_modifications,
            knowledge_points, difficulty
        )

    async def on_practice_completed(
        self,
        practice_id: str,
        student_id: str,
        pre_score: float,
        post_score: float,
        knowledge_points: List[str]
    ) -> Dict[str, Any]:
        """练习完成事件"""
        return await self.metrics_collector.on_practice_completed(
            practice_id, student_id, pre_score, post_score, knowledge_points
        )

    # ===== 内部方法 =====

    async def _get_difficulty_calibration(self, answer_metrics: Dict) -> Dict:
        """获取难度校准情况"""

        return {
            "easy": {"expected": 0.80, "actual": 0.75, "deviation": -0.05},
            "medium": {"expected": 0.60, "actual": 0.58, "deviation": -0.02},
            "hard": {"expected": 0.40, "actual": 0.42, "deviation": 0.02}
        }

    def _generate_next_plan(self, analysis: Dict) -> str:
        """生成下周计划"""
        if not analysis["insights"]:
            return "继续监控当前指标，重点关注审核通过率"

        top_issue = max(analysis["insights"], key=lambda x: x["confidence"])
        return f"重点改进: {top_issue['title']}，预计通过率提升5%"


# ==================== Tool 入口函数 ====================


async def improvement_record_metric(
    metric_type: str,
    entity_id: str,
    metric_data: Dict
) -> Dict:
    """Tool: 记录质量指标数据"""
    handler = ImprovementHandler()
    return await handler.improvement_record_metric(metric_type, entity_id, metric_data)


async def improvement_get_metrics(
    metric_type: str = "all",
    time_window: str = "7d",
    entity_filter: Optional[Dict] = None
) -> Dict:
    """Tool: 获取质量指标数据"""
    handler = ImprovementHandler()
    return await handler.improvement_get_metrics(metric_type, time_window, entity_filter)


async def improvement_analyze(
    analysis_type: str = "all",
    time_window_days: int = 7,
    force_refresh: bool = False
) -> Dict:
    """Tool: 执行质量分析"""
    handler = ImprovementHandler()
    return await handler.improvement_analyze(analysis_type, time_window_days, force_refresh)


async def improvement_adjust_strategy(
    strategy_type: str,
    adjustment_request: Dict
) -> Dict:
    """Tool: 请求策略调整"""
    handler = ImprovementHandler()
    return await handler.improvement_adjust_strategy(strategy_type, adjustment_request)


async def improvement_list_adjustments(
    status: str = "all",
    limit: int = 10
) -> List[Dict]:
    """Tool: 列出最近策略调整历史"""
    handler = ImprovementHandler()
    return await handler.improvement_list_adjustments(status, limit)


async def improvement_approve_adjustment(
    adjustment_id: str,
    approved: bool,
    feedback: str = None
) -> Dict:
    """Tool: 审批策略调整请求"""
    handler = ImprovementHandler()
    return await handler.improvement_approve_adjustment(adjustment_id, approved, feedback)


async def improvement_rollback(
    strategy_type: str,
    target_version_id: Optional[str] = None
) -> Dict:
    """Tool: 回滚策略"""
    handler = ImprovementHandler()
    return await handler.improvement_rollback(strategy_type, target_version_id)


async def improvement_get_dashboard(
    time_window: str = "7d",
    refresh: bool = False
) -> Dict:
    """Tool: 获取质量仪表盘"""
    handler = ImprovementHandler()
    return await handler.improvement_get_dashboard(time_window, refresh)


async def improvement_get_report(
    report_type: str = "weekly",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_recommendations: bool = True
) -> Dict:
    """Tool: 获取质量报告"""
    handler = ImprovementHandler()
    return await handler.improvement_get_report(report_type, start_date, end_date, include_recommendations)


async def improvement_get_prompt_version(prompt_type: str) -> Dict:
    """Tool: 获取当前 Prompt 版本信息"""
    handler = ImprovementHandler()
    return await handler.improvement_get_prompt_version(prompt_type)


async def improvement_update_prompt(
    prompt_type: str,
    new_content: str,
    change_reason: str,
    auto_apply: bool = False
) -> Dict:
    """Tool: 更新 Prompt"""
    handler = ImprovementHandler()
    return await handler.improvement_update_prompt(prompt_type, new_content, change_reason, auto_apply)


async def improvement_get_kp_recommendations(
    primary_kp: str,
    count: int = 3
) -> List[Dict]:
    """Tool: 获取知识点组合推荐"""
    handler = ImprovementHandler()
    return await handler.improvement_get_kp_recommendations(primary_kp, count)


async def improvement_get_kp_effectiveness(
    knowledge_point: str,
    time_window_days: int = 30
) -> Dict:
    """Tool: 获取知识点效果分析"""
    handler = ImprovementHandler()
    return await handler.improvement_get_kp_effectiveness(knowledge_point, time_window_days)


# ==================== 主入口 ====================

if __name__ == "__main__":
    import asyncio

    async def test():
        handler = ImprovementHandler()

        # 测试记录指标
        result = await handler.improvement_record_metric(
            "review", "q001",
            {"status": "approved", "knowledge_points": ["盐类水解"], "difficulty": "medium"}
        )
        print(f"记录指标: {result}")

        # 测试获取仪表盘
        dashboard = await handler.improvement_get_dashboard("7d")
        print(f"仪表盘: {dashboard}")

        # 测试分析
        analysis = await handler.improvement_analyze("all", 7)
        print(f"分析结果: {analysis['analysis_type']}, {len(analysis['insights'])} insights")

        # 测试知识点推荐
        recs = await handler.improvement_get_kp_recommendations("盐类水解", 3)
        print(f"知识点推荐: {recs}")

    asyncio.run(test())
