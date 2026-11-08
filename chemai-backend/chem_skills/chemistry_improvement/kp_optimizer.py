"""
chemistry-improvement KP Optimizer
知识点组合优化器
"""
from typing import Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
import logging

logger = logging.getLogger("chemistry-improvement")

# 存储目录
KP_DATA_DIR = Path(__file__).parent / "kp_data"
KP_DATA_DIR.mkdir(exist_ok=True)


@dataclass
class KPCombinationMetrics:
    """知识点组合指标"""
    kp_combination: Tuple[str, ...]
    times_used: int = 0
    avg_learning_lift: float = 0.0
    approval_rate: float = 0.0
    student_satisfaction: float = 0.0
    effectiveness_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "kp_combination": list(self.kp_combination),
            "times_used": self.times_used,
            "avg_learning_lift": self.avg_learning_lift,
            "approval_rate": self.approval_rate,
            "student_satisfaction": self.student_satisfaction,
            "effectiveness_score": self.effectiveness_score
        }


class KPOptimizer:
    """知识点组合优化器"""

    def __init__(self):
        self.data_dir = KP_DATA_DIR
        self.combination_metrics: Dict[Tuple[str, ...], KPCombinationMetrics] = {}
        self.min_samples = 5
        self._load_data()

        # 预设的知识点关联
        self.default_relations = {
            "盐类水解": ["电离", "水的离子积", "电离常数"],
            "电离": ["电解质", "离子反应", "盐类水解"],
            "氧化还原反应": ["电化学", "原电池", "电解池"],
            "原电池": ["氧化还原反应", "电解池", "金属腐蚀"],
            "化学平衡": ["勒夏特列原理", "化学反应速率", "平衡常数"],
            "物质的量": ["阿伏伽德罗常数", "摩尔质量", "气体摩尔体积"],
        }

    def _get_data_file(self) -> Path:
        return self.data_dir / "kp_combinations.json"

    def _load_data(self) -> None:
        """加载数据"""
        data_file = self._get_data_file()
        if data_file.exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        kp_tuple = tuple(json.loads(key))
                        self.combination_metrics[kp_tuple] = KPCombinationMetrics(
                            kp_combination=kp_tuple,
                            times_used=value.get("times_used", 0),
                            avg_learning_lift=value.get("avg_learning_lift", 0.0),
                            approval_rate=value.get("approval_rate", 0.0),
                            student_satisfaction=value.get("student_satisfaction", 0.0),
                            effectiveness_score=value.get("effectiveness_score", 0.0)
                        )
            except json.JSONDecodeError:
                pass

    def _save_data(self) -> None:
        """保存数据"""
        data_file = self._get_data_file()
        data = {}
        for kp_tuple, metrics in self.combination_metrics.items():
            data[json.dumps(kp_tuple)] = metrics.to_dict()

        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def record_usage(
        self,
        kp_combination: List[str],
        learning_lift: float,
        approved: bool
    ) -> None:
        """
        记录一次知识点组合的使用

        Args:
            kp_combination: 知识点组合（无序）
            learning_lift: 学习提升度
            approved: 是否审核通过
        """
        # 排序以统一表示
        kp_tuple = tuple(sorted(kp_combination))

        if kp_tuple not in self.combination_metrics:
            self.combination_metrics[kp_tuple] = KPCombinationMetrics(
                kp_combination=kp_tuple,
                times_used=0,
                avg_learning_lift=0.0,
                approval_rate=0.0,
                student_satisfaction=0.0,
                effectiveness_score=0.0
            )

        m = self.combination_metrics[kp_tuple]

        # 更新指标（滑动平均）
        m.times_used += 1
        m.avg_learning_lift = (
            (m.avg_learning_lift * (m.times_used - 1) + learning_lift) / m.times_used
        )
        if approved:
            m.approval_rate = (
                (m.approval_rate * (m.times_used - 1) + 1.0) / m.times_used
            )
        else:
            m.approval_rate = m.approval_rate * (m.times_used - 1) / m.times_used

        # 重新计算综合评分
        m.effectiveness_score = self._calculate_effectiveness(m)

        logger.info(f"更新KP组合指标: {kp_tuple}, score={m.effectiveness_score:.2f}")

        # 保存
        self._save_data()

    def get_best_combinations(
        self,
        knowledge_point: str,
        top_n: int = 5
    ) -> List[KPCombinationMetrics]:
        """
        获取与给定知识点搭配效果最好的组合

        Args:
            knowledge_point: 锚定知识点
            top_n: 返回数量

        Returns:
            按效果评分排序的组合列表
        """
        # 找出所有包含该知识点的组合
        relevant = [
            m for kp_tuple, m in self.combination_metrics.items()
            if knowledge_point in kp_tuple and m.times_used >= self.min_samples
        ]

        # 按效果评分排序
        relevant.sort(key=lambda m: m.effectiveness_score, reverse=True)

        return relevant[:top_n]

    def get_recommended_combinations(
        self,
        primary_kp: str,
        count: int = 3
    ) -> List[Dict]:
        """
        获取推荐的知识组合

        基于:
        1. 历史上与 primary_kp 搭配效果好的组合
        2. 知识点关联图谱中的相关知识点
        3. 高考真题中常见的组合模式
        """
        best = self.get_best_combinations(primary_kp, top_n=count)

        recommendations = []
        for m in best:
            # 找出组合中除 primary_kp 外的其他知识点
            other_kps = [kp for kp in m.kp_combination if kp != primary_kp]

            recommendations.append({
                "primary_kp": primary_kp,
                "recommended_kps": other_kps,
                "effectiveness_score": m.effectiveness_score,
                "avg_learning_lift": m.avg_learning_lift,
                "sample_size": m.times_used,
                "confidence": min(m.times_used / 20, 1.0)
            })

        # 如果样本不足，使用默认值
        if not recommendations:
            recommendations = self._get_default_recommendations(primary_kp)

        return recommendations

    def get_effectiveness(
        self,
        knowledge_point: str,
        time_window_days: int = 30
    ) -> Dict:
        """
        获取知识点的效果分析

        Args:
            knowledge_point: 知识点
            time_window_days: 时间窗口（天）

        Returns:
            效果分析结果
        """
        # 找出所有包含该知识点的组合
        relevant = [
            m for kp_tuple, m in self.combination_metrics.items()
            if knowledge_point in kp_tuple
        ]

        if not relevant:
            return {
                "knowledge_point": knowledge_point,
                "sample_size": 0,
                "avg_effectiveness_score": 0.0,
                "avg_learning_lift": 0.0,
                "total_combinations": 0,
                "is_default": True,
                "recommendations": self._get_default_recommendations(knowledge_point)
            }

        total_samples = sum(m.times_used for m in relevant)
        avg_score = (
            sum(m.effectiveness_score * m.times_used for m in relevant) / total_samples
            if total_samples > 0
            else 0
        )
        avg_lift = (
            sum(m.avg_learning_lift * m.times_used for m in relevant) / total_samples
            if total_samples > 0
            else 0
        )

        return {
            "knowledge_point": knowledge_point,
            "sample_size": total_samples,
            "avg_effectiveness_score": avg_score,
            "avg_learning_lift": avg_lift,
            "total_combinations": len(relevant),
            "is_default": False,
            "recommendations": self.get_recommended_combinations(knowledge_point, count=3)
        }

    def _calculate_effectiveness(self, m: KPCombinationMetrics) -> float:
        """
        计算综合效果评分

        公式: w1 * learning_lift + w2 * approval_rate + w3 * satisfaction
        """
        w1, w2, w3 = 0.5, 0.3, 0.2

        # 标准化各指标到 0-1
        lift_norm = min(m.avg_learning_lift / 20.0, 1.0)
        approval_norm = m.approval_rate
        satisfaction_norm = m.student_satisfaction

        return w1 * lift_norm + w2 * approval_norm + w3 * satisfaction_norm

    def _get_default_recommendations(self, primary_kp: str) -> List[Dict]:
        """获取默认推荐（基于知识点关联图谱）"""
        default_kps = self.default_relations.get(primary_kp, [])

        return [
            {
                "primary_kp": primary_kp,
                "recommended_kps": default_kps[:2],
                "effectiveness_score": 0.5,
                "avg_learning_lift": 5.0,
                "sample_size": 0,
                "confidence": 0.3,
                "is_default": True
            }
        ]
