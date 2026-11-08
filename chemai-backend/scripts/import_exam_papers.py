"""
真题导入脚本 — 百度OCR → LLM结构化 → JSON + 数据库

处理 2020-2025 年高考化学解析卷，按试卷分类存储。

用法:
  python scripts/import_exam_papers.py            # 全量导入
  python scripts/import_exam_papers.py --dry-run  # 只看不做
  python scripts/import_exam_papers.py --year 2024  # 单年
"""
import sys
import os
import json
import re
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 配置 ──
PDF_DIR = r"D:\BaiduNetdiskDownload\2008-2025·（湖南）化学高考真题"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "exam_questions")
YEARS = list(range(2020, 2026))  # 2020-2025

# ── 找出目标 PDF ──

def find_parsed_pdfs():
    """返回 [(region, year, pdf_path, pdf_name), ...] 的解析卷列表"""
    results = []
    for root, dirs, files in os.walk(PDF_DIR):
        for f in files:
            if not f.endswith('.pdf'):
                continue
            if '解析' not in f and '答案' not in f:
                continue
            # 提取年份
            year_match = re.search(r'20(\d{2})', f)
            if not year_match:
                continue
            year = 2000 + int(year_match.group(1))
            if year not in YEARS:
                continue
            # 提取地区
            if '湖南' in f or '湖南卷' in f:
                region = '湖南卷'
            elif '全国' in f or '新课标' in f:
                region = '全国卷'
            else:
                region = '全国卷'
            results.append((region, year, os.path.join(root, f), f))
    results.sort(key=lambda x: (x[1], x[0]))
    return results


# ── PDF 转图片 ──

def pdf_to_images(pdf_path, dpi=150):
    """PyMuPDF 逐页转 PNG，返回 [(page_num, image_bytes), ...]"""
    import fitz
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(doc.page_count):
        pix = doc[i].get_pixmap(dpi=dpi)
        pages.append((i + 1, pix.tobytes('png')))
    doc.close()
    return pages


# ── OCR ──

def ocr_page(image_bytes):
    """百度 OCR 单页"""
    from app.services.ocr_service import ocr_service
    # Ensure env vars loaded
    if not ocr_service.enabled:
        ocr_service.baidu_key = os.getenv("BAIDU_OCR_API_KEY", "")
        ocr_service.baidu_secret = os.getenv("BAIDU_OCR_SECRET_KEY", "")
        ocr_service.enabled = bool(ocr_service.baidu_key and ocr_service.baidu_secret)

    result = ocr_service._call_baidu_ocr(image_bytes)
    if result.get('success'):
        return result.get('raw_text', '')
    return f"[OCR FAILED: {result.get('error', 'unknown')}]"


# ── LLM 结构化 ──

def parse_questions_with_llm(full_text, region, year):
    """分块 OCR 文本 → LLM 提取 → 合并题目列表"""
    from app.services.llm_service import llm_service

    # Split text into chunks of ~4000 chars, breaking at page boundaries
    pages = full_text.split('\n--- Page ')
    chunks = []
    current = ''
    for page in pages:
        if not page.strip():
            continue
        chunk = f'--- Page {page}' if not page.startswith('---') else page
        if len(current) + len(chunk) > 4500 and current:
            chunks.append(current)
            current = chunk
        else:
            current += '\n' + chunk
    if current:
        chunks.append(current)

    print(f"  Split into {len(chunks)} text chunks")

    all_questions = []
    for ci, chunk in enumerate(chunks):
        print(f"  Chunk {ci+1}/{len(chunks)} ({len(chunk)} chars)...", end=' ', flush=True)

        questions = _parse_chunk(llm_service, chunk, region, year)
        print(f"{len(questions)} questions extracted")
        all_questions.extend(questions)
        if ci < len(chunks) - 1:
            time.sleep(1)  # rate limit

    # Deduplicate by question number
    seen = set()
    unique = []
    for q in all_questions:
        num = q.get('number', '')
        if num and num not in seen:
            seen.add(num)
            unique.append(q)
    unique.sort(key=lambda q: int(q['number']) if q.get('number','').isdigit() else 999)

    print(f"  Total: {len(unique)} unique questions (deduped from {len(all_questions)})")
    return unique


def _parse_chunk(llm_service, chunk_text, region, year):
    """LLM 解析单个文本块"""
    import re
    import json

    prompt = f"""你是高中化学教研员。以下是{year}年{region}高考化学试卷OCR文本片段（含解析/答案）。

提取本片段中所有题目，返回JSON数组。每道题必须包含:
- number: 题号(字符串)
- content: 题目正文（完整，含选项如"A.xxx B.xxx"）
- answer: 正确答案（解析卷标注的答案，如"D"）
- analysis: 解析/解题思路（摘录解析卷内容，精简到100字以内）
- knowledge_points: 知识点列表(如["氧化还原","电化学"])
- difficulty: "easy"/"medium"/"hard"
- question_type: "choice"/"fill"/"calc"/"experiment"/"synthesis"

严格要求: 每条analysis不超过100字。content中如含化学式，保留原样。
只返回JSON数组:
[{{"number":"1","content":"...","answer":"D","analysis":"...","knowledge_points":[...],"difficulty":"easy","question_type":"choice"}}]

OCR文本:
{chunk_text}"""

    try:
        result = llm_service.generate_text(
            prompt=prompt,
            system_prompt="你是高中化学教研员。只返回JSON数组。",
            temperature=0.2,
            max_tokens=3000,
        )
        if result.get('success'):
            content = result['content']
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    # Try fixing truncated JSON
                    fixed = _fix_truncated_json(json_match.group())
                    if fixed:
                        return fixed
    except Exception as e:
        print(f"LLM error: {e}")
    return []


def _fix_truncated_json(json_str):
    """尝试修复被截断的JSON数组"""
    # Try adding missing closing brackets
    for suffix in ['}]', '}]\n]', '}]', '\n]']:
        try:
            return json.loads(json_str.rstrip() + suffix)
        except json.JSONDecodeError:
            continue
    # Try removing last incomplete element
    last_comma = json_str.rfind(',\n  {')
    if last_comma > 0:
        try:
            return json.loads(json_str[:last_comma] + '\n]')
        except json.JSONDecodeError:
            pass
    return None


# ── 保存 ──

def save_paper(region, year, questions, paper_name):
    """保存为 HistoricalQuestion 兼容的 JSON + 导入数据库"""
    # Map question_type values
    type_map = {
        'choice': 'single_choice',
        'single_choice': 'single_choice',
        'fill': 'fill_blank',
        'fill_blank': 'fill_blank',
        'calc': 'calculation',
        'calculation': 'calculation',
        'experiment': 'short_answer',
        'synthesis': 'short_answer',
    }

    # Convert to HistoricalQuestion-compatible format
    formatted = []
    for q in questions:
        num = q.get('number', '')
        qt = type_map.get(q.get('question_type', 'choice'), 'single_choice')
        # Default score: 3 for Hunan choice, 6 for national choice, 12-15 for non-choice
        if qt == 'single_choice':
            score = 3 if region == '湖南卷' else 6
        else:
            score = q.get('score', 14)

        formatted.append({
            'exam_id': f"{'hun' if '湖南' in region else 'nat'}_{year}_t{num}",
            'source': f"{region}{year}",
            'year': year,
            'region': region,
            'paper_name': paper_name,
            'question_number': f"T{num}",
            'original_number': num,
            'question_type': qt,
            'content': q.get('content', ''),
            'options': q.get('options'),
            'answer': str(q.get('answer', '')),
            'analysis': q.get('analysis', ''),
            'knowledge_points': q.get('knowledge_points', []),
            'difficulty': q.get('difficulty', 'medium'),
            'discrimination': 0.5,
            'score': score,
            'chapter': '',
        })

    # JSON 文件
    region_dir = os.path.join(OUTPUT_DIR, region, str(year))
    os.makedirs(region_dir, exist_ok=True)

    safe_name = paper_name.replace('/', '_').replace('\\', '_')
    json_path = os.path.join(region_dir, f"{safe_name}.json")

    data = {
        "paper_name": paper_name,
        "region": region,
        "year": year,
        "subject": "化学",
        "total_score": sum(q['score'] for q in formatted),
        "question_count": len(formatted),
        "questions": formatted,
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  Saved: {json_path} ({len(formatted)} questions)")

    # 数据库
    try:
        from app.models.database import get_db, Question
        db = next(get_db())
        try:
            for q in formatted:
                question = Question(
                    question_id=f"q_{q['exam_id']}",
                    content=q.get('content', ''),
                    options=q.get('options'),
                    answer=str(q.get('answer', '')),
                    analysis=q.get('analysis', ''),
                    knowledge_points=q.get('knowledge_points', []),
                    source_exam=f"{region}{year}",
                    difficulty=q.get('difficulty', 'medium'),
                )
                db.add(question)
            db.commit()
            print(f"  DB: {len(formatted)} questions saved")
        finally:
            db.close()
    except Exception as e:
        print(f"  DB save failed (non-fatal): {e}")

    return json_path


# ── 主流程 ──

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--year', type=int)
    parser.add_argument('--dpi', type=int, default=150)
    args = parser.parse_args()

    if args.year:
        global YEARS
        YEARS = [args.year]

    # Load dotenv for API keys
    from dotenv import load_dotenv
    load_dotenv()

    pdfs = find_parsed_pdfs()
    print(f"Found {len(pdfs)} parsed exam PDFs (2020-2025):")
    for region, year, path, name in pdfs:
        print(f"  [{year}] {region} — {name}")

    if args.dry_run:
        print("\n[Dry run — no processing]")
        return

    for i, (region, year, pdf_path, paper_name) in enumerate(pdfs):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(pdfs)}] {year} {region}")
        paper_name_clean = paper_name.replace('.pdf', '')

        # Step 1: PDF → images
        print(f"  Converting PDF to images (dpi={args.dpi})...")
        pages = pdf_to_images(pdf_path, dpi=args.dpi)
        print(f"  {len(pages)} pages")

        # Step 2: OCR each page
        full_text = ""
        for page_num, img_bytes in pages:
            print(f"  OCR page {page_num}/{len(pages)}...", end=' ', flush=True)
            text = ocr_page(img_bytes)
            full_text += f"\n--- Page {page_num} ---\n{text}"
            print(f"({len(text)} chars)")
            time.sleep(0.3)  # rate limit

        print(f"  Total OCR text: {len(full_text)} chars")

        if len(full_text) < 100:
            print("  WARNING: OCR text too short, skipping")
            continue

        # Step 3: LLM parse
        print("  Parsing with LLM...")
        questions = parse_questions_with_llm(full_text, region, year)

        if not questions:
            print("  WARNING: LLM returned 0 questions, saving raw OCR")
            # Save raw text as fallback
            os.makedirs(os.path.join(OUTPUT_DIR, region, str(year)), exist_ok=True)
            raw_path = os.path.join(OUTPUT_DIR, region, str(year),
                                     f"{paper_name_clean}_raw.txt")
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(full_text)
            print(f"  Raw OCR saved to: {raw_path}")
            continue

        # Step 4: Save
        save_paper(region, year, questions, paper_name_clean)

    print(f"\n{'='*60}")
    print("Import complete!")


if __name__ == '__main__':
    main()
