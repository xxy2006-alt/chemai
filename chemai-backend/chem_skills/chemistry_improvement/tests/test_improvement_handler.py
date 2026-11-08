"""
chemistry-improvement Skill Tests
测试自改进系统
"""
import sys
from pathlib import Path
import tempfile
import shutil

# 添加项目根目录
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestKPOptimizer:
    """测试知识点优化器"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        import chemistry_improvement.kp_optimizer as kp_module
        self.original_dir = kp_module.KP_DATA_DIR
        kp_module.KP_DATA_DIR = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """每个测试后清理"""
        import chemistry_improvement.kp_optimizer as kp_module
        shutil.rmtree(kp_module.KP_DATA_DIR, ignore_errors=True)

    def test_record_usage(self):
        """测试记录知识点组合使用"""
        from chemistry_improvement.kp_optimizer import KPOptimizer

        optimizer = KPOptimizer()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            optimizer.record_usage(
                kp_combination=["盐类水解", "电离"],
                learning_lift=10.0,
                approved=True
            )
        )

        assert optimizer.combination_metrics
        combo = tuple(sorted(["盐类水解", "电离"]))
        assert combo in optimizer.combination_metrics
        assert optimizer.combination_metrics[combo].times_used == 1

    def test_get_recommended_combinations(self):
        """测试获取知识点组合推荐"""
        from chemistry_improvement.kp_optimizer import KPOptimizer

        optimizer = KPOptimizer()

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            optimizer.record_usage(
                kp_combination=["盐类水解", "电离"],
                learning_lift=10.0,
                approved=True
            )
        )

        recs = optimizer.get_recommended_combinations("盐类水解", count=3)
        assert len(recs) >= 1
        assert recs[0]["primary_kp"] == "盐类水解"


class TestPromptManager:
    """测试 Prompt 管理器"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        import chemistry_improvement.prompt_manager as pm_module
        self.original_dir = pm_module.PROMPTS_DIR
        pm_module.PROMPTS_DIR = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """每个测试后清理"""
        import chemistry_improvement.prompt_manager as pm_module
        shutil.rmtree(pm_module.PROMPTS_DIR, ignore_errors=True)

    def test_get_default_prompt(self):
        """测试获取默认 Prompt"""
        from chemistry_improvement.prompt_manager import PromptManager

        manager = PromptManager()
        prompt = manager.get_prompt("question_generation")

        assert "高中化学" in prompt
        assert "JSON" in prompt

    def test_get_prompt_version_info(self):
        """测试获取 Prompt 版本信息"""
        from chemistry_improvement.prompt_manager import PromptManager

        manager = PromptManager()
        info = manager.get_prompt_version_info("question_generation")

        assert "version_id" in info
        assert "content" in info


class TestMetricsCollector:
    """测试指标收集器"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        import chemistry_improvement.metrics_collector as mc_module
        self.original_dir = mc_module.METRICS_ROOT
        mc_module.METRICS_ROOT = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """每个测试后清理"""
        import chemistry_improvement.metrics_collector as mc_module
        shutil.rmtree(mc_module.METRICS_ROOT, ignore_errors=True)

    def test_record_metric(self):
        """测试记录指标"""
        from chemistry_improvement.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            collector.record_metric(
                "review", "q001",
                {"status": "approved", "knowledge_points": ["盐类水解"]}
            )
        )

        assert result["success"] is True
        assert "metric_id" in result

    def test_get_metrics(self):
        """测试获取指标"""
        from chemistry_improvement.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        import asyncio
        # 先记录一些指标
        asyncio.get_event_loop().run_until_complete(
            collector.record_metric(
                "review", "q001",
                {"status": "approved", "knowledge_points": ["盐类水解"]}
            )
        )

        result = asyncio.get_event_loop().run_until_complete(
            collector.get_metrics("review", "7d")
        )

        assert "metrics" in result
        assert "summary" in result


class TestImprovementHandler:
    """测试改进处理器"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        import chemistry_improvement.handler as handler_module
        import chemistry_improvement.metrics_collector as mc_module
        import chemistry_improvement.prompt_manager as pm_module
        import chemistry_improvement.kp_optimizer as kp_module

        self.original_metrics = mc_module.METRICS_ROOT
        self.original_prompts = pm_module.PROMPTS_DIR
        self.original_kp = kp_module.KP_DATA_DIR

        temp_dir = Path(tempfile.mkdtemp())
        mc_module.METRICS_ROOT = temp_dir / "metrics"
        pm_module.PROMPTS_DIR = temp_dir / "prompts"
        kp_module.KP_DATA_DIR = temp_dir / "kp"

        mc_module.METRICS_ROOT.mkdir(exist_ok=True)
        pm_module.PROMPTS_DIR.mkdir(exist_ok=True)
        kp_module.KP_DATA_DIR.mkdir(exist_ok=True)

    def teardown_method(self):
        """每个测试后清理"""
        import chemistry_improvement.metrics_collector as mc_module
        import chemistry_improvement.prompt_manager as pm_module
        import chemistry_improvement.kp_optimizer as kp_module

        shutil.rmtree(mc_module.METRICS_ROOT.parent, ignore_errors=True)

        mc_module.METRICS_ROOT = self.original_metrics
        pm_module.PROMPTS_DIR = self.original_prompts
        kp_module.KP_DATA_DIR = self.original_kp

    def test_get_dashboard(self):
        """测试获取仪表盘"""
        from chemistry_improvement.handler import ImprovementHandler

        handler = ImprovementHandler()

        import asyncio
        dashboard = asyncio.get_event_loop().run_until_complete(
            handler.improvement_get_dashboard("7d")
        )

        assert "dashboard_id" in dashboard
        assert "metrics" in dashboard
        assert "alerts" in dashboard
        assert dashboard["time_window"] == "7d"

    def test_get_report(self):
        """测试获取报告"""
        from chemistry_improvement.handler import ImprovementHandler

        handler = ImprovementHandler()

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(
            handler.improvement_get_report("weekly")
        )

        assert "report_id" in report
        assert report["report_type"] == "weekly"
        assert "period" in report

    def test_kp_recommendations(self):
        """测试知识点推荐"""
        from chemistry_improvement.handler import ImprovementHandler

        handler = ImprovementHandler()

        import asyncio
        recs = asyncio.get_event_loop().run_until_complete(
            handler.improvement_get_kp_recommendations("盐类水解", 3)
        )

        assert isinstance(recs, list)
        assert len(recs) >= 1


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
