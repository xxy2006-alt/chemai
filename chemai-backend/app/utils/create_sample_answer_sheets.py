"""
生成更多示例答题卡
用于OCR/MinerU/多模态测试
"""
import os
from PIL import Image, ImageDraw, ImageFont
import random

SAMPLE_DIR = "data/sample_answer_sheets"
os.makedirs(SAMPLE_DIR, exist_ok=True)

CLASS1_NAMES = [
    "周翔", "危恩泽", "刘博晨", "曾妍", "吴溪", "姜媛媛", "唐平浩", "陈玥玚",
    "吴林峰", "郑晓峰", "王秀英", "李俊杰", "张雪梅", "刘佳伟", "陈思思", "杨浩然",
    "黄雨彤", "周涛", "吴敏", "郑建华", "王磊", "李婷", "张勇", "刘芳", "陈志强",
    "杨超", "黄丽", "周伟", "吴艳", "郑云", "王强", "李娟", "张强", "刘军"
]

CLASS2_NAMES = [
    "陈伟", "林思琪", "黄志强", "周秀兰", "吴浩宇", "郑雅婷", "王志强", "李雅静",
    "张俊杰", "刘思远", "陈雨萱", "杨浩然", "黄静怡", "周子轩", "吴秀英", "郑佳伟",
    "王思思", "李浩然", "张雨彤", "刘涛", "陈敏", "杨建华", "黄磊", "周婷",
    "吴勇", "郑芳", "王超", "李艳", "张云", "刘强", "陈娟", "杨军"
]


def create_answer_sheet_image(config, student_index, quality, draw_border=True):
    """创建答题卡图片，返回PIL Image对象"""
    width, height = 850, 1100
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("msyh.ttc", 20)
        font_medium = ImageFont.truetype("msyh.ttc", 14)
        font_small = ImageFont.truetype("msyh.ttc", 12)
    except Exception:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    y = 20
    draw.text((width//2 - 200, y), "长沙市某中学 2026-2027学年第一学期", fill='black', font=font_large)
    y += 35
    draw.text((width//2 - 120, y), config["name"], fill='black', font=font_medium)
    y += 40

    # 考生信息框
    draw.rectangle([50, y, width-50, y+60], outline='black', width=2)
    if config["class_id"] == "class_2025_1":
        student_name = CLASS1_NAMES[student_index % len(CLASS1_NAMES)]
    else:
        student_name = CLASS2_NAMES[student_index % len(CLASS2_NAMES)]
    student_id = f"20261{config['class_id'][-1]}0{student_index+1:02d}"

    draw.text((60, y+10), f"班级: {config['class']}", fill='black', font=font_medium)
    draw.text((60, y+35), f"姓名: {student_name}", fill='black', font=font_medium)
    draw.text((450, y+10), f"学号: {student_id}", fill='black', font=font_medium)
    draw.text((450, y+35), f"日期: {config['date']}", fill='black', font=font_medium)
    y += 80

    draw.text((50, y), "请在以下区域作答:", fill='black', font=font_medium)
    y += 30

    # 选择题
    draw.text((50, y), "一、选择题 (共12题，每题6分)", fill='black', font=font_medium)
    y += 30

    options = ['A', 'B', 'C', 'D']
    start_y = y

    # 根据质量确定标记模式
    if quality == "clean":
        marked = [3, 7, 11] if student_index % 3 == 0 else [5, 9] if student_index % 2 == 0 else [2]
    elif quality == "normal":
        marked = [i for i in range(1, 13) if random.random() < 0.5]
    elif quality == "messy":
        marked = [i for i in range(1, 13) if random.random() < 0.8]
    else:
        marked = [i for i in range(1, 13) if random.random() < 0.9]

    for q in range(1, 13):
        row = (q - 1) // 4
        col = (q - 1) % 4
        x = 60 + col * 180
        y_pos = start_y + row * 35

        draw.text((x, y_pos), f"T{q}:", fill='black', font=font_small)

        for i, opt in enumerate(options):
            ox = x + 35 + i * 40
            draw.ellipse([ox, y_pos, ox+25, y_pos+25], outline='black', width=1)
            if q in marked:
                if quality in ["messy", "very_messy"] and random.random() < 0.3:
                    draw.line([(ox, y_pos), (ox+25, y_pos+25)], fill='red', width=1)
                    draw.line([(ox+25, y_pos), (ox, y_pos+25)], fill='red', width=1)
                    ox2 = ox + 40 if i < 3 else ox - 40
                    draw.ellipse([ox2, y_pos, ox2+25, y_pos+25], outline='black', width=2)
                    draw.text((ox2+7, y_pos+3), options[(i+1)%4], fill='black', font=font_small)
                else:
                    draw.text((ox+7, y_pos+3), opt, fill='black', font=font_small)

    y = start_y + 4 * 35 + 20
    draw.text((50, y), "二、非选择题 (共6题，每题14分)", fill='black', font=font_medium)
    y += 30

    for q in range(13, 19):
        draw.rectangle([50, y, width-50, y+60], outline='black', width=1)
        draw.text((55, y+5), f"T{q}:", fill='gray', font=font_small)

        if quality in ["normal", "messy", "very_messy"]:
            lines_count = random.randint(2, 4)
            for li in range(lines_count):
                line_y = y + 20 + li * 12
                line_len = random.randint(200, 500) if quality == "messy" else random.randint(300, 600)
                if quality == "very_messy":
                    for seg in range(line_len // 20):
                        sx = 60 + seg * 20
                        draw.arc([sx, line_y, sx+18, line_y+10], 0, 180, fill='gray', width=1)
                else:
                    draw.line([(60, line_y), (60 + line_len, line_y)], fill='lightgray', width=1)

        if quality in ["messy", "very_messy"] and random.random() < 0.4:
            ly = y + random.randint(20, 40)
            draw.line([(60, ly), (300, ly)], fill='red', width=1)
        y += 70

    y += 20
    draw.rectangle([50, y, width-50, y+50], outline='black', width=2)
    draw.text((60, y+10), "评分区:", fill='gray', font=font_small)
    draw.text((60, y+30), "总分:", fill='black', font=font_medium)

    return img, student_name, student_id


def generate_all_samples():
    print("=" * 60)
    print("生成更多示例答题卡")
    print("=" * 60)

    # 考试配置
    exams = [
        {"name": "高一化学月考（一）", "date": "2025年10月15日", "class": "2419班", "class_id": "class_2025_1"},
        {"name": "高一化学月考（二）", "date": "2025年11月20日", "class": "2419班", "class_id": "class_2025_1"},
        {"name": "高一化学期中考试", "date": "2025年11月30日", "class": "2419班", "class_id": "class_2025_1"},
        {"name": "高一化学期末考试", "date": "2025年12月28日", "class": "2419班", "class_id": "class_2025_1"},
        {"name": "高一化学月考（一）", "date": "2025年10月15日", "class": "2420班", "class_id": "class_2025_2"},
        {"name": "高一化学月考（二）", "date": "2025年11月20日", "class": "2420班", "class_id": "class_2025_2"},
        {"name": "高一化学期中考试", "date": "2025年11月30日", "class": "2420班", "class_id": "class_2025_2"},
        {"name": "高一化学期末考试", "date": "2025年12月28日", "class": "2420班", "class_id": "class_2025_2"},
    ]

    qualities = ["clean", "normal", "messy", "very_messy"]
    count = 0

    for exam in exams:
        class_num = "1" if exam["class_id"] == "class_2025_1" else "2"

        for qi, quality in enumerate(qualities):
            # 每种考试每个班级每个质量生成2个样本
            for i in range(2):
                student_idx = (count * 3 + qi * 7 + i) % 34

                img, name, sid = create_answer_sheet_image(exam, student_idx, quality)

                # PNG文件名
                exam_idx = len([e for e in exams[:exams.index(exam)] if e['class_id'] == exam['class_id']]) + 1
                png_name = f"c{class_num}_exam{exam_idx}_{quality}_{i+1}.png"
                img.save(f"{SAMPLE_DIR}/{png_name}")

                # PDF文件名
                pdf_name = f"c{class_num}_exam{exam_idx}_{quality}_{i+1}.pdf"
                img.save(f"{SAMPLE_DIR}/{pdf_name}", "PDF", resolution=100.0)

                print(f"生成: {png_name} ({name})")
                count += 1

    print(f"\n共生成 {count * 2} 个文件 (PNG+PDF)")
    return count


if __name__ == "__main__":
    generate_all_samples()

    print("\n" + "=" * 60)
    print("文件列表:")
    files = sorted(os.listdir(SAMPLE_DIR))
    print(f"共 {len(files)} 个文件:")
    for f in files:
        fpath = os.path.join(SAMPLE_DIR, f)
        size = os.path.getsize(fpath)
        print(f"  {f} ({size:,} bytes)")
    print("=" * 60)
