# Session 11 · OCR 管线搭建

## 产出物

- `app/services/ocr_service.py` — 三层 OCR 架构（Baidu 快速层 + MinerU 精读层 + MiMo 视觉兜底）
- `import_mineru_paper.py` — MinerU pipeline 调用脚本（PDF → 结构化 JSON）
- `download_mineru_models.py` — MinerU 7 个模型的下载脚本
- `tests/test_mineru_2020.py` — 2020 全国卷高考化学 OCR 精度验证
- `data/papers/2020_gaokao_chemistry.json` — 12 道题的完整结构化输出（含 LaTeX）
- `requirements.txt` 更新 — 新增 mineru、numpy<2.0 等 OCR 依赖

## 前置条件

- Session 1 的 `chemai-backend/` 目录完整可用
- Session 2 的 `app/services/llm_service.py` 可用（LLM 用于 OCR 后处理）
- Session 10 的数据库就绪（14 个表）
- Python 3.11，内存 >= 8GB（MinerU pipeline 峰值 2.8GB）
- 硬盘剩余空间 >= 10GB（MinerU 模型文件约 4GB + 依赖）
- 需要下载测试数据：2020 年全国卷高考化学（新课标 I）解析卷 PDF（22 页）
- **如果学生电脑只有 4GB 内存**，提前告知——MinerU 模型加载阶段可能 OOM

## 项目背景（给学生的概述）

上节课你完成了场景假设和数据库设计。但教师手头的高考真题都是 PDF 格式——22 页的扫描文档，里面混着化学方程式、分子结构图、实验装置图、表格。通用 OCR 面对这些东西基本报废。这节课要解决的是 ChemAI 最硬的一块骨头：**让计算机读懂化学 PDF**。

我们从三个方案中选型：百度 OCR（最快但化学式丢失）、Qwen-VL-OCR（多模态但碎片化）、MinerU pipeline（专门为论文/教材设计的 OCR 引擎）。实测结论是 MinerU 是唯一能完整提取 12 道题、保留所有 LaTeX 公式的方案。

但 MinerU 不是"装上就能用"——你需要下载 7 个模型（Layout Detection、MFR 公式识别、OCR 文字识别、Table Recognition 等）、处理 Windows multiprocessing 兼容性问题、解决 numpy 2.0 冲突。这些坑我们都踩过一遍，这节课你要照着我们的路径走一遍。

最后，我们要设计一个三层架构：百度 OCR 做快速预览（10 秒出结果）、MinerU 做精确导入（15 分钟处理 22 页）、MiMo 视觉做兜底（处理 MinerU 失败的页面）。

---

## 操作步骤

### 步骤 1：POC 测试——三种 OCR 方案对比

**目标**：用 2020 全国卷高考化学 PDF 测试三个 OCR 方案，量化差距，确定选型

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 项目中，创建 tests/test_ocr_poc.py，对三种 OCR 方案做 POC 对比。

先准备好测试 PDF：data/papers/2020_gaokao_chemistry.pdf（需要手动下载 2020 年全国卷高考化学新课标 I 解析卷，22 页 PDF，放到 data/papers/ 目录）。

测试脚本 tests/test_ocr_poc.py 的内容：

1. 方案 A — 百度 OCR 测试：
   - 安装 baidu-aip：pip install baidu-aip
   - 调用百度通用文字识别 API（需要 APP_ID, API_KEY, SECRET_KEY，暂时用环境变量传）
   - 对 PDF 逐页截图后调用 API
   - 记录：提取出的文字内容、是否正确识别化学式（如 Fe2O3 vs Fe203）、LaTeX 完整性
   - 打印结果摘要

2. 方案 B — Qwen-VL-OCR 测试（用 DashScope 的多模态接口）：
   - 使用 DashScope 的 qwen-vl-ocr 模型
   - 将 PDF 页面转为图片 base64 发送
   - 记录：与方案 A 相同的指标
   - 注意：使用 app/services/llm_service.py 中的配置（DASHSCOPE_API_KEY）

3. 方案 C — MinerU pipeline 测试（先尝试安装，如果失败只打印错误信息）：
   - pip install magic-pdf
   - 简单调用验证

4. 对比表格打印：
   | 方案 | 估计题数 | LaTeX | 化学式 | 耗时估算 |
   |------|---------|-------|--------|---------|

   填入实际测试数据。

运行脚本，观察三种方案对同一份化学试卷的输出质量差异。
```

**验证**：
- [ ] 百度 OCR 返回了文字但化学式丢失（Fe2O3 变成 Fe203）
- [ ] Qwen-VL-OCR 同样化学式碎片化
- [ ] 如果 MinerU 安装成功，输出质量明显优于前两者

---

### 步骤 2：安装 MinerU 并修复依赖冲突

**目标**：正确安装 MinerU，解决 numpy 版本冲突

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 项目、venv 激活状态下，安装 MinerU 及其依赖。

1. 首先检查当前 numpy 版本：pip show numpy

2. 安装 MinerU：
   pip install magic-pdf

3. 如果安装过程中报错 numpy 相关冲突（常见错误：AttributeError: module 'numpy' has no attribute 'float_'）：
   - 这是因为 numpy 2.0 移除了 np.float_ 别名，而 chromadb（MinerU 的依赖）还在使用旧 API
   - 解决方案：pip install "numpy<2.0"
   - 重新验证：python -c "import numpy; print(numpy.__version__)" 确认版本 < 2.0

4. 安装其他依赖：
   pip install pdf2image pillow opencv-python-headless

5. 验证 MinerU 安装：
   python -c "from magic_pdf.pipe.UNIPipe import UNIPipe; print('MinerU OK')"

6. 更新 requirements.txt：
   pip freeze > requirements.txt

记录每一步的输出，如果遇到其他错误不要跳过，尝试修复后再继续。
```

**验证**：
- [ ] `pip show numpy` 显示版本 < 2.0（如 1.26.4）
- [ ] `python -c "from magic_pdf.pipe.UNIPipe import UNIPipe; print('MinerU OK')"` 无报错
- [ ] requirements.txt 已更新

---

### 步骤 3：下载 MinerU 的 7 个模型

**目标**：创建模型下载脚本，下载 MinerU pipeline 需要的全部模型

**提示词**（复制到 Claude Code）：
```
创建 download_mineru_models.py（放在 chemai-backend 根目录），下载 MinerU pipeline 的 7 个模型。

脚本内容：

import os
from magic_pdf.model.doc_analyze_by_custom_model import ModelSingleton

def download_models():
    """
    MinerU pipeline 需要以下 7 个模型：
    1. Layout Detection（版面检测）— 检测 PDF 中的文本块/表格/图片
    2. MFR (Math Formula Recognition) — 公式识别，将图片公式转 LaTeX
    3. OCR — 文字识别
    4. Table Recognition — 表格识别
    5. Reading Order — 版面阅读顺序
    6. Formula Detection — 公式区域检测
    7. PDF Classification — PDF 分类

    模型总大小约 4GB，下载需要 10-30 分钟（取决于网络）。
    """

    # 初始化 ModelSingleton，触发模型下载
    model_manager = ModelSingleton()
    # 如果模型已存在，跳过下载；否则自动下载

    # 打印下载进度
    print("MinerU 模型下载完成，模型路径：", model_manager.get_models_dir())

if __name__ == "__main__":
    download_models()

如果你使用 MinerU 的具体 API 和我上面写的不一致，请根据实际的 magic_pdf 版本调整。先运行 python -c "import magic_pdf; print(dir(magic_pdf))" 确认可用的模块。

如果模型下载很慢（国内网络），可以设置镜像：
- 模型文件托管在 HuggingFace，设置环境变量 HF_ENDPOINT=https://hf-mirror.com 使用国内镜像
- 在代码中加 os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

运行脚本，等待模型下载完成。
```

**验证**：
- [ ] 运行 `python download_mineru_models.py` 无报错
- [ ] 7 个模型全部下载成功（检查模型目录是否存在对应文件）

---

### 步骤 4：编写 import_mineru_paper.py——OCR 处理主脚本

**目标**：创建 `import_mineru_paper.py`，实现对 PDF 的完整处理流程

**提示词**（复制到 Claude Code）：
```
创建 import_mineru_paper.py（放在 chemai-backend 根目录），用于处理高考化学 PDF。

脚本功能：

1. 定义一个函数 do_parse(pdf_path: str, output_dir: str = "data/papers/") -> dict：
   - 输入：PDF 文件路径
   - 输出：包含所有题目的结构化字典

2. 处理流程：
   a. 加载 PDF 文件
   b. 调用 MinerU pipeline 的 UNIPipe 进行版面分析
   c. 提取文本块（paragraphs）、表格（tables）、公式（formulas）、图片（images）
   d. 将公式渲染为 LaTeX 字符串
   e. 将输出保存为 JSON 文件（output_dir / pdf文件名.json）
   f. 返回解析结果

3. 使用 MinerU 的 API（根据实际 magic_pdf 版本调整）：
   from magic_pdf.pipe.UNIPipe import UNIPipe

   典型用法：
   pipe = UNIPipe(pdf_bytes, jso_useful_key={"_pdf_type": "ocr"})
   pipe.pipe_classify()    # PDF 分类
   pipe.pipe_analyze()     # 版面分析
   pipe.pipe_parse()       # 解析
   结果在 pipe.get_content() 中

4. 在 if __name__ == "__main__" 中：
   - 处理 data/papers/2020_gaokao_chemistry.pdf
   - 打印处理进度（每页处理状态）
   - 打印摘要：提取到的题目数、表格数、公式数、图片数
   - 输出文件保存为 data/papers/2020_gaokao_chemistry.json

5. 重要：Windows multiprocessing 兼容性
   - 如果使用 ProcessPoolExecutor，必须在 if __name__ == "__main__" 块内创建
   - 否则 Windows spawn 模式会导致子进程重复执行脚本
   - 如果遇到 RuntimeError: freeze_support，确认 multiprocessing 代码在 main 保护内

运行脚本，观察输出结果。
```

**验证**：
- [ ] 运行 `python import_mineru_paper.py`，处理 2020 卷 PDF
- [ ] 控制台输出 22 页的处理进度
- [ ] `data/papers/2020_gaokao_chemistry.json` 生成，文件非空

---

### 步骤 5：验证——2020 全国卷 12 道题全量测试

**目标**：创建精确验证脚本，逐题检查 MinerU 的提取质量

**提示词**（复制到 Claude Code）：
```
创建 tests/test_mineru_2020.py，对 MinerU 处理 2020 全国卷的结果做精确验证。

1. 读取 data/papers/2020_gaokao_chemistry.json
2. 统计并打印：
   - 提取到的题目总数（目标：12 题）
   - 每道题的类型（选择题/填空题/简答题）
   - 每道题的 LaTeX 公式数量和完整性（无碎片化）
   - 表格提取情况（是否有遗漏）
   - 图片提取数量（目标：60+ 张）
3. 对比已知正确答案：
   - 2020 全国卷共有 12 道题（7 选择 + 3 必做 + 2 选做，总分 115 分）
   - 验证每道题的关键信息（化学反应方程式、计算数值、实验装置描述）
4. 输出详细报告：
   ```
   === MinerU 2020 全国卷 OCR 验证报告 ===
   题目总数: X/12
   选择题:  X/7
   非选择:  X/5
   LaTeX 公式: X 个（完整率: Y%）
   表格: X 个（完整率: Y%）
   图片: X 张
   处理耗时: X 秒
   总体评价: [通过/未通过]
   ```

运行脚本，确认 MinerU 的提取质量达到 12/12 题完整、LaTeX 全保留。
```

**验证**：
- [ ] 运行 `python tests/test_mineru_2020.py`
- [ ] 题目总数 12/12
- [ ] LaTeX 公式完整，无碎片化（化学式不丢失下标和上标）
- [ ] 图片数量 >= 60 张

---

### 步骤 6：设计三层 OCR 架构

**目标**：在 `app/services/ocr_service.py` 中实现三层 OCR 架构

**提示词**（复制到 Claude Code）：
```
创建 app/services/ocr_service.py，实现三层 OCR 架构。

架构设计：
┌─────────────────────────────────────┐
│         OCR 路由层                   │
│   根据场景选择处理层                  │
├─────────────────────────────────────┤
│ Layer 1: Baidu OCR                  │
│   场景：快速预览（教师上传预览）       │
│   速度：~10s/22页                    │
│   质量：文字 OK，化学式丢失            │
├─────────────────────────────────────┤
│ Layer 2: MinerU Pipeline            │
│   场景：精确导入（题库入库）           │
│   速度：~15min/22页                  │
│   质量：化学式 + LaTeX + 表格全保留    │
├─────────────────────────────────────┤
│ Layer 3: MiMo Visual Fallback        │
│   场景：MinerU 失败的页面             │
│   方案：截图 → MiMo 多模态阅读理解    │
│   用途：兜底，处理扫描质量差的页面     │
└─────────────────────────────────────┘

实现内容：

1. 函数 ocr_quick_preview(file_path: str) -> dict:
   - 调用百度 OCR（baidu-aip）
   - 返回 {"text": "...", "warnings": ["化学式可能丢失"]}
   - 用于教师上传 PDF 后的即时预览

2. 函数 ocr_precise_import(file_path: str, output_dir: str) -> dict:
   - 调用 MinerU pipeline（import_mineru_paper.do_parse）
   - 返回完整的结构化 JSON（题目、LaTeX、表格、图片）
   - 用于题库入库

3. 函数 ocr_with_fallback(file_path: str, page_num: int) -> dict:
   - 先用 MinerU 处理指定页
   - 如果 MinerU 失败（版面分析异常、MFR 超时），调用 MiMo 视觉兜底
   - 用 app.services.llm_service 调用 MiMo（provider="mimo"），发送页面截图
   - 返回处理结果 + 标注使用的处理层

4. 函数 ocr_route(file_path: str, mode: str = "preview") -> dict:
   - mode == "preview" → ocr_quick_preview
   - mode == "import" → ocr_precise_import
   - mode == "auto" → 先尝试精确导入，失败页用 fallback

5. 在 if __name__ == "__main__" 中测试三个模式。

注意：百度 OCR 的 APP_ID/API_KEY/SECRET_KEY 用环境变量 BAIDU_APP_ID, BAIDU_API_KEY, BAIDU_SECRET_KEY 传入。把这些加到 .env 中。
```

**验证**：
- [ ] `app/services/ocr_service.py` 文件已创建
- [ ] 三个函数全部实现
- [ ] import_mineru_paper 被正确引用

---

### 步骤 7：Git 提交

**目标**：提交本节所有改动

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 目录里提交本节所有改动：

1. git status 查看所有变更
2. git add app/services/ocr_service.py import_mineru_paper.py download_mineru_models.py tests/test_mineru_2020.py tests/test_ocr_poc.py requirements.txt .env
3. 确认 data/papers/ 在 .gitignore 中（模型输出不应提交）
4. git commit -m "v1.3.0: OCR 三层管线 — Baidu 快速层 + MinerU 精读层 + MiMo 视觉兜底"

注意：模型文件（约 4GB）和 PDF 测试数据不要提交到 Git。
```

**验证**：
- [ ] `git log` 显示新的提交 `v1.3.0`
- [ ] `git status` clean
- [ ] 模型文件和 PDF 不在 Git 跟踪中

---

## 发生了什么（教师参考）

### 1. 为什么通用 OCR 对化学试卷无效？

这是一个值得花时间让学生理解的认知：**OCR 不是"眼睛"，是"模式匹配"**。

百度 OCR 的训练数据以中文文本为主（新闻、合同、书籍），化学试卷里的东西它"没见过"：
- `Fe2O3` — 被识别为 `Fe203`（下标 2 和 3 变成了普通数字）
- `Cl2` — 被识别为 `Cl2`（下标丢失）
- `H+` — 被识别为 `H` 或 `H.`（上标 + 丢失）
- LaTeX 公式 `\frac{n}{V}` — 直接变成乱码

这不是百度 OCR 的"bug"——它就没被训练过识别化学式。就像一个只能听懂普通话的人，你让他听粤语，他不是"听不清"，他是"不会这种语言"。

### 2. 三种 OCR 方案的全部对比数据

2026 年 4 月 20 日（Week 2）做的 POC，使用 2020 年全国卷高考化学（新课标 I）解析卷（22 页 PDF）作为测试数据。

| 维度 | Baidu OCR + LLM | Qwen-VL-OCR + LLM | MinerU pipeline + LLM |
|------|----------------|-------------------|----------------------|
| 提取题数 | 6 题 | 6 题 | **12 题** |
| LaTeX 完整性 | 碎片化（100% 丢失）| 碎片化（100% 丢失）| **完整保留** |
| 化学式保真度 | 低（下标丢失）| 低（下标丢失）| **高（全部正确）** |
| 表格 | 无（识别为文本）| 无（识别为文本）| **HTML `<table>`** |
| 图片提取 | 无 | 无 | **60+ 张** |
| 处理耗时 | ~10 分钟 | ~15 分钟 | **~15 分钟** |
| 结论 | 不可用 | 不可用 | **唯一可用方案** |

**关键洞察**：前两个方案都是"6 题"——这不是巧合。百度 OCR 和改进版 Qwen-VL-OCR 都在同样的问题上栽了：含有化学方程式、分子结构图、实验装置图的页面，文字识别完全失败。它们能识别的是"纯文字题"（如选择题的题干），一旦题目中出现化学式，整道题就丢了。

MinerU 的优势在于它 **专门为学术论文设计**——学术论文的页面布局和高考化学试卷非常相似（公式+文字+表格+图片混排），所以版面和公式识别非常准确。

### 3. MinerU pipeline 的内部处理流程

MinerU 的处理不是"一步到位"的，而是分阶段逐步处理的：

```
PDF 输入
  │
  ├─ [PDF Classification]    判断 PDF 类型（扫描/文字/混合）
  │
  ├─ [Layout Detection]      版面分析：找出文本块、表格区、公式区、图片区
  │   耗时：~22% 内存：~800MB
  │
  ├─ [MFR]                   公式识别：将截图中的公式转 LaTeX 代码
  │   耗时：~63% ← 最慢的阶段！ 内存：~2.1GB（峰值）
  │
  ├─ [OCR]                   文字识别：识别文本块中的文字
  │   耗时：~10% 内存：~1.2GB
  │
  ├─ [Table Recognition]     表格识别：提取表格为 HTML <table>
  │   耗时：~3%
  │
  └─ [Reading Order]         阅读顺序：确定最终的阅读顺序
      耗时：~2%
```

**MFR（Math Formula Recognition）占总耗时的 63%**。这是 MinerU 的性能瓶颈——每一页的每一个公式都要经过 MFR 模型推理，22 页试卷处理了大约 200+ 个公式区域，每个区域的推理时间累加起来就是瓶颈。

如果学生在处理更厚的试卷（如 5 年真题合订本），耗时可以线性计算：22 页 = 15 分钟，100 页 ≈ 68 分钟。

### 4. 踩坑实录——四个关键问题的解决过程

**坑 1：MinerU 模型下载的四次尝试**

MinerU pipeline 需要从 HuggingFace 下载 7 个预训练模型，总大小约 4GB。在 2026 年 1 月的网络环境下，这非常容易失败。

| 尝试 | 方法 | 结果 |
|------|------|------|
| 1 | 直接 pip install magic-pdf 后自动下载 | 下载中断（网络超时）|
| 2 | 设置 HF_ENDPOINT=https://hf-mirror.com 国内镜像 | 部分模型下载成功，2 个模型 hash 校验失败 |
| 3 | 手动从 HuggingFace 下载模型文件到本地 models/ 目录 | 总耗时 40min，但 7 个模型全部校验通过 |
| 4 | `ModelSingleton` 自动检测本地模型 + 缺失时从镜像下载 | **最终方案** |

最终方案（尝试 4）实现了：已有模型不重复下载 + 缺失自动补全 + 国内镜像加速。这就是 `download_mineru_models.py` 的设计来源。

**坑 2：Windows multiprocessing 的 `spawn` 模式**

Linux 的 multiprocessing 默认是 `fork`（子进程继承父进程内存），Windows 是 `spawn`（子进程从头执行脚本）。

MinerU 内部使用了 `ProcessPoolExecutor` 做并行版面分析。在 Windows 上，如果 `ProcessPoolExecutor` 不在 `if __name__ == '__main__'` 保护内，子进程会递归创建新子进程，最终导致 RuntimeError。

解决方案：所有使用 MinerU 的脚本，确保入口在 `if __name__ == "__main__"` 块内。`import_mineru_paper.py` 已经按这个要求设计。

**坑 3：numpy 2.0 与 chromadb 的兼容性冲突**

错误信息：`AttributeError: module 'numpy' has no attribute 'float_'`

根本原因：numpy 2.0（2024 年 6 月发布）移除了 `np.float_`、`np.int_`、`np.bool_` 等旧别名。但 chromadb（MinerU 的依赖之一，用于向量存储）仍然在使用这些旧 API。

解决方案：强制降级 numpy 到 1.x 版本：`pip install "numpy<2.0"`。这不是 MinerU 的问题，是 chromadb 没有及时适配 numpy 2.0。

**坑 4：MinerU v3.4 vs 其他版本的 API 差异**

MinerU 的 API 在不同版本间变化很大：
- v2.x：使用 `do_parse()` 函数，API 简单但不支持自定义模型
- v3.x：引入 `UNIPipe` 类，需要分步调用 `pipe_classify()` → `pipe_analyze()` → `pipe_parse()`
- v3.4：增加 `jso_useful_key` 参数（PDF 类型指定），支持更多版面配置

我们选择 v3.4 是因为它的版面分析准确率比 v2.x 提升了约 15%（官方 benchmark 数据）。但 v3.4 的 API 更复杂，学生可能遇到的版本差异需要提前说明。

### 5. 三层架构的设计理由

为什么需要三个层，而不是只保留 MinerU？

| 场景 | 选用的层 | 理由 |
|------|---------|------|
| 教师刚上传 PDF，想看预览 | Layer 1（百度 OCR）| 10 秒出结果，不需要等 15 分钟 |
| 正式导入题库 | Layer 2（MinerU）| 精确度最重要，15 分钟可以接受 |
| 某页扫描质量太差，MinerU 失败 | Layer 3（MiMo 视觉）| 用 LLM 的多模态能力兜底 |

这是一个"慢但准"和"快但糙"之间的权衡。三层架构让学生可以把"快速出结果"和"高精度"两个目标分开实现，而不是为了精度牺牲所有场景的速度。

另一个被考虑但放弃的方案是"只用 MinerU + 异步任务队列"——教师上传后系统在后台处理，处理完通知教师。这个方案在技术上更优雅，但需要消息队列（Redis/Celery）和前端轮询机制，对于只处理 22 页 PDF 的场景来说过于复杂。三层架构在简单性和实用性之间取得了平衡。

### 6. 如果学生问"为什么不选 Qwen-VL-OCR？"

Qwen-VL-OCR 是多模态模型——它"看"图片然后直接"输出"文字，看起来比 MinerU 的 pipeline 方案简单很多。为什么不选它？

实测结果：Qwen-VL-OCR 确实能"看懂"图片中的化学式（比百度 OCR 强），但它输出的格式是不确定的——同一个公式有时输出 `Fe_2O_3`（Markdown 写法），有时输出 `Fe2O3`（纯文本），有时直接描述"三氧化二铁"。这种"格式不一致"导致无法做结构化存储。

MinerU 的 MFR 模块专门训练过"图片公式 → LaTeX 代码"的映射，输出格式严格一致（都是 LaTeX），这是专门化模型相对于通用多模态模型的优势。

---

## 课后产出检查

- [ ] `app/services/ocr_service.py` 包含三层架构的完整实现
- [ ] `import_mineru_paper.py` 能成功处理 2020 全国卷 PDF，生成 JSON
- [ ] `download_mineru_models.py` 所有 7 个模型已下载
- [ ] `tests/test_mineru_2020.py` 验证结果：12/12 题完整提取
- [ ] `.env` 包含百度 OCR 的三个 Key（BAIDU_APP_ID, BAIDU_API_KEY, BAIDU_SECRET_KEY）
- [ ] numpy 版本 < 2.0（`pip show numpy` 确认）
- [ ] 学生能解释三层架构每一层的适用场景和局限

**下节课需要**：OCR 管线可用，MinerU 模型已下载。Session 12 将创建前端页面（教师端 6 页 + 学生端 4 页）。

---

## 补充内容 — 教师深度参考

### A. MinerU 的 7 个模型详解

| 模型名 | 用途 | 大小 | 架构 |
|--------|------|------|------|
| Layout Detection | 版面检测，识别文本/表格/公式/图片区域 | ~400MB | DocLayout-YOLO |
| MFR | 数学公式识别（图片 → LaTeX）| ~1.2GB | UniMERNet |
| OCR | 文字识别（图片 → 文本）| ~800MB | PaddleOCR |
| Table Recognition | 表格识别（图片 → HTML table）| ~600MB | RapidTable |
| Reading Order | 阅读顺序排序 | ~300MB | LayoutReader |
| Formula Detection | 公式区域检测（与 Layout 协作）| ~500MB | 自定义模型 |
| PDF Classification | PDF 类型分类（扫描/文字/混合）| ~200MB | 轻量分类器 |

### B. POC 2 的完整内存占用数据

在 8GB 内存的 Windows 笔记本上处理 2020 全国卷（22 页 PDF）的内存占用分布：

| 阶段 | 内存 | 说明 |
|------|------|------|
| 空闲 | 0.3GB | Python 进程基础开销 |
| Layout Detection | 0.8GB | 版面检测模型加载 |
| MFR（峰值）| **2.8GB** | MFR 模型推理，张量计算 |
| OCR | 1.2GB | 文字识别 |
| Table Recognition | 1.0GB | 表格识别 |
| 最终输出 | 0.5GB | 结果序列化 |

**结论**：8GB 内存的笔记本可以稳定运行。4GB 内存可能会在 MFR 阶段 OOM。建议学生在处理大文件前关闭其他程序释放内存。

### C. 如果要用 MinerU 处理更多试卷

当试卷量增加到 5-10 份时，可以考虑的优化：

1. **模型预热**：第一次加载模型后保持进程存活，后续试卷直接推理，避免每次重新加载
2. **MFR 批处理**：将多页的公式区域合并成一个 batch 推理，减少 GPU/CPU 切换开销
3. **跳过无公式页**：对于纯文字页，跳过 MFR 阶段，直接 OCR

这些优化在课程中暂不涉及，但如果学生主动提出性能问题，可以告知这些方向。

### D. 百度 OCR vs MinerU 的成本对比

| 方案 | 单份试卷成本 | 月成本（10 份）| 年成本 |
|------|------------|--------------|--------|
| 百度 OCR API | ¥0.5-2 | ¥5-20 | ¥60-240 |
| MinerU（本地）| ¥0（不含电费）| ¥0 | ¥0 |
| MinerU + GPU 云 | ¥0.1-0.5 | ¥1-5 | ¥12-60 |

MinerU 是本地运行的（模型下载后不产生额外费用），但需要 4GB 模型存储 + 处理时的 2.8GB 内存。百度 OCR 是云端 API，按调用次数收费但不需要本地资源。
