"""
历年真题数据模型
基于PRD: 覆盖全国卷2022-2024 + 湖南卷2022-2024
"""
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class ExamRegion(str, Enum):
    """试卷来源地区"""
    NATIONAL = "全国卷"  # 全国卷
    HUNAN = "湖南卷"     # 湖南卷


class QuestionType(str, Enum):
    """题目类型"""
    SINGLE_CHOICE = "single_choice"    # 单选题
    MULTIPLE_CHOICE = "multiple_choice"  # 多选题
    FILL_BLANK = "fill_blank"          # 填空题
    SHORT_ANSWER = "short_answer"      # 简答题
    CALCULATION = "calculation"        # 计算题


class HistoricalQuestion(BaseModel):
    """历年真题结构"""
    exam_id: str               # 唯一ID
    source: str                # "全国卷2024"
    year: int                  # 2024
    region: str                # "全国卷"
    paper_name: str            # "2024年普通高等学校招生全国统一考试(甲卷)"
    question_number: str       # "T1", "T15" (卷面题号)
    original_number: str       # 原卷题号
    question_type: str         # 题目类型
    content: str               # 题目内容
    options: Optional[List[str]] = None  # 选项(如有)
    answer: str                # 参考答案
    analysis: Optional[str] = None  # 题目解析
    knowledge_points: List[str]  # 知识点列表
    difficulty: str            # easy/medium/hard
    discrimination: float     # 区分度 0-1
    score: int                 # 分值
    chapter: str               # 章节
    page_image: Optional[str] = None  # 试卷原图路径(如 figures/page_01.png)
    created_at: Optional[str] = None


class ExamPaper(BaseModel):
    """试卷结构"""
    paper_id: str
    source: str                # "全国卷2024"
    year: int
    region: str
    paper_name: str
    subject: str = "化学"
    total_score: int           # 总分
    question_count: int        # 题目数量
    exam_date: Optional[str] = None
    questions: List[HistoricalQuestion]


def get_sample_national_2024() -> List[HistoricalQuestion]:
    """样例: 2024年全国卷化学真题(部分)"""

    # ===== 选择题部分 =====
    questions = [
        # T1 化学与社会
        HistoricalQuestion(
            exam_id="nat_2024_t1",
            source="全国卷2024",
            year=2024,
            region="全国卷",
            paper_name="2024年普通高等学校招生全国统一考试化学",
            question_number="T1",
            original_number="1",
            question_type="single_choice",
            content="化学与生活密切相关。下列说法正确的是",
            options=[
                "A. 棉花、蚕丝都属于天然纤维",
                "B. 淀粉和油脂都是高分子化合物",
                "C. 维生素C具有还原性，可用作食品抗氧化剂",
                "D. 明矾净水原理是明矾与水反应生成沉淀"
            ],
            answer="C",
            analysis="A. 蚕丝是蛋白质，不是纤维；B. 油脂不是高分子化合物；"
            "D. 明矾净水是由于Al3+水解生成Al(OH)3胶体，吸附杂质",
            knowledge_points=["化学与STSE", "高分子化合物", "氧化还原", "盐类水解"],
            difficulty="easy",
            discrimination=0.45,
            score=6,
            chapter="化学与可持续发展"
        ),

        # T7 元素周期律
        HistoricalQuestion(
            exam_id="nat_2024_t7",
            source="全国卷2024",
            year=2024,
            region="全国卷",
            paper_name="2024年普通高等学校招生全国统一考试化学",
            question_number="T7",
            original_number="7",
            question_type="single_choice",
            content="根据元素周期表和元素周期律，下列说法正确的是",
            options=[
                "A. 同周期主族元素从左到右，原子半径逐渐增大",
                "B. 第IA族元素的金属性从上到下逐渐减弱",
                "C. 第VIA族元素的气态氢化物沸点从上到下逐渐升高",
                "D. 原子序数为34的元素位于第4周期第VIA族"
            ],
            answer="D",
            analysis="A. 同周期原子半径逐渐减小；B. 金属性增强；C. H2O由于氢键沸点反常高",
            knowledge_points=["元素周期律", "原子半径", "金属性", "氢键"],
            difficulty="medium",
            discrimination=0.58,
            score=6,
            chapter="物质结构 元素周期律"
        ),

        # T8 电解质溶液
        HistoricalQuestion(
            exam_id="nat_2024_t8",
            source="全国卷2024",
            year=2024,
            region="全国卷",
            paper_name="2024年普通高等学校招生全国统一考试化学",
            question_number="T8",
            original_number="8",
            question_type="single_choice",
            content="下列溶液中外加NaOH固体，恢复至原温度后，pH明显增大的是",
            options=[
                "A. 醋酸钠溶液",
                "B. 氯化铵溶液",
                "C. 饱和石灰水",
                "D. 碳酸钠溶液"
            ],
            answer="C",
            analysis="A. 生成醋酸，pH增大但不如C显著；B. 生成氨水，可能pH先增大后减小；"
            "C. Ca(OH)2溶解度随温度升高降低，NaOH加入使Ca(OH)2析出，pH降低；"
            "D. CO3 2-水解，pH增大",
            knowledge_points=["电解质溶液", "盐类水解", "水的离子积", "酸碱中和"],
            difficulty="hard",
            discrimination=0.65,
            score=6,
            chapter="电解质溶液"
        ),

        # T12 电化学
        HistoricalQuestion(
            exam_id="nat_2024_t12",
            source="全国卷2024",
            year=2024,
            region="全国卷",
            paper_name="2024年普通高等学校招生全国统一考试化学",
            question_number="T12",
            original_number="12",
            question_type="single_choice",
            content="某固态金属M制成的电极，电解稀硫酸溶液，一段时间后阳极区溶液pH下降。下列说法正确的是",
            options=[
                "A. 阳极反应: M - 2e⁻ → M²⁺",
                "B. 电解过程中，阴极区pH逐渐下降",
                "C. 电解后电路中转移电子数约为0.1mol时，析出H₂约2.24L",
                "D. 若将稀硫酸换成硫酸钠溶液，阳极区pH不变"
            ],
            answer="A",
            analysis="阳极金属M失电子变成M²⁺，阳极区H⁺消耗，pH上升；阴极2H⁺ + 2e⁻ → H₂↑，H⁺减少pH上升",
            knowledge_points=["电化学", "原电池", "电解池", "电极反应"],
            difficulty="hard",
            discrimination=0.68,
            score=6,
            chapter="电化学"
        ),

        # ===== 非选择题部分 =====

        # T26 物质结构推断
        HistoricalQuestion(
            exam_id="nat_2024_t26",
            source="全国卷2024",
            year=2024,
            region="全国卷",
            paper_name="2024年普通高等学校招生全国统一考试化学",
            question_number="T26",
            original_number="26",
            question_type="fill_blank",
            content="化合物X是一种重要的化工原料，其分子式为C₄H₈O₂。X能发生如下转化：",
            answer="(1) CH₃COOCH₃ 或其他合理答案 (2) 酯基 (3) 4",
            analysis="根据转化关系推断X为酯类化合物",
            knowledge_points=["有机化合物", "官能团", "酯化反应", "同分异构体"],
            difficulty="medium",
            discrimination=0.62,
            score=15,
            chapter="有机化学基础"
        ),

        # T28 化学反应原理综合
        HistoricalQuestion(
            exam_id="nat_2024_t28",
            source="全国卷2024",
            year=2024,
            region="全国卷",
            paper_name="2024年普通高等学校招生全国统一考试化学",
            question_number="T28",
            original_number="28",
            question_type="calculation",
            content="化学反应原理综合应用。回答下列问题：",
            answer="(1) ΔH = -196 kJ·mol⁻¹ (2) K = 1.8×10³ (3) 65%",
            analysis="盖斯定律计算反应热，平衡常数计算，转化率计算",
            knowledge_points=["化学反应速率", "化学平衡", "反应热", "勒夏特列原理"],
            difficulty="hard",
            discrimination=0.72,
            score=14,
            chapter="化学反应速率与平衡"
        ),
    ]

    return questions


def get_sample_hunan_2024() -> List[HistoricalQuestion]:
    """样例: 2024年湖南卷化学真题(部分)"""

    questions = [
        # T1 化学与STSE
        HistoricalQuestion(
            exam_id="hun_2024_t1",
            source="湖南卷2024",
            year=2024,
            region="湖南卷",
            paper_name="2024年湖南省普通高中学业水平选择性考试化学",
            question_number="T1",
            original_number="1",
            question_type="single_choice",
            content="化学与环境密切相关。下列说法错误的是",
            options=[
                "A. 汽车尾气中的NOx会形成光化学烟雾",
                "B. 工业废水中的重金属离子可用化学沉淀法除去",
                "C. 太阳能电池板的主要材料是SiO₂",
                "D. 垃圾分类有利于资源的回收利用"
            ],
            answer="C",
            analysis="太阳能电池板主要材料是Si，不是SiO₂",
            knowledge_points=["化学与环境", "大气污染", "污水处理", "半导体材料"],
            difficulty="easy",
            discrimination=0.40,
            score=3,
            chapter="化学与可持续发展"
        ),

        # T3 物质的量
        HistoricalQuestion(
            exam_id="hun_2024_t3",
            source="湖南卷2024",
            year=2024,
            region="湖南卷",
            paper_name="2024年湖南省普通高中学业水平选择性考试化学",
            question_number="T3",
            original_number="3",
            question_type="single_choice",
            content="设NA为阿伏伽德罗常数的值。下列说法正确的是",
            options=[
                "A. 1mol D₂O中含有的质子数为10NA",
                "B. 标准状况下，22.4L Cl₂溶于水转移电子数为NA",
                "C. 1L 0.1mol·L⁻¹ Na₂CO₃溶液中CO₃²⁻数目为0.1NA",
                "D. 56g Fe与足量稀盐酸反应生成H₂分子数为NA"
            ],
            answer="A",
            analysis="D₂O的摩尔质量为20g/mol，1mol含10mol质子",
            knowledge_points=["物质的量", "阿伏伽德罗常数", "气体摩尔体积", "氧化还原反应"],
            difficulty="medium",
            discrimination=0.55,
            score=3,
            chapter="化学计量"
        ),

        # T8 盐类水解
        HistoricalQuestion(
            exam_id="hun_2024_t8",
            source="湖南卷2024",
            year=2024,
            region="湖南卷",
            paper_name="2024年湖南省普通高中学业水平选择性考试化学",
            question_number="T8",
            original_number="8",
            question_type="single_choice",
            content="常温下，用0.1mol·L⁻¹ NaOH溶液滴定20mL 0.1mol·L⁻¹ CH₃COOH溶液，滴定曲线如下。下列说法正确的是",
            options=[
                "A. P点溶液中：c(CH₃COO⁻) > c(Na⁺) > c(H⁺) > c(OH⁻)",
                "B. Q点所示溶液中：c(Na⁺) = c(CH₃COO⁻) + c(CH₃COOH)",
                "C. 滴定过程中水的电离程度先增大后减小",
                "D. P点到Q点过程中，导电能力一定增强"
            ],
            answer="C",
            analysis="醋酸钠水解促进水电离，NaOH加入先中和醋酸，后OH⁻抑制水电离",
            knowledge_points=["盐类水解", "水的离子积", "酸碱中和滴定", "离子浓度比较"],
            difficulty="hard",
            discrimination=0.68,
            score=3,
            chapter="电解质溶液"
        ),

        # T14 电解池
        HistoricalQuestion(
            exam_id="hun_2024_t14",
            source="湖南卷2024",
            year=2024,
            region="湖南卷",
            paper_name="2024年湖南省普通高中学业水平选择性考试化学",
            question_number="T14",
            original_number="14",
            question_type="single_choice",
            content="用NaClO溶液处理含CN⁻的电镀废水，反应原理为：CN⁻ + ClO⁻ → CO₂ + N₂ + Cl⁻ + H₂O。下列说法正确的是",
            options=[
                "A. 该反应中C被氧化，N被还原",
                "B. 处理1mol CN⁻，消耗0.5mol ClO⁻",
                "C. CO₂的电子式为 :O::C::O:",
                "D. 该反应可用于处理汽车尾气"
            ],
            answer="A",
            analysis="CN⁻中C从+2升到+4被氧化，ClO⁻中Cl从+1降到-1被还原",
            knowledge_points=["氧化还原反应", "电化学", "电极反应", "电子式"],
            difficulty="medium",
            discrimination=0.58,
            score=3,
            chapter="氧化还原反应"
        ),

        # T18 化学反应速率与平衡
        HistoricalQuestion(
            exam_id="hun_2024_t18",
            source="湖南卷2024",
            year=2024,
            region="湖南卷",
            paper_name="2024年湖南省普通高中学业水平选择性考试化学",
            question_number="T18",
            original_number="18",
            question_type="calculation",
            content="为实现碳中和，工业上以CO₂和H₂为原料合成低碳烯烃，反应为：2CO₂(g) + 6H₂(g) ⇌ C₂H₄(g) + 4H₂O(g)。",
            answer="(1) ΔH < 0，ΔS > 0 (2) K = 1.5×10⁴ (3) 80%",
            analysis="利用ΔH和ΔS判断反应方向，计算平衡常数和转化率",
            knowledge_points=["化学反应速率", "化学平衡", "反应热", "勒夏特列原理", "化学平衡常数"],
            difficulty="hard",
            discrimination=0.70,
            score=12,
            chapter="化学反应速率与平衡"
        ),
    ]

    return questions
