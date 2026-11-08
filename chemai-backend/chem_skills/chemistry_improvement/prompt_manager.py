"""
chemistry-improvement Prompt Manager
Prompt 策略管理器
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import json
import logging

from .models import PromptVersion

logger = logging.getLogger("chemistry-improvement")

# 存储目录
PROMPTS_DIR = Path(__file__).parent / "prompts_data"
PROMPTS_DIR.mkdir(exist_ok=True)


class PromptManager:
    """Prompt 管理器"""

    def __init__(self):
        self.storage_path = PROMPTS_DIR
        self.current_versions: Dict[str, PromptVersion] = {}
        self.change_history: List[PromptVersion] = []

        # 加载当前版本
        self._load_current_versions()

    def _get_prompt_file(self, prompt_type: str) -> Path:
        """获取 Prompt 文件路径"""
        return self.storage_path / f"{prompt_type}.json"

    def get_prompt(self, prompt_type: str) -> str:
        """获取当前版本的 Prompt"""
        if prompt_type in self.current_versions:
            return self.current_versions[prompt_type].content
        return self._get_default_prompt(prompt_type)

    def get_prompt_version_info(self, prompt_type: str) -> Dict[str, Any]:
        """获取 Prompt 版本信息"""
        version = self.current_versions.get(prompt_type)
        if not version:
            return {
                "prompt_type": prompt_type,
                "version_id": "default",
                "content": self._get_default_prompt(prompt_type),
                "created_at": datetime.now().isoformat(),
                "created_by": "system",
                "change_history": []
            }

        history = [v for v in self.change_history if v.prompt_type == prompt_type]
        history = sorted(history, key=lambda x: x.created_at, reverse=True)[:5]

        return {
            "version_id": version.version_id,
            "prompt_type": version.prompt_type,
            "content": version.content,
            "created_at": version.created_at.isoformat(),
            "created_by": version.created_by,
            "change_reason": version.change_reason,
            "change_source": version.change_source,
            "change_history": [
                {
                    "version_id": v.version_id,
                    "change_reason": v.change_reason,
                    "created_at": v.created_at.isoformat(),
                    "created_by": v.created_by
                }
                for v in history
            ]
        }

    async def update_prompt(
        self,
        prompt_type: str,
        new_content: str,
        change_reason: str,
        change_source: str = "manual",
        metrics_at_change: Optional[Dict] = None,
        created_by: str = "manual"
    ) -> PromptVersion:
        """
        更新 Prompt 版本
        """
        logger.info(f"更新 Prompt: type={prompt_type}, source={change_source}")

        # 创建新版本
        version = PromptVersion(
            version_id=f"{prompt_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            prompt_type=prompt_type,
            content=new_content,
            change_reason=change_reason,
            change_source=change_source,
            metrics_at_change=metrics_at_change or {},
            created_at=datetime.now(),
            created_by=created_by
        )

        # 保存旧版本到历史
        if prompt_type in self.current_versions:
            self.change_history.append(self.current_versions[prompt_type])

        # 更新当前版本
        self.current_versions[prompt_type] = version

        # 持久化
        await self._save_version(version)

        return version

    async def rollback(
        self,
        prompt_type: str,
        target_version_id: Optional[str] = None
    ) -> PromptVersion:
        """
        回滚 Prompt 到之前的版本
        """
        logger.info(f"回滚 Prompt: type={prompt_type}, target={target_version_id}")

        if target_version_id:
            # 找到指定版本
            target = None
            for v in self.change_history:
                if v.version_id == target_version_id:
                    target = v
                    break
            if not target:
                raise ValueError(f"版本不存在: {target_version_id}")
        else:
            # 回滚到上一个版本
            if self.change_history:
                # 找到该类型的最后一个版本
                for i in range(len(self.change_history) - 1, -1, -1):
                    if self.change_history[i].prompt_type == prompt_type:
                        target = self.change_history.pop(i)
                        break
                else:
                    raise ValueError("没有可回滚的版本")
            else:
                raise ValueError("没有可回滚的版本")

        # 更新当前版本
        self.current_versions[prompt_type] = target

        # 保存
        await self._save_version(target)

        return target

    def get_change_history(
        self,
        prompt_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """获取变更历史"""
        history = self.change_history
        if prompt_type:
            history = [v for v in history if v.prompt_type == prompt_type]

        history = sorted(history, key=lambda x: x.created_at, reverse=True)

        return [
            {
                "version_id": v.version_id,
                "prompt_type": v.prompt_type,
                "change_reason": v.change_reason,
                "change_source": v.change_source,
                "created_at": v.created_at.isoformat(),
                "created_by": v.created_by
            }
            for v in history[:limit]
        ]

    # ===== 预设的 Prompt 模板 =====

    def _get_default_prompt(self, prompt_type: str) -> str:
        """获取默认 Prompt 模板"""
        defaults = {
            "question_generation": """你是一位资深高中化学教师,擅长根据知识点生成高质量的化学练习题。

要求:
1. 题目科学性100%正确,化学方程式必须配平
2. 题目语言清晰,无歧义
3. 选项设置要有区分度
4. 注明题目考查的知识点
5. 适当设置陷阱选项考察学生易错点

返回格式（JSON）:
{
    "questions": [
        {
            "content": "题目正文",
            "options": ["A. 选项", "B. 选项", "C. 选项", "D. 选项"],
            "answer": "正确答案字母",
            "knowledge_points": ["知识点1", "知识点2"],
            "difficulty": "easy/medium/hard"
        }
    ]
}""",

            "question_audit": """你是一位高中化学教研专家,负责审核AI生成的化学题目是否合格。

审核维度:
1. 科学性: 题目内容/化学方程式/概念是否正确
2. 准确性: 知识点对应是否准确
3. 适当性: 难度是否适中,是否符合高中生水平
4. 陷阱设置: 陷阱选项是否合理

请严格审核,发现任何科学性错误必须指出。""",

            "learning_plan": """你是一位资深高中化学教师,擅长根据学生的学习情况制定个性化学习计划。

学习计划要求:
1. 针对学生的具体障碍类型制定干预策略
2. 结合薄弱知识点安排循序渐进的学习内容
3. 计划要具体可执行,包括每日/每周任务
4. 包含激励性话语,增强学生学习信心
5. 计划周期建议2-4周"""
        }
        return defaults.get(prompt_type, "")

    # ===== 内部方法 =====

    def _load_current_versions(self) -> None:
        """加载当前版本"""
        prompt_types = ["question_generation", "question_audit", "learning_plan"]

        for prompt_type in prompt_types:
            prompt_file = self._get_prompt_file(prompt_type)
            if prompt_file.exists():
                try:
                    with open(prompt_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.current_versions[prompt_type] = PromptVersion(
                            version_id=data["version_id"],
                            prompt_type=data["prompt_type"],
                            content=data["content"],
                            change_reason=data.get("change_reason", ""),
                            change_source=data.get("change_source", "manual"),
                            metrics_at_change=data.get("metrics_at_change", {}),
                            created_at=datetime.fromisoformat(data["created_at"]),
                            created_by=data["created_by"]
                        )
                except (json.JSONDecodeError, KeyError):
                    pass

    async def _save_version(self, version: PromptVersion) -> None:
        """保存版本到文件"""
        prompt_file = self._get_prompt_file(version.prompt_type)
        with open(prompt_file, "w", encoding="utf-8") as f:
            json.dump({
                "version_id": version.version_id,
                "prompt_type": version.prompt_type,
                "content": version.content,
                "change_reason": version.change_reason,
                "change_source": version.change_source,
                "metrics_at_change": version.metrics_at_change,
                "created_at": version.created_at.isoformat(),
                "created_by": version.created_by
            }, f, ensure_ascii=False, indent=2)
