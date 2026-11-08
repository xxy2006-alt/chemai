"""Import a single exam paper — Qwen-VL-OCR → Markdown parser → DB."""
import sys
import os
import json
import re
import time
import sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else None
REGION = sys.argv[2] if len(sys.argv) > 2 else "全国卷"
YEAR = int(sys.argv[3]) if len(sys.argv) > 3 else 2020

if not PDF_PATH:
    print("Usage: python scripts/import_single_paper.py <pdf_path> [region] [year]")
    sys.exit(1)

print(f"Importing: {PDF_PATH} ({REGION} {YEAR})")

out_dir = f"data/exam_questions/{REGION}/{YEAR}"
fig_dir = f"{out_dir}/figures"
os.makedirs(fig_dir, exist_ok=True)

# ── 1. PDF → Qwen-VL-OCR per page ──
import fitz  # noqa: E402
from app.services.llm_service import llm_service  # noqa: E402

doc = fitz.open(PDF_PATH)
npages = doc.page_count
print(f"Pages: {npages}")

page_texts = []
for pg in range(npages):
    pix = doc[pg].get_pixmap(dpi=150)
    img = pix.tobytes("png")
    # Save page image
    with open(f"{fig_dir}/page_{pg+1:02d}.png", "wb") as f:
        f.write(img)
    # OCR
    r = llm_service.ocr_image(img)
    if r.get("success"):
        page_texts.append((pg+1, r["content"]))
        print(f"  Page {pg+1}: {len(r['content'])} chars, {r.get('usage',{}).get('total_tokens','?')}t")
    else:
        print(f"  Page {pg+1}: FAILED - {r.get('error','')}")
    time.sleep(0.5)
doc.close()

full_md = "\n\n".join(t[1] for t in page_texts)
print(f"Total: {len(full_md)} chars\n")

# ── 2. Parse Markdown → structured questions ──
questions = []
# Split on question number patterns: "1. (6分)", "10. (14分)", "1.(6分)"
blocks = re.split(r'\n(?=\d{1,2}\.\s*\(\d+分?\)|\d{1,2}\.\s*\d+分)', full_md)
for block in blocks:
    block = block.strip()
    if not block or len(block) < 50:
        continue

    # Extract question number
    m = re.match(r'(\d{1,2})[\.、]\s*(?:\((\d+)分?\))?', block)
    if not m:
        continue
    number = m.group(1)
    score = int(m.group(2)) if m.group(2) else 0

    # Extract answer
    answer = ""
    ans_m = re.search(r'【答案】\s*(.+?)(?:\n|$)', block)
    if ans_m:
        answer = ans_m.group(1).strip()
    if not answer:
        ans_m = re.search(r'【解答】解\s*(.+?)(?:\n|$)', block)
        if ans_m:
            answer = ans_m.group(1).strip()
    if not answer or len(answer) < 2:
        ans_m = re.search(r'故选[：:]\s*(.+?)(?:[。\.]|$)', block)
        if ans_m:
            answer = ans_m.group(1).strip()

    # Extract analysis
    analysis = ""
    anal_m = re.search(r'【分析】(.*?)(?=【|$)', block, re.DOTALL)
    if anal_m:
        analysis = anal_m.group(1).strip()[:200]
    if not analysis:
        anal_m = re.search(r'【解析】(.*?)(?=【|$)', block, re.DOTALL)
        if anal_m:
            analysis = anal_m.group(1).strip()[:200]

    # Content: the block itself (preserves Markdown formatting)
    content = block.strip()

    # Question type
    qtype = "choice"
    if int(number) >= 8:
        qtype = "fill_blank"
    if any(kw in block for kw in ["计算", "求", "="]):
        qtype = "calculation"

    # Difficulty
    difficulty = "easy" if int(number) <= 7 else "medium"

    # Page estimate (crude: figures on pages 1-7 for choice, 8+ for non-choice)
    page_est = int(number) if int(number) <= 7 else int(number) - 7 + 7

    questions.append({
        "number": number,
        "content": content,
        "answer": answer,
        "analysis": analysis[:200] if analysis else "",
        "score": score or (6 if int(number) <= 7 else 14),
        "qtype": qtype,
        "difficulty": difficulty,
        "page_image": f"figures/page_{page_est:02d}.png",
    })
    print(f"  [{number}] ({len(content)}c, {len(analysis)}a) ans={answer[:30]}")

print(f"\nParsed {len(questions)} questions")

# ── 3. Save ──
db = sqlite3.connect("chemai.db")
paper_qs = []
for q in questions:
    n = q["number"]
    fq = {
        "exam_id": f"{'nat' if '全国' in REGION else 'hun'}_{YEAR}_t{n}",
        "source": f"{REGION}{YEAR}", "year": YEAR, "region": REGION,
        "paper_name": f"{YEAR}年{REGION}高考化学试卷",
        "question_number": f"T{n}", "original_number": n,
        "question_type": q["qtype"],
        "content": q["content"], "options": None,
        "answer": q["answer"],
        "analysis": q["analysis"],
        "knowledge_points": [], "difficulty": q["difficulty"],
        "discrimination": 0.5, "score": q["score"], "chapter": "",
        "page_image": q["page_image"],
    }
    paper_qs.append(fq)
    db.execute(
        "INSERT INTO questions(question_id,content,options,answer,analysis,knowledge_points,difficulty,source,source_exam) VALUES(?,?,?,?,?,?,?,?,?)",
        (fq["exam_id"], fq["content"], None, fq["answer"], fq["analysis"],
         json.dumps([]), fq["difficulty"], "ocr_import", f"{REGION}{YEAR}"))
db.commit()
db.close()

# Summary JSON (exam_bank compatible)
with open(f"{out_dir}/{YEAR}年{REGION}高考化学.json", "w", encoding="utf-8") as f:
    json.dump({"paper_name": f"{YEAR}年{REGION}高考化学试卷", "region": REGION, "year": YEAR,
               "subject": "化学", "total_score": sum(q["score"] for q in questions),
               "question_count": len(paper_qs), "questions": paper_qs},
              f, ensure_ascii=False, indent=2)

# Also save raw Markdown
with open(f"{out_dir}/{YEAR}年{REGION}高考化学_full.md", "w", encoding="utf-8") as f:
    f.write(f"# {YEAR}年{REGION}高考化学试卷\n\n{full_md}")

print(f"\nSaved: {len(questions)} questions to {out_dir}/")
