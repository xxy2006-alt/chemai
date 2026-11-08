"""Import exam paper: MinerU pipeline → LLM structure → JSON + DB."""
import sys
import os
import re
import json
import time
import shutil
import sqlite3
import multiprocessing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(pdf_path_str, region, year):
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()

    pdf_path = Path(pdf_path_str)
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path_str}")
        sys.exit(1)

    print(f"MinerU Import: {pdf_path} ({region} {year})")

    # ── Step 0: Prepare directories ──
    out_base = Path(f"data/exam_questions/{region}/{year}")
    fig_dir = out_base / "figures"
    mineru_work_dir = out_base / "_mineru_work"
    fig_dir.mkdir(parents=True, exist_ok=True)
    mineru_work_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: MinerU do_parse ──
    print("\n[1/5] MinerU parsing PDF...")
    from mineru.cli.common import do_parse, read_fn
    from mineru.utils.enum_class import MakeMode

    t0 = time.time()
    do_parse(
        output_dir=str(mineru_work_dir),
        pdf_file_names=[pdf_path.stem],
        pdf_bytes_list=[read_fn(pdf_path)],
        p_lang_list=["ch"],
        backend="pipeline",
        formula_enable=True, table_enable=True,
        f_draw_layout_bbox=False, f_draw_span_bbox=False,
        f_dump_md=True, f_dump_middle_json=False, f_dump_model_output=False,
        f_dump_orig_pdf=False, f_dump_content_list=True,
        f_make_md_mode=MakeMode.MM_MD,
    )
    print(f"  Done in {time.time()-t0:.0f}s")

    # Find the output directory MinerU created
    mineru_out = None
    for d in mineru_work_dir.iterdir():
        if d.is_dir() and pdf_path.stem in d.name:
            mineru_out = d / "auto"
            break
    if not mineru_out or not mineru_out.exists():
        print("ERROR: MinerU output not found")
        sys.exit(1)

    md_file = mineru_out / f"{pdf_path.stem}.md"
    img_src = mineru_out / "images"
    if not md_file.exists():
        print("ERROR: Markdown not found")
        sys.exit(1)

    with open(md_file, "r", encoding="utf-8") as f:
        full_md = f.read()
    print(f"  Markdown: {len(full_md)} chars")

    # ── Step 2: Copy images & fix paths ──
    print("\n[2/5] Copying images & fixing paths...")
    img_count = 0
    if img_src.exists():
        for img in img_src.iterdir():
            if img.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                shutil.copy2(img, fig_dir / img.name)
                img_count += 1
    # Fix Markdown references: images/xxx.jpg → figures/xxx.jpg
    full_md = full_md.replace("(images/", "(figures/")
    print(f"  Copied {img_count} images, paths fixed")

    # ── Step 2b: PDF page screenshots ──
    print("  Generating page screenshots...")
    import fitz
    pdf_doc = fitz.open(str(pdf_path))
    for pg in range(pdf_doc.page_count):
        page_path = fig_dir / f"page_{pg+1:02d}.png"
        if not page_path.exists():
            pix = pdf_doc[pg].get_pixmap(dpi=120)
            pix.save(str(page_path))
    total_pages = pdf_doc.page_count
    pdf_doc.close()
    print(f"  {total_pages} page screenshots")

    # ── Step 3: Split Markdown into question blocks ──
    print("\n[3/5] Splitting into question blocks...")

    # Split on question number patterns: "7．（6 分）..." or "8．（14分）..."
    # MinerU outputs: "7．(6 分)" with fullwidth ．（）
    q_pat = re.compile(r'(?<=\n)(\d{1,2})\s*[.．]\s*[(\uFF08]\s*(\d+)\s*分?\s*[)\uFF09]')
    splits = q_pat.split(full_md)

    blocks = []
    i = 0
    while i < len(splits):
        if re.match(r'^\d{1,2}$', splits[i]):
            num, raw_score, body = splits[i], splits[i+1], splits[i+2]
            score = int(raw_score) if raw_score.isdigit() else 0
            block = f"## 第{num}题（{score}分）\n{body}"
            blocks.append((int(num), score, block))
            i += 3
        else:
            i += 1

    # Catch trailing Q12 without score pattern (选考题)
    if blocks and len(splits) >= 3:
        last_body = splits[-1]
        m = re.search(r'\n(12)\s*[．.]', last_body)
        if m:
            q11_body = last_body[:m.start()]
            q12_body = last_body[m.start()+1:].strip()
            n, s, _ = blocks[-1]
            blocks[-1] = (n, s, f"Question {n} ({s} points):\n{q11_body}")
            blocks.append((12, 15, f"Question 12 (15 points):\n{q12_body}"))

    print(f"  {len(blocks)} question blocks found")

    # ── Step 4: LLM structure each block ──
    print("\n[4/5] LLM structuring...")
    from app.services.llm_service import llm_service

    questions = []
    for qi, (num, score, block) in enumerate(blocks):
        print(f"  [{num}/{len(blocks)}] T{num} ({len(block)} chars)...", end=" ", flush=True)

        # Find the first image in this block for page_image
        page_img = ""
        img_match = re.search(r'!\[.*?\]\((figures/page_\d{2}\.png)\)', block)
        if not img_match:
            img_match = re.search(r'!\[.*?\]\((figures/[^)]+)\)', block)
        if not img_match:
            pg = max(1, min(num, 22))
            page_img = f"figures/page_{pg:02d}.png"
        else:
            page_img = img_match.group(1)

        prompt = f"""你是化学题目解析器。从以下高考化学题目Markdown中提取信息，返回JSON。

{block[:2500]}

重要：content字段必须**原样保留所有 ![](/static/figures/...) 图片引用**！
返回JSON: {{"number":"{num}","content":"完整题目(保留所有图片引用和化学式)","answer":"正确答案","analysis":"简短解析","knowledge_points":["知识点"],"difficulty":"easy","question_type":"choice"}}"""

        try:
            r = llm_service.generate_text(
                prompt=prompt,
                system_prompt="只返回JSON对象。",
                temperature=0.1,
                max_tokens=5000,
                provider="deepseek",
            )
            if r.get("success"):
                content = r["content"].strip()
                content = re.sub(r'^```(?:json)?\s*\n?', '', content)
                content = re.sub(r'\n?```\s*$', '', content)
                start = content.find('{')
                end = content.rfind('}')
                if start >= 0 and end > start:
                    content = content[start:end+1]
                from json_repair import repair_json
                content = repair_json(content)
                q = json.loads(content)
                q["number"] = str(num)
                q["page_image"] = page_img
                q["score"] = score
                questions.append(q)
                print(f"OK type={q.get('question_type','?')}")
            else:
                print(f"LLM FAIL: {r.get('error','')}")
        except Exception as e:
            print(f"PARSE FAIL: {e}")

        if qi < len(blocks) - 1:
            time.sleep(0.5)

    print(f"\n  Structured {len(questions)}/{len(blocks)} questions")

    # ── Step 5: Save ──
    print("\n[5/5] Saving...")

    type_map = {
        "choice": "single_choice", "single_choice": "single_choice",
        "fill_blank": "fill_blank", "fill": "fill_blank",
        "fill-in-the-blank": "fill_blank",
        "calculation": "calculation", "calc": "calculation",
        "short_answer": "short_answer", "experiment": "short_answer",
        "comprehensive": "short_answer", "non-choice": "short_answer",
    }

    paper_qs = []
    for q in questions:
        num = str(q.get("number", ""))
        qt = type_map.get(q.get("question_type", "choice"), "single_choice")
        paper_qs.append({
            "exam_id": f"{'nat' if '全国' in region else 'hun'}_{year}_t{num}",
            "source": f"{region}{year}", "year": year, "region": region,
            "paper_name": f"{year}年{region}高考化学试卷",
            "question_number": f"T{num}", "original_number": num,
            "question_type": qt,
            "content": q.get("content", ""),
            "options": q.get("options"),
            "answer": str(q.get("answer", "")),
            "analysis": (q.get("analysis", "") or "")[:300],
            "knowledge_points": q.get("knowledge_points", []),
            "difficulty": q.get("difficulty", "medium"),
            "discrimination": 0.5,
            "score": q.get("score", 6),
            "chapter": "",
            "page_image": q.get("page_image", ""),
        })

    # JSON file
    json_path = out_base / f"{year}年{region}高考化学.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "paper_name": f"{year}年{region}高考化学试卷",
            "region": region, "year": year, "subject": "化学",
            "total_score": sum(q["score"] for q in paper_qs),
            "question_count": len(paper_qs),
            "questions": paper_qs,
        }, f, ensure_ascii=False, indent=2)
    print(f"  JSON: {json_path} ({len(paper_qs)} questions)")

    # Full Markdown
    md_path = out_base / f"{year}年{region}高考化学_full.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {year}年{region}高考化学试卷\n\n{full_md}")
    print(f"  MD:   {md_path} ({len(full_md)} chars)")

    # DB insert
    try:
        db = sqlite3.connect("chemai.db")
        for q in paper_qs:
            db.execute(
                "INSERT OR REPLACE INTO questions(question_id,content,options,answer,analysis,knowledge_points,difficulty,source,source_exam) VALUES(?,?,?,?,?,?,?,?,?)",
                (q["exam_id"], q["content"], None, q["answer"], q["analysis"],
                 json.dumps(q["knowledge_points"]), q["difficulty"], "mineru_import",
                 f"{region}{year}"))
        db.commit()
        db.close()
        print(f"  DB:   {len(paper_qs)} questions saved")
    except Exception as e:
        print(f"  DB warning: {e}")

    # Clean up mineru work dir
    shutil.rmtree(mineru_work_dir, ignore_errors=True)

    print(f"\nDone! {len(paper_qs)} questions imported to {json_path}")
    print(f"Figures: {fig_dir} ({len(list(fig_dir.glob('*')))} files)")

    return len(paper_qs)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    pdf_arg = sys.argv[1] if len(sys.argv) > 1 else None
    region_arg = sys.argv[2] if len(sys.argv) > 2 else "全国卷"
    year_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 2020
    if not pdf_arg:
        print("Usage: python scripts/import_mineru_paper.py <pdf_path> [region] [year]")
        sys.exit(1)
    main(pdf_arg, region_arg, year_arg)
