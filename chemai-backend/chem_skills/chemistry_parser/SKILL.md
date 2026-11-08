---
name: chemistry-parser
description: Parse PDF/Word documents to extract chemical questions with LaTeX formulas. Integrates MinerU for high-precision document parsing and chemical formula recognition.
version: 1.0.0
author: ChemAI Hermes Integration
license: MIT
metadata:
  hermes:
    tags: [parsing, pdf, word, ocr, chemical-formula, latex, extraction]
    related_skills: [chemistry-exam, chemistry-diagnosis]
---

# Chemistry Parser Skill

## Overview

Integrates MinerU v3.0.0 high-precision document parsing engine to extract chemical questions from PDF/Word documents, enabling fill-in-the-blank and short-answer question types (previously only available as选择题).

## Core Capabilities

- **PDF Parsing**: Use MinerU's hybrid-auto-engine backend for high-accuracy text and formula extraction
- **LaTeX Formula Recognition**: Preserve chemical formulas (e.g., `Ca(OH)₂`, `Fe₂(SO₄)₃`) in parsed output
- **Question Extraction**: Identify and extract question text, options, and answers from parsed content
- **Chemical Formula Standardization**: Normalize various chemical notation formats
- **OCR Support**: Handle scanned/image-based PDFs with OCR capability

## Integration with MinerU

MinerU provides:
- `hybrid-auto-engine` backend for highest accuracy
- `formula_enable=True` for LaTeX chemical formula extraction
- `table_enable=True` for chemical data tables
- Support for Chinese (`ch`) language

## How It Works

1. User provides document path (PDF/Word/image)
2. MinerU parses document, extracting:
   - Full text content
   - LaTeX formulas (chemical equations, reaction conditions)
   - Tables (solubility tables, activity series, etc.)
   - Images (molecular structures, experimental apparatus)
3. chemistry-parser Skill post-processes the extracted content:
   - Identifies question boundaries
   - Classifies question types (fill-blank, short-answer, calculation)
   - Standardizes chemical formulas
   - Structures output for ChemAI Agent consumption

## Question Types Enabled

| Type | Description | Example |
|------|-------------|---------|
| 填空题 | Fill-in-the-blank | "实验室制取氧气时，试管口应___倾斜。" |
| 简答题 | Short answer | "解释铁在潮湿空气中生锈的原因。" |
| 计算题 | Calculation | "已知25°C时Ksp(AgCl)=1.8×10⁻¹⁰，求..." |

## Safety Considerations

- Parsed content should still go through `chemistry_exam.exam_audit` for safety review
- Chemical formulas should be validated before use in generation prompts
- OCR results should be verified for accuracy in critical educational content

## Example Workflow

```
1. User uploads: "初中化学期中试卷.pdf"
2. Skill calls: parse_pdf_questions("试卷.pdf", lang="ch")
3. MinerU returns: {md_content, middle_json, images, formulas}
4. Post-processing: Extract questions, standardize formulas
5. Output: Structured questions ready for exam generation or review
```
