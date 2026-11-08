"""
真题数据自动生成脚本
使用LLM自动生成带标注的高中化学真题数据
解决: 外部数据集不可用的问题

使用方法:
    python generate_exams.py --generate --count 30
    python generate_exams.py --fill-template national_2023 --count 30
"""
import json
import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Optional

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_service import QwenService
from app.core.config import settings


# 已有关键知识点列表 (用于生成题目)
CHEMISTRY_KNOWLEDGE_POINTS = [
    # 电解质溶液
    "电解质溶液", "电离", "盐类水解", "水的离子积", "电离常数",
    "离子反应", "离子共存", "离子方程式",

    # 氧化还原
    "氧化还原反应", "氧化剂", "还原剂", "电子转移", "电极反应",

    # 电化学
    "原电池", "电解池", "金属腐蚀", "电镀", "阳极", "阴极",

    # 物质结构
    "元素周期律", "原子结构", "离子半径", "电负性",
    "共价键", "离子键", "金属键", "分子间作用力", "氢键",
    "杂化轨道", " sp3杂化", " sp2杂化", " sp杂化",

    # 化学反应速率与平衡
    "化学反应速率", "化学平衡", "勒夏特列原理", "平衡常数",
    "转化率", "反应热", "盖斯定律", "活化能",

    # 有机化学
    "有机化合物", "官能团", "同分异构体", "取代反应", "加成反应",
    "消去反应", "酯化反应", "水解反应", "银镜反应",
    "烷烃", "烯烃", "炔烃", "芳香烃", "醇", "醛", "羧酸", "酯",

    # 化学计量
    "物质的量", "阿伏伽德罗常数", "摩尔质量", "气体摩尔体积",
    "物质的量浓度", "质量分数",

    # 实验
    "化学实验", "物质的分离", "物质的检验", "常见气体制备",
]


class ExamGenerator:
    """
    历年真题自动生成器
    基于LLM生成结构化标注的化学真题
    """

    SYSTEM_PROMPT = """你是一位资深高中化学教研专家，擅长将高考真题转化为结构化JSON数据。

请根据给定的知识点和年份，生成一道高考风格的选择题。

要求：
1. 题目科学性100%正确
2. 选项设置有区分度（2-3个干扰选项）
3. 陷阱选项要符合学生常见错误
4. 标注的知识点要准确

返回格式（JSON）:
{
    "exam_id": "自动生成唯一ID",
    "source": "全国卷2023 或 湖南卷2023",
    "year": 2023,
    "region": "全国卷 或 湖南卷",
    "paper_name": "2023年普通高等学校招生全国统一考试化学",
    "question_number": "T7",
    "original_number": "7",
    "question_type": "single_choice",
    "content": "题目正文",
    "options": ["A. 选项内容", "B. 选项内容", "C. 选项内容", "D. 选项内容"],
    "answer": "正确答案字母",
    "analysis": "详细解析",
    "knowledge_points": ["知识点1", "知识点2"],
    "difficulty": "easy/medium/hard",
    "discrimination": 0.0-1.0之间的数,
    "score": 分值,
    "chapter": "章节名称"
}"""

    def __init__(self):
        self.llm = QwenService()
        self.generated_count = 0

    def generate_single_question(
        self,
        knowledge_points: List[str],
        year: int,
        region: str,
        difficulty: str = "medium"
    ) -> Optional[Dict]:
        """生成单道题目"""
        prompt = f"""请为以下知识点生成一道{year}年高考风格的化学单选题:

知识点: {', '.join(knowledge_points)}
难度: {difficulty}

请直接返回JSON，不要有其他文字:"""

        result = self.llm.generate_text(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=1500
        )

        if not result["success"]:
            print(f"生成失败: {result.get('error', 'Unknown error')}")
            return None

        try:
            content = result["content"]
            # 尝试提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            question_data = json.loads(content.strip())

            # 补充必填字段
            question_data["year"] = year
            question_data["region"] = region
            question_data["source"] = f"{region}{year}"
            question_data["paper_name"] = f"{year}年{'普通高等学校招生全国统一考试' if region == '全国卷' else '湖南省普通高中学业水平选择性考试'}化学"

            self.generated_count += 1
            return question_data

        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"原始内容: {result['content'][:200]}")
            return None

    def generate_exam_paper(
        self,
        year: int,
        region: str,
        count: int = 20,
        difficulty_distribution: Dict[str, int] = None
    ) -> List[Dict]:
        """
        生成一套试卷的题目
        difficulty_distribution: {"easy": 5, "medium": 10, "hard": 5}
        """
        if difficulty_distribution is None:
            difficulty_distribution = {"easy": 5, "medium": 12, "hard": 3}

        questions = []

        for difficulty, num in difficulty_distribution.items():
            for i in range(num):
                # 随机选择1-2个知识点
                import random
                kps = random.sample(CHEMISTRY_KNOWLEDGE_POINTS, min(2, len(CHEMISTRY_KNOWLEDGE_POINTS)))

                question = self.generate_single_question(
                    knowledge_points=kps,
                    year=year,
                    region=region,
                    difficulty=difficulty
                )

                if question:
                    question["question_number"] = f"T{len(questions) + 1}"
                    question["original_number"] = str(len(questions) + 1)
                    question["score"] = 6 if difficulty == "easy" else (6 if difficulty == "medium" else 6)
                    questions.append(question)
                    print(f"  [{len(questions)}/{count}] 生成: {question.get('content', '')[:30]}...")

                if len(questions) >= count:
                    break

            if len(questions) >= count:
                break

        return questions


def generate_with_template(
    source: str,
    year: int,
    region: str,
    count: int = 20
) -> Dict:
    """
    使用模板生成真题数据文件
    """
    generator = ExamGenerator()

    print(f"\n开始生成 {source} 真题数据 ({count}题)...")
    print(f"知识点覆盖: {len(CHEMISTRY_KNOWLEDGE_POINTS)} 个")

    questions = generator.generate_exam_paper(
        year=year,
        region=region,
        count=count
    )

    paper_name = f"{year}年{'普通高等学校招生全国统一考试' if region == '全国卷' else '湖南省普通高中学业水平选择性考试'}化学"

    paper_data = {
        "paper_name": paper_name,
        "region": region,
        "year": year,
        "total_score": 100,
        "exam_date": f"{year}-06-08" if region == "全国卷" else f"{year}-06-09",
        "questions": questions
    }

    return paper_data


def fill_existing_template(source: str, year: int, region: str, count: int = 20):
    """
    填充现有模板文件
    """
    generator = ExamGenerator()

    # 读取现有模板
    template_file = os.path.join(
        settings.EXAM_QUESTIONS_PATH,
        f"{source.lower().replace(' ', '_').replace('全国卷', 'national').replace('湖南卷', 'hunan')}.json"
    )

    # 如果文件不存在，创建新的
    if not os.path.exists(template_file):
        data = {
            "paper_name": f"{year}年{'普通高等学校招生全国统一考试' if region == '全国卷' else '湖南省普通高中学业水平选择性考试'}化学",
            "region": region,
            "year": year,
            "total_score": 100,
            "questions": []
        }
    else:
        with open(template_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    print(f"\n当前已有 {len(data.get('questions', []))} 题")
    print(f"开始生成 {count} 题...")

    new_questions = generator.generate_exam_paper(year=year, region=region, count=count)

    data["questions"] = data.get("questions", []) + new_questions
    data["total_score"] = len(data["questions"]) * 6  # 假设每题6分

    # 保存
    with open(template_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n已保存到: {template_file}")
    print(f"总计 {len(data['questions'])} 题")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="高中化学真题自动生成")
    parser.add_argument("--generate", action="store_true", help="生成新真题数据")
    parser.add_argument("--fill-template", choices=["national_2023", "hunan_2023", "national_2022", "hunan_2022"],
                       help="填充指定模板")
    parser.add_argument("--count", type=int, default=20, help="生成题目数量")
    parser.add_argument("--year", type=int, help="指定年份")
    parser.add_argument("--region", choices=["全国卷", "湖南卷"], help="指定地区")

    args = parser.parse_args()

    if args.fill_template:
        # 解析模板名称
        parts = args.fill_template.split("_")
        region = "全国卷" if parts[0] == "national" else "湖南卷"
        year = int(parts[1])

        fill_existing_template(
            source=args.fill_template,
            year=year,
            region=region,
            count=args.count
        )

    elif args.generate:
        # 交互式生成
        year = args.year or int(input("请输入年份 (2022-2024): ") or "2024")
        region = args.region or input("请输入地区 (全国卷/湖南卷): ") or "全国卷"

        data = generate_with_template(
            source=f"{region}{year}",
            year=year,
            region=region,
            count=args.count
        )

        # 保存
        filename = f"national_{year}.json" if region == "全国卷" else f"hunan_{year}.json"
        output_path = os.path.join(settings.EXAM_QUESTIONS_PATH, filename)

        os.makedirs(settings.EXAM_QUESTIONS_PATH, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n已保存到: {output_path}")
        print(f"共生成 {len(data['questions'])} 题")

    else:
        parser.print_help()
        print("\n示例:")
        print("  # 生成20题填充到2023年全国卷模板")
        print("  python generate_exams.py --fill-template national_2023 --count 20")
        print()
        print("  # 交互式生成2024年湖南卷20题")
        print("  python generate_exams.py --generate --year 2024 --region 湖南卷 --count 20")
