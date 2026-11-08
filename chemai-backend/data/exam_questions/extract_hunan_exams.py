#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从PDF提取高考化学真题并转换为题库JSON格式
使用pdftotext命令行工具进行PDF文本提取
"""
import os
import re
import json
import subprocess
import glob
from typing import List, Dict, Optional, Tuple


def extract_text_from_pdf(pdf_path: str) -> str:
    """使用pdftotext提取PDF文本"""
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp_path = tmp.name

        # Use shell=True to properly handle the command
        cmd = f'pdftotext -layout -enc UTF-8 "{pdf_path}" "{tmp_path}"'
        os.system(cmd)

        with open(tmp_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        print(f"Error extracting {pdf_path}: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def clean_text(text: str) -> str:
    """清理文本"""
    if not text:
        return ""
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def detect_question_type(content: str, options: List[Dict]) -> str:
    """检测题型"""
    if options and len(options) >= 4:
        # Check if it might be multiple choice
        if any('正确' in content and '错误' in content for opt in options):
            return "single_choice"
        return "single_choice"
    if '填空' in content or '_______' in content or '______' in content:
        return "fill_blank"
    if '计算' in content or '计算题' in content:
        return "calculation"
    return "short_answer"


def detect_difficulty(content: str) -> str:
    """基于关键词检测难度"""
    hard_keywords = ['复杂', '困难', '难题', '竞赛', '综合', '探究', '设计实验', '复杂']
    easy_keywords = ['基础', '简单', '常识', '了解']

    content_lower = content.lower()
    if any(kw in content for kw in hard_keywords):
        return "hard"
    if any(kw in content for kw in easy_keywords):
        return "easy"
    return "medium"


def extract_knowledge_points(content: str) -> List[str]:
    """提取知识点"""
    kp_keywords = [
        ('氧化还原', ['氧化还原反应', '氧化剂', '还原剂', '氧化性', '还原性']),
        ('电解', ['电解', '电解池', '阳极', '阴极']),
        ('电离', ['电离', '电解质', '非电解质']),
        ('盐类水解', ['盐类水解', '水解']),
        ('沉淀', ['沉淀', '溶解度']),
        ('离子反应', ['离子反应', '离子共存', '离子方程式']),
        ('元素周期律', ['元素周期律', '原子结构', '化学键', '共价键', '离子键', '金属键']),
        ('有机物', ['有机物', '官能团', '取代反应', '加成反应', '消去反应']),
        ('酯化', ['酯化反应', '酯化']),
        ('中和', ['中和反应', '中和热']),
        ('羧酸', ['羧酸', '羧基']),
        ('醇', ['醇', '羟基']),
        ('醛', ['醛', '醛基']),
        ('化学平衡', ['化学平衡', '平衡移动', '勒夏特列', '反应速率', '平衡常数']),
        ('电化学', ['电化学', '原电池', '电极反应']),
        ('物质的量', ['物质的量', '阿伏加德罗', '摩尔', '浓度']),
        ('胶体', ['胶体', '分散系', '溶液', '浊液']),
        ('实验', ['实验', '制备', '检验', '分离', '提纯', '实验设计']),
        ('金属', ['金属', '碱金属', '铝', '铁', '铜']),
        ('非金属', ['非金属', '卤素', '氧族', '氮族', '硫', '氮', '硅', '氯']),
        ('热化学', ['热化学', '燃烧热', '反应热', '盖斯定律']),
        ('酸碱', ['酸碱', 'PH', '缓冲溶液', '盐溶液']),
        ('晶体', ['晶体', '晶胞', '原子晶体', '分子晶体', '离子晶体', '金属晶体']),
        ('化学与社会', ['化学与社会', 'STSE', '环境', '绿色化学', '可持续发展']),
        ('新能源', ['新能源', '太阳能', '氢能', '锂电池']),
        ('化工流程', ['工艺流程', '工业生产', '流程']),
    ]

    found = []
    for kp_name, keywords in kp_keywords:
        for kw in keywords:
            if kw in content:
                found.append(kp_name)
                break

    return list(set(found))[:5] if found else ['综合']


def parse_single_choice_questions(text: str, year: str, region: str) -> List[Dict]:
    """解析单选题"""
    questions = []
    lines = text.split('\n')

    current_question = None
    current_options = []
    q_num = None
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty and page numbers
        if not line:
            i += 1
            continue
        if re.match(r'^\d+\s*\|\s*\d+\s*页', line):
            i += 1
            continue
        if '注意事项' in line or '可能用到的相对原子质量' in line:
            i += 1
            continue
        if line.startswith('一、') or line.startswith('二、') or line.startswith('三、'):
            i += 1
            continue
        if '选择题' in line:
            i += 1
            continue

        # Detect question start - handle both regular and fullwidth periods
        # Format 1: "1.（3 分）在溶液中..." or "1．（3 分）在溶液中..."
        # Format 2: "1. 下列有关..." or "1． 下列有关..." (newer papers like 2021+ 湖南卷)
        match = re.match(r'^(\d+)[．\.]\s*（[^）]+）\s*(.+)', line)
        if not match:
            # Try format without parentheses (newer papers)
            match = re.match(r'^(\d+)[．\.]\s+([^A-D].+)', line)
        if match and not line.startswith(('A.', 'B.', 'C.', 'D.', 'A．', 'B．', 'C．', 'D．')):
            # Save previous question
            if current_question and q_num:
                q = build_question(current_question, current_options, year, region, q_num)
                if q:
                    questions.append(q)

            q_num = match.group(1)
            current_question = match.group(2)
            current_options = []
            i += 1
            continue

        # Detect options - handle both regular and fullwidth periods
        # Format: "A．NH4+..." or "A. NH4+..."
        opt_match = re.match(r'^([A-D])[．\.]\s*(.+)', line)
        if opt_match and current_question:
            current_options.append({
                'label': opt_match.group(1),
                'text': opt_match.group(2)
            })
            i += 1
            continue

        # Handle options that span multiple lines (for multiple choice)
        if current_question and len(current_options) >= 2:
            last_opt = current_options[-1]['text']
            # If last option doesn't end with proper punctuation, might continue
            if not last_opt.endswith(('.', '。', '，', '、')):
                if re.match(r'^[A-D]\s+', line) or re.match(r'^\s+[A-D]', line):
                    current_options[-1]['text'] += ' ' + line.strip()
                    i += 1
                    continue

        i += 1

    # Save last question
    if current_question and q_num:
        q = build_question(current_question, current_options, year, region, q_num)
        if q:
            questions.append(q)

    return questions


def build_question(content: str, options: List[Dict], year: str, source: str, q_num: str) -> Optional[Dict]:
    """构建题目JSON结构"""
    if not content or len(content) < 5:
        return None

    content = clean_text(content)
    q_type = detect_question_type(content, options)
    difficulty = detect_difficulty(content)
    knowledge_points = extract_knowledge_points(content)

    return {
        "exam_id": f"{source.lower().replace(' ', '')}_{year}_t{q_num}".replace(" ", "_"),
        "source": f"{source}{year}",
        "year": int(year),
        "region": source,
        "paper_name": f"{year}年{source}高考化学试卷",
        "question_number": f"T{q_num}",
        "original_number": str(q_num),
        "question_type": q_type,
        "content": content,
        "options": [f"{opt['label']}. {opt['text']}" for opt in options] if options else None,
        "answer": "",
        "analysis": "",
        "knowledge_points": knowledge_points,
        "difficulty": difficulty,
        "discrimination": 0.5,
        "score": 3,
        "chapter": knowledge_points[0] if knowledge_points else "综合"
    }


def extract_answers_from_analysis(text: str) -> Dict[int, Dict]:
    """从解析卷提取答案和分析"""
    answers = {}

    lines = text.split('\n')

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Match "【答案】X" pattern (answer on its own line)
        if '【答案】' in line_stripped:
            # Try to extract answer letter(s)
            match = re.search(r'【答案】\s*([A-D]+)', line_stripped)
            if match:
                answer = match.group(1)
                # Try to find question number from previous lines (look back up to 20 lines)
                q_num = None
                for j in range(i-1, max(i-20, -1), -1):
                    prev = lines[j].strip()
                    # Match various question number patterns
                    q_match = re.match(r'^(\d+)\.', prev)
                    if q_match:
                        q_num = int(q_match.group(1))
                        break

                if q_num:
                    answers[q_num] = {
                        'answer': answer,
                        'analysis': ''
                    }

    return answers


def merge_questions_with_answers(questions: List[Dict], answers: Dict[int, Dict]) -> List[Dict]:
    """合并题目和答案"""
    for q in questions:
        q_num = int(q.get('original_number', 0))
        if q_num in answers:
            q['answer'] = answers[q_num]['answer']
            if answers[q_num]['analysis']:
                q['analysis'] = answers[q_num]['analysis']
    return questions


def parse_exam_filename(filename: str) -> Tuple[str, str, str]:
    """从文件名解析考试信息"""
    year_match = re.search(r'(\d{4})年', filename)
    paper_type = "blank" if "空白卷" in filename else "analysis"

    year = year_match.group(1) if year_match else ""

    # Detect region by byte patterns (avoiding encoding issues)
    # "湖南" in UTF-8 is \xe6\xb9\x96\xe5\x8d\x97
    # "全国" in UTF-8 is \xe5\x85\xa8\xe5\x9b\xbd
    if b'\xe6\xb9\x96\xe5\x8d\x97' in filename.encode('utf-8') or '湖南' in filename:
        region = "湖南卷"
    elif b'\xe5\x85\xa8\xe5\x9b\xbd' in filename.encode('utf-8') or '全国' in filename:
        region = "全国卷"
    else:
        # Fallback: check for common patterns in garbled text
        if 'Ͼ' in filename or '���Ͼ' in filename:
            region = "湖南卷"
        else:
            region = "全国卷"

    return year, region, paper_type


def main():
    """主函数"""
    source_dir = "D:/BaiduNetdiskDownload/2008-2025·（湖南）化学高考真题"
    output_dir = "data/exam_questions"

    if not os.path.exists(source_dir):
        print(f"Source directory not found: {source_dir}")
        return

    pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
    if not pdf_files:
        print("No PDF files found!")
        return

    print(f"Found {len(pdf_files)} PDF files")

    # 按年份和类型处理
    exam_data = {}

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        year, region, paper_type = parse_exam_filename(filename)
        if not year:
            continue

        print(f"Processing: {filename}")

        text = extract_text_from_pdf(pdf_path)
        if not text or len(text) < 100:
            print(f"  Warning: Empty or very short text extracted")
            continue

        key = f"{year}_{region}"
        if key not in exam_data:
            exam_data[key] = {}

        exam_data[key][paper_type] = {
            'text': text,
            'year': year,
            'region': region,
            'filename': filename
        }

    # 解析并生成JSON
    os.makedirs(output_dir, exist_ok=True)

    total_questions = 0

    for key, data in exam_data.items():
        if 'blank' not in data:
            print(f"\n{key}: No blank paper, skipping")
            continue

        blank_text = data['blank']['text']
        year = data['blank']['year']
        region = data['blank']['region']

        print(f"\n{key}:")

        # 解析题目
        questions = parse_single_choice_questions(blank_text, year, region)
        print(f"  Found {len(questions)} questions from blank paper")

        # 从解析卷提取答案
        answers = {}
        if 'analysis' in data:
            answers = extract_answers_from_analysis(data['analysis']['text'])
            print(f"  Found {len(answers)} answers from analysis paper")

        # 合并答案
        questions = merge_questions_with_answers(questions, answers)

        if questions:
            # Use national_ or hunan_ prefix based on region
            region_prefix = "national" if region == "全国卷" else "hunan"
            output_file = os.path.join(output_dir, f"{region_prefix}_{year}_full.json")
            output_data = {
                "paper_name": f"{year}年{region}高考化学试卷",
                "region": region,
                "year": int(year),
                "total_score": 100,
                "exam_date": f"{year}-06-08",
                "questions": questions
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"  Saved: {output_file}")
            total_questions += len(questions)

    print(f"\n\nTotal questions extracted: {total_questions}")


if __name__ == "__main__":
    main()
