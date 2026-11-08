"""
chemistry-improvement Strategy Controller
策略调整控制器
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import logging

from .models import StrategyAdjustment

logger = logging.getLogger("chemistry-improvment")

# 存储目录
STRATEGY_DIR = Path(__file__).parent / "strategy_data"
STRATEGY_DIR.mkdir(exist_ok=True)


class AdjustmentType:
    """调整类型"""
    PROMPT_UPDATE = "prompt_update"
    DIFFICULTY_RECALIBRATE = "difficulty_recalibrate"
    KP_WEIGHT_UPDATE = "kp_weight_update"
    THRESHOLD_ADJUST = "threshold_adjust"


@dataclass
class AdjustmentRule:
    """调整规则"""
    rule_id: str
    trigger_condition: str
    adjustment_type: str
    adjustment_value: Any
    auto_apply: bool
    requires_approval: bool


class StrategyController:
    """策略调整控制器"""

    def __init__(self, prompt_manager=None, kp_optimizer=None):
        self.prompt_manager = prompt_manager
        self.kp_optimizer = kp_optimizer
        self.strategy_dir = STRATEGY_DIR

        # 预设调整规则
        self.rules: List[AdjustmentRule] = self._get_default_rules()

        # 调整历史
        self.adjustment_history: List[StrategyAdjustment] = []
        self.pending_adjustments: Dict[str, StrategyAdjustment] = {}

        # 加载历史
        self._load_history()

    def _get_history_file(self) -> Path:
        return self.strategy_dir / "adjustments.json"

    def _load_history(self) -> None:
        """加载历史"""
        history_file = self._get_history_file()
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.adjustment_history = [
                        StrategyAdjustment(
                            adjustment_id=a["adjustment_id"],
                            strategy_type=a["strategy_type"],
                            adjustment_type=a["adjustment_type"],
                            old_value=a.get("old_value"),
                            new_value=a["new_value"],
                            trigger_reason=a["trigger_reason"],
                            applied_at=datetime.fromisoformat(a["applied_at"]),
                            applied_by=a["applied_by"],
                            approved_by=a.get("approved_by"),
                            status=a.get("status", "applied")
                        )
                        for a in data.get("history", [])
                    ]
                    self.pending_adjustments = {
                        a["adjustment_id"]: StrategyAdjustment(
                            adjustment_id=a["adjustment_id"],
                            strategy_type=a["strategy_type"],
                            adjustment_type=a["adjustment_type"],
                            old_value=a.get("old_value"),
                            new_value=a["new_value"],
                            trigger_reason=a["trigger_reason"],
                            applied_at=datetime.fromisoformat(a["applied_at"]),
                            applied_by=a["applied_by"],
                            approved_by=a.get("approved_by"),
                            status=a.get("status", "pending")
                        )
                        for a in data.get("pending", [])
                    }
            except json.JSONDecodeError:
                pass

    def _save_history(self) -> None:
        """保存历史"""
        history_file = self._get_history_file()
        data = {
            "history": [
                {
                    "adjustment_id": a.adjustment_id,
                    "strategy_type": a.strategy_type,
                    "adjustment_type": a.adjustment_type,
                    "old_value": a.old_value,
                    "new_value": a.new_value,
                    "trigger_reason": a.trigger_reason,
                    "applied_at": a.applied_at.isoformat(),
                    "applied_by": a.applied_by,
                    "approved_by": a.approved_by,
                    "status": a.status
                }
                for a in self.adjustment_history
            ],
            "pending": [
                {
                    "adjustment_id": a.adjustment_id,
                    "strategy_type": a.strategy_type,
                    "adjustment_type": a.adjustment_type,
                    "old_value": a.old_value,
                    "new_value": a.new_value,
                    "trigger_reason": a.trigger_reason,
                    "applied_at": a.applied_at.isoformat(),
                    "applied_by": a.apjusted_by,
                    "approved_by": a.approved_by,
                    "status": a.status
                }
                for a in self.pending_adjustments.values()
            ]
        }
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_default_rules(self) -> List[AdjustmentRule]:
        """获取默认调整规则"""
        return [
            AdjustmentRule(
                rule_id="rule_approval_rate_low",
                trigger_condition="approval_rate < 0.70 for 7 days",
                adjustment_type=AdjustmentType.PROMPT_UPDATE,
                adjustment_value="auto_improve",
                auto_apply=False,
                requires_approval=True
            ),

            AdjustmentRule(
                rule_id="rule_difficulty_calibration",
                trigger_condition="difficulty_deviation > 0.15 for 3 days",
                adjustment_type=AdjustmentType.DIFFICULTY_RECALIBRATE,
                adjustment_value="auto_adjust",
                auto_apply=True,
                requires_approval=False
            ),

            AdjustmentRule(
                rule_id="rule_learning_lift_low",
                trigger_condition="learning_lift < 5% for 14 days",
                adjustment_type=AdjustmentType.KP_WEIGHT_UPDATE,
                adjustment_value="reduce_weight",
                auto_apply=False,
                requires_approval=True
            ),

            AdjustmentRule(
                rule_id="rule_kp_combination_good",
                trigger_condition="kp_combination_score > 0.85 with 20+ samples",
                adjustment_type=AdjustmentType.KP_WEIGHT_UPDATE,
                adjustment_value="increase_weight",
                auto_apply=True,
                requires_approval=False
            ),
        ]

    async def request_adjustment(
        self,
        strategy_type: str,
        adjustment_request: Dict
    ) -> StrategyAdjustment:
        """
        请求策略调整

        Args:
            strategy_type: 策略类型 (prompt/difficulty/kp_combination/threshold)
            adjustment_request: 调整请求

        Returns:
            调整对象
        """
        adjustment = StrategyAdjustment(
            adjustment_id=f"adj_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            strategy_type=strategy_type,
            adjustment_type=self._get_adjustment_type(strategy_type),
            old_value=adjustment_request.get("current_value"),
            new_value=adjustment_request.get("proposed_value"),
            trigger_reason=adjustment_request.get("reason", ""),
            applied_at=datetime.now(),
            applied_by="teacher_request",
            status="pending"
        )

        self.pending_adjustments[adjustment.adjustment_id] = adjustment
        self._save_history()

        return adjustment

    async def list_adjustments(
        self,
        status: str = "all",
        limit: int = 10
    ) -> List[Dict]:
        """
        列出调整历史

        Args:
            status: 状态过滤 (all/applied/pending/rejected)
            limit: 返回数量

        Returns:
            调整列表
        """
        if status == "all":
            history = self.adjustment_history + list(self.pending_adjustments.values())
        elif status == "pending":
            history = list(self.pending_adjustments.values())
        else:
            history = [
                a for a in self.adjustment_history
                if a.status == status
            ]

        history = sorted(history, key=lambda x: x.applied_at, reverse=True)

        return [
            {
                "adjustment_id": a.adjustment_id,
                "strategy_type": a.strategy_type,
                "adjustment_type": a.adjustment_type,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "trigger_reason": a.trigger_reason,
                "applied_at": a.applied_at.isoformat(),
                "applied_by": a.applied_by,
                "approved_by": a.approved_by,
                "status": a.status
            }
            for a in history[:limit]
        ]

    async def approve_adjustment(
        self,
        adjustment_id: str,
        teacher_id: str,
        approved: bool,
        feedback: str = None
    ) -> bool:
        """
        审批调整请求

        Args:
            adjustment_id: 调整ID
            teacher_id: 审批老师ID
            approved: 是否批准
            feedback: 审批反馈

        Returns:
            是否成功
        """
        pending = self.pending_adjustments.get(adjustment_id)
        if not pending:
            return False

        if approved:
            # 执行调整
            await self._execute_adjustment(pending)
            pending.approved_by = teacher_id
            pending.status = "applied"
            self.adjustment_history.append(pending)
            del self.pending_adjustments[adjustment_id]
        else:
            # 拒绝
            pending.approved_by = teacher_id
            pending.status = "rejected"
            self.adjustment_history.append(pending)
            del self.pending_adjustments[adjustment_id]

        self._save_history()
        return True

    async def rollback(
        self,
        strategy_type: str,
        target_version_id: Optional[str] = None
    ) -> Dict:
        """
        回滚策略

        Args:
            strategy_type: 策略类型
            target_version_id: 目标版本ID

        Returns:
            回滚结果
        """
        if strategy_type == "prompt" and self.prompt_manager:
            version = await self.prompt_manager.rollback(strategy_type, target_version_id)
            return {
                "success": True,
                "rolled_back_to": version.version_id if version else "default"
            }
        else:
            return {
                "success": False,
                "error": f"Cannot rollback strategy type: {strategy_type}"
            }

    # ===== 内部方法 =====

    async def _execute_adjustment(self, adjustment: StrategyAdjustment) -> None:
        """执行调整"""
        logger.info(f"执行调整: {adjustment.adjustment_id}")

        if adjustment.adjustment_type == AdjustmentType.PROMPT_UPDATE:
            if self.prompt_manager:
                # 生成改进的 Prompt（简化实现）
                improved_prompt = self._generate_improved_prompt(adjustment)
                await self.prompt_manager.update_prompt(
                    prompt_type="question_generation",
                    new_content=improved_prompt,
                    change_reason=f"自动改进: {adjustment.trigger_reason}",
                    change_source="auto_improvement",
                    metrics_at_change={"adjustment_id": adjustment.adjustment_id}
                )

    def _generate_improved_prompt(self, adjustment: StrategyAdjustment) -> str:
        """生成改进的 Prompt（简化实现）"""
        # 这里可以调用 LLM 来生成改进建议
        current = self.prompt_manager.get_prompt("question_generation") if self.prompt_manager else ""

        # 添加更严格的审核提示
        improved = current + "\n\n[改进建议] 根据分析结果，请特别关注以下方面：\n"

        if "equation" in adjustment.trigger_reason.lower():
            improved += "- 必须反复核对化学方程式是否配平\n"
        if "knowledge_point" in adjustment.trigger_reason.lower():
            improved += "- 确保知识点对应准确无误\n"
        if "difficulty" in adjustment.trigger_reason.lower():
            improved += "- 难度设置要符合学生实际水平\n"

        return improved

    def _get_adjustment_type(self, strategy_type: str) -> str:
        """获取调整类型"""
        type_map = {
            "prompt": AdjustmentType.PROMPT_UPDATE,
            "difficulty": AdjustmentType.DIFFICULTY_RECALIBRATE,
            "kp_combination": AdjustmentType.KP_WEIGHT_UPDATE,
            "threshold": AdjustmentType.THRESHOLD_ADJUST
        }
        return type_map.get(strategy_type, AdjustmentType.PROMPT_UPDATE)
