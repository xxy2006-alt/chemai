"""
基于知识图谱生成化学大题模板
用于扩充高考化学大题题库
"""
import json
import random

# 加载知识图谱
def load_knowledge_points():
    try:
        with open('data/knowledge_graph/knowledge_points.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

# 大题模板
LARGE_QUESTION_TEMPLATES = {
    "电解质溶液": {
        "topic": "电解质溶液",
        "templates": [
            {
                "content": "某盐溶液呈酸性、碱性或中性，请设计实验探究其原因。\n"
                "(1) 已知0.1mol/L的NaA溶液pH为8.5，判断HA是强酸还是弱酸；\n"
                "(2) 若该盐为Na2CO3，写出其水解的离子方程式；\n"
                "(3) 比较0.1mol/L Na2CO3和0.1mol/L NaHCO3溶液的pH大小并说明原因。",
                "answer": "(1) HA为弱酸\n(2) CO3²⁻ + H2O ⇌ HCO3⁻ + OH⁻\n(3) Na2CO3 > NaHCO3，因为CO3²⁻水解程度更大",
                "analysis": "本题考察盐类水解原理。NaA溶液呈碱性说明A⁻发 水解，需通过pH判断HA酸性强弱。",
                "knowledge_points": ["盐类水解", "水解离子方程式", "水解程度比较"],
                "difficulty": "hard"
            },
            {
                "content": "实验室可用Na2CO3和盐酸反应制备CO2。\n"
                "(1) 若初始浓度均为0.1mol/L，计算反应后溶液中的c(CO3²⁻)、c(HCO3⁻)、c(H2CO3)；\n"
                "(2) 已知H2CO3的Ka1=4.3×10⁻⁷，Ka2=5.6×10⁻¹¹，计算该反应的平衡常数；\n"
                "(3) 判断加入CaCl2溶液是否能产生CaCO3沉淀( Ksp=3.4×10⁻⁹)。",
                "answer": "(1) 计算略\n(2) K = Ka1/Ka2\n(3) 能产生沉淀",
                "analysis": "本题综合考察弱酸电离和沉淀溶解平衡。",
                "knowledge_points": ["电离常数", "沉淀溶解平衡", "离子浓度计算"],
                "difficulty": "hard"
            }
        ]
    },
    "原电池": {
        "topic": "原电池",
        "templates": [
            {
                "content": "某学习小组设计如图所示装置进行原电池原理探究：\n"
                "(1) 电极材料：a为Zn片，b为Cu片；\n"
                "(2) 电解质溶液：0.1mol/L NaCl溶液\n"
                "请回答：\n"
                "① 标明正负极，写出负极反应方程式；\n"
                "② 若工作一段时间后，溶液pH如何变化？\n"
                "③ 若将NaCl换成0.1mol/L HCl，电流强度如何变化？",
                "answer": "① 负极：Zn - 2e⁻ = Zn²⁺；② pH升高；③ 电流强度增大",
                "analysis": "本题考察原电池电极反应。Zn-Cu原电池中Zn为负极失去电子，溶液pH因OH⁻生成而升高。",
                "knowledge_points": ["原电池原理", "电极反应", "pH变化"],
                "difficulty": "medium"
            },
            {
                "content": "新型高能电池锂空气电池引起广泛关注。\n"
                "(1) 写出锂空气电池放电时的正极反应方程式；\n"
                "(2) 若电池的电动势为3.0V，计算其理论能量密度；\n"
                "(3) 为提高电池性能，常加入有机电解液，说明有机电解液的作用。",
                "answer": "(1) O2 + 4Li⁺ + 4e⁻ = 2Li2O\n(2) 计算略\n(3) 传导离子，隔绝空气",
                "analysis": "本题考察新型电池。锂空气电池是近年研究热点，结合原电池原理和电化学知识。",
                "knowledge_points": ["原电池", "电化学计算", "电池原理"],
                "difficulty": "hard"
            }
        ]
    },
    "化学平衡": {
        "topic": "化学平衡",
        "templates": [
            {
                "content": "在密闭容器中发生反应：N2O4(g) ⇌ 2NO2(g)，ΔH>0。\n"
                "(1) 起始时N2O4的浓度为1.0mol/L，达到平衡时NO2的浓度为0.6mol/L，计算该温度下的平衡常数；\n"
                "(2) 若温度升高，平衡如何移动？\n"
                "(3) 若压缩体积使压强增大，NO2的体积分数如何变化？",
                "answer": "(1) K = 0.36\n(2) 向正反应方向移动\n(3) 减小",
                "analysis": "本题考察化学平衡计算和勒夏特列原理。",
                "knowledge_points": ["化学平衡常数", "平衡移动方向", "勒夏特列原理"],
                "difficulty": "medium"
            },
            {
                "content": "工业合成氨反应：N2 + 3H2 ⇌ 2NH3，ΔH<0。\n"
                "(1) 在一定条件下，N2的转化率为25%，H2的转化率为20%，求平衡常数；\n"
                "(2) 实际生产为何采用高温高压？\n"
                "(3) 画出该反应的速率-温度关系图并说明。",
                "answer": "(1) 计算略\n(2) 综合考虑反应速率和平衡移动\n(3) 图像分析略",
                "analysis": "本题考察合成氨工业条件选择。",
                "knowledge_points": ["化学平衡", "转化率计算", "反应条件选择"],
                "difficulty": "hard"
            }
        ]
    },
    "离子反应": {
        "topic": "离子反应",
        "templates": [
            {
                "content": "某混合溶液中可能含有Na⁺、Mg²⁺、Al³⁺、Fe³⁺、Cl⁻、SO4²⁻、CO3²⁻等离子。\n"
                "(1) 取少量溶液加入BaCl2溶液，生成白色沉淀，说明什么？\n"
                "(2) 若向原溶液中加入过量NaOH溶液，先产生沉淀后部分溶解，写出相关离子方程式；\n"
                "(3) 如何检验Cl⁻的存在？",
                "answer": "(1) 含有SO4²⁻或SO3²⁻\n"
                "(2) Al³⁺ + 3OH⁻ = Al(OH)3↓；Al(OH)3 + OH⁻ = AlO2⁻ + H2O\n"
                "(3) 加AgNO3和HNO3",
                "analysis": "本题考察离子检验和推断。",
                "knowledge_points": ["离子检验", "离子方程式", "离子共存"],
                "difficulty": "medium"
            }
        ]
    },
    "有机化合物": {
        "topic": "有机化合物",
        "templates": [
            {
                "content": "有机物A的分子式为C3H6O2，具有愉快的气味。\n"
                "(1) 若A能与NaHCO3反应产生气体，确定A的结构简式；\n"
                "(2) 写出A与乙醇反应的方程式；\n"
                "(3) 若A的同分异构体B能发生银镜反应，写出B的结构简式。",
                "answer": "(1) CH3CH2COOH\n(2) CH3CH2COOH + C2H5OH ⇌ CH3CH2COOC2H5 + H2O\n(3) HCOOCH2CH3",
                "analysis": "本题考察羧酸和酯的性质。",
                "knowledge_points": ["官能团性质", "同分异构体", "酯化反应"],
                "difficulty": "medium"
            },
            {
                "content": "化合物X(C4H8O2)是食醋的主要成分之一。\n"
                "(1) 写出X的结构简式及官能团名称；\n"
                "(2) X与足量NaOH溶液反应的方程式；\n"
                "(3) X的同分异构体中能发生水解反应且产物能发生银镜反应的共有几种？",
                "answer": "(1) CH3COOH，羧基\n(2) CH3COOH + NaOH → CH3COONa + H2O\n(3) 2种",
                "analysis": "本题考察羧酸和酯的性质及同分异构体。",
                "knowledge_points": ["羧酸", "酯的水解", "同分异构体"],
                "difficulty": "medium"
            }
        ]
    },
    "元素周期律": {
        "topic": "元素周期律",
        "templates": [
            {
                "content": "下表是元素周期表的一部分，标出了原子序数1-20的部分元素。\n"
                "(1) 写出原子序数为11、17的元素在周期表中的位置；\n"
                "(2) 比较Na、Mg、Al的原子半径和离子半径大小；\n"
                "(3) 若原子序数为11的元素与Cl形成化合物，判断化合物类型和晶体类型。",
                "answer": "(1) Na：第三周期IA族；Cl：第三周期VIIA族\n"
                "(2) 原子半径Na>Mg>Al；离子半径Na⁺>Mg²⁺>Al³⁺\n"
                "(3) 离子化合物，离子晶体",
                "analysis": "本题考察原子结构和元素周期律。",
                "knowledge_points": ["原子结构", "元素周期表", "晶体类型"],
                "difficulty": "easy"
            }
        ]
    },
    "化学反应速率": {
        "topic": "化学反应速率",
        "templates": [
            {
                "content": "在2L密闭容器中，N2与H2反应生成NH3，3秒后NH3的浓度增加了0.6mol/L。\n"
                "(1) 计算该时间段内N2、H2、NH3的反应速率；\n"
                "(2) 若温度升高，反应速率如何变化？\n"
                "(3) 若使用催化剂，活化能如何变化？",
                "answer": "(1) v(N2)=0.1mol/(L·s)，v(H2)=0.3mol/(L·s)，v(NH3)=0.2mol/(L·s)\n(2) 增大\n(3) 降低",
                "analysis": "本题考察化学反应速率计算和影响因素。",
                "knowledge_points": ["化学反应速率", "速率计算", "影响速率因素"],
                "difficulty": "medium"
            }
        ]
    }
}


def generate_large_questions():
    """生成大题数据"""
    print("=" * 60)
    print("基于知识图谱生成化学大题")
    print("=" * 60)

    kps = load_knowledge_points()
    print(f"已加载 {len(kps)} 个知识点")

    all_questions = []

    for topic, data in LARGE_QUESTION_TEMPLATES.items():
        for i, template in enumerate(data["templates"]):
            q = {
                "exam_id": f"large_{topic}_{i+1}",
                "source": f"知识图谱生成-{topic}",
                "year": 2025,
                "region": "化学大题库",
                "paper_name": f"化学大题练习-{topic}",
                "question_number": f"L{i+1}",
                "original_number": f"{i+1}",
                "question_type": "short_answer" if "计算" not in template["content"] else "calculation",
                "content": template["content"],
                "options": None,
                "answer": template["answer"],
                "analysis": template["analysis"],
                "knowledge_points": template["knowledge_points"],
                "difficulty": template["difficulty"],
                "discrimination": 0.5,
                "score": 15,
                "chapter": topic
            }
            all_questions.append(q)

    # 添加更多基于知识点的变式题
    for kp_name, kp_data in list(kps.items())[:10]:
        for i in range(2):
            q = {
                "exam_id": f"kp_{kp_name}_{i+1}",
                "source": f"知识点变式-{kp_name}",
                "year": 2025,
                "region": "化学题库",
                "paper_name": f"化学练习-{kp_name}",
                "question_number": f"V{i+1}",
                "original_number": f"{i+1}",
                "question_type": random.choice(["short_answer", "calculation"]),
                "content": f"【{kp_data['description']}】\n"
                f"根据以下信息回答问题：\n"
                f"(1) 解释{kp_name}的基本概念；\n"
                f"(2) 列举其在生活中的一个应用；\n"
                f"(3) 写出相关的化学反应方程式。",
                "options": None,
                "answer": "(1)(2)(3) 答案见解析",
                "analysis": f"本题考察{kp_name}相关知识。{kp_data.get('description', '')}",
                "knowledge_points": [kp_name] + kp_data.get("related_kps", [])[:2],
                "difficulty": kp_data.get("difficulty", "medium"),
                "discrimination": 0.5,
                "score": 12,
                "chapter": kp_data.get("category", kp_name)
            }
            all_questions.append(q)

    print(f"\n共生成 {len(all_questions)} 道大题")

    # 保存到文件
    output = {
        "paper_name": "2025年化学大题精选",
        "region": "题库扩充",
        "year": 2025,
        "total_score": 100,
        "exam_date": "2025-01-01",
        "questions": all_questions
    }

    output_file = "data/exam_questions/large_questions_2025.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"已保存到: {output_file}")

    return all_questions


if __name__ == "__main__":
    generate_large_questions()
