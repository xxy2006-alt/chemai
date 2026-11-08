"""复杂结构式渲染服务（ADR-0005 H1）。

AI 出题产出的 [SMILES:...] 标记 → RDKit 渲染 2D 结构图 PNG → 存 data/question_images/。
SMILES 解析失败返回 None，调用方退化为文本，不阻断出题。
"""
import hashlib
import io
import os
import re

from rdkit import Chem
from rdkit.Chem import Draw

IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "question_images")


def _canonical_smiles(smiles: str) -> str | None:
    """解析并返回 canonical SMILES；非法返回 None（不抛异常）"""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return Chem.MolToSmiles(mol)
    except Exception:
        return None


# 白名单 canonical 缓存：{canonical: 教材白名单 SMILES}
_WHITELIST_CANONICAL: dict[str, str] | None = None


def _whitelist_canonical() -> dict[str, str]:
    """构建白名单 canonical 索引（惰性）。

    用户反馈「生成的有机化学结构式很多都有问题（图是错的）」：
    LLM 输出的 [SMILES:...] 即使语法合法，写法/环表示可能与教材不一致。
    高频高中结构一律以人工验证过的白名单 SMILES 为准 —— 等价结构（canonical
    相同）归一化到白名单写法渲染，保证图是标准教材式。"""
    global _WHITELIST_CANONICAL
    if _WHITELIST_CANONICAL is None:
        _WHITELIST_CANONICAL = {}
        for _name, _s in COMMON_STRUCTURES.items():
            _c = _canonical_smiles(_s)
            if _c:
                _WHITELIST_CANONICAL[_c] = _s
    return _WHITELIST_CANONICAL


def render_smiles_png(smiles: str, out_dir: str = IMG_DIR, size: int = 250) -> str | None:
    """把 SMILES 渲染成 2D 结构图 PNG，返回文件路径。

    化学合法性验证（用户反馈「结构式不对」）：
    - MolFromSmiles 失败（价态/芳香环 kekulization 等 sanitize 错误）→ None；
    - 显式 SanitizeMol 二次校验 → 异常返回 None；
    - canonical 与白名单等价 → 归一化到教材白名单 SMILES 渲染。
    失败返回 None（不抛异常），调用方退化为文本；相同 SMILES 命中缓存返回同一路径。
    """
    if not smiles or not smiles.strip():
        return None
    s = smiles.strip()

    # 1. 白名单归一：等价结构用教材写法（图必须"正确标准"）
    canonical = _canonical_smiles(s)
    if canonical:
        whitelist = _whitelist_canonical().get(canonical)
        if whitelist and whitelist != s:
            s = whitelist

    # 2. 化学合法性：解析（含价态/芳香性 sanitize）+ 显式二次校验
    mol = Chem.MolFromSmiles(s)
    if mol is None:
        return None
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        return None

    os.makedirs(out_dir, exist_ok=True)
    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]
    path = os.path.join(out_dir, f"{digest}.png")
    if os.path.exists(path):
        return path

    img = Draw.MolToImage(mol, size=(size, size))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    return path


# [SMILES:...] 标记（AI 出题产出）。SMILES 可含括号原子（如 [N+](...)），故按括号单元匹配。
_SMILES_MARKER_RE = re.compile(r"\[SMILES:((?:[^\[\]]|\[[^\[\]]*\])+)\]")


def replace_smiles_markers(content: str, out_dir: str = IMG_DIR) -> str:
    """把题目 content 里的 [SMILES:...] 标记替换为结构图 <img> 引用。

    渲染成功 → `<img src="/static/question_images/{hash}.png" alt="{smiles}">`；
    非法 SMILES 渲染失败 → 退化为 `\ce{{...}}` 文本（不抛异常、不阻断出题）；
    无标记的 content 原样返回。
    """
    if not content or "[SMILES:" not in content:
        return content

    def _repl(m: re.Match) -> str:
        smiles = m.group(1).strip()
        path = render_smiles_png(smiles, out_dir=out_dir)
        if not path:
            return f"\\ce{{{smiles}}}"
        return f'<img src="/static/question_images/{os.path.basename(path)}" alt="{smiles}">'

    return _SMILES_MARKER_RE.sub(_repl, content)


# 常见高中有机结构 → SMILES（白名单：人工验证过的教材标准写法。
# 2026-08-14 用户反馈：有机题要有结构图 + 「结构式不对」→ 高频结构一律白名单；
# canonical 等价时归一化到这里的写法渲染，保证图正确标准）。
# 名称按长度降序匹配，避免"苯"吃掉"苯酚/甲苯"等复合词。
COMMON_STRUCTURES: dict[str, str] = {
    "乙酸乙酯": "CCOC(=O)C",
    "苯乙烯": "C=Cc1ccccc1",
    "环己烷": "C1CCCCC1",
    "苯甲酸": "OC(=O)c1ccccc1",
    "硝基苯": "[O-][N+](=O)c1ccccc1",
    "苯酚": "Oc1ccccc1",
    "苯胺": "Nc1ccccc1",
    "乙二醇": "OCCO",
    "甘油": "OCC(O)CO",
    "甲苯": "Cc1ccccc1",
    "氯苯": "Clc1ccccc1",
    "乙醛": "CC=O",
    "丙酮": "CC(=O)C",
    "甲醛": "C=O",
    "乙酸": "CC(=O)O",
    "乙醇": "CCO",
    "乙炔": "C#C",
    "乙烯": "C=C",
    "苯": "C1=CC=CC=C1",
}
_COMMON_RE = re.compile("(" + "|".join(sorted(COMMON_STRUCTURES, key=len, reverse=True)) + ")")

# 名称兜底触发语境（用户反馈「碰到有机化学的名字就自动生成结构式，有时候不用」）：
# 仅当名称出现在"结构相关"语境附近才补图，避免"乙醇能与钠反应"这类不需要图的地方乱插图。
_STRUCTURE_CONTEXT_RE = re.compile(
    r"结构|简式|示性式|键线式|如图|图示|示意图|空间构型|分子构型|立体结构|分子结构|的组成|的构造|的骨架"
)
_CONTEXT_WINDOW = 20  # 名称前后各 20 字符内出现语境词才触发

# 常见有机分子式（LaTeX 写法，已归一化去 _/{}/\mathrm 并小写）→ (名称, SMILES)
# 覆盖"$CH_3CH_2OH$ 含醛基"这类分子式判断题，让分子式也能配结构图。
COMMON_FORMULAS: dict[str, tuple[str, str]] = {
    "ch3ch2oh": ("乙醇", "CCO"),
    "c2h5oh": ("乙醇", "CCO"),
    "ch3cooh": ("乙酸", "CC(=O)O"),
    "ch3cho": ("乙醛", "CC=O"),
    "ch3cooc2h5": ("乙酸乙酯", "CCOC(=O)C"),
    "c6h5oh": ("苯酚", "Oc1ccccc1"),
    "c6h6": ("苯", "C1=CC=CC=C1"),
    "c2h4": ("乙烯", "C=C"),
    "c2h2": ("乙炔", "C#C"),
}
_FORMULA_BLOCK_RE = re.compile(r"\$[^$]{1,60}\$")


def _normalize_formula(f: str) -> str:
    return (
        f.replace("\\mathrm", "").replace("\\text", "")
        .replace("_", "").replace("{", "").replace("}", "")
        .replace(" ", "").replace("$", "").lower()
    )


def enrich_organic_structures(content: str, out_dir: str = IMG_DIR) -> str:
    """有机题结构图兜底：常见有机物名在"结构相关语境"自动补结构图 <img>。

    LLM 生成有机题时经常不输出 [SMILES:...] 标记（即使 prompt 已要求），
    导致题目没有结构图。本函数扫描文本中的常见有机结构名称，
    仅当名称前后 _CONTEXT_WINDOW 字符内出现结构语境词（结构/简式/如图等）
    才在名称首次出现处插入 RDKit 渲染的结构图 —— 避免"乙醇能与钠反应"
    这类不需要结构图的地方乱插图（2026-08-14 用户反馈）。
    已有结构图（question_images）时整体跳过；非法 SMILES 跳过对应名称。
    幂等：已有图时不再重复插入。"""
    if not content or "question_images" in content:
        return content

    inserted: set[str] = set()

    def _repl(m: re.Match) -> str:
        name = m.group(1)
        if name in inserted:
            return name
        # 语境触发：名称附近必须有结构相关词（否则"提到名字就配图"过度）
        start = max(0, m.start() - _CONTEXT_WINDOW)
        end = min(len(content), m.end() + _CONTEXT_WINDOW)
        if not _STRUCTURE_CONTEXT_RE.search(content[start:end]):
            return name
        smiles = COMMON_STRUCTURES.get(name)
        if not smiles:
            return name
        path = render_smiles_png(smiles, out_dir=out_dir)
        if not path:
            return name
        inserted.add(name)
        return f'{name}<img src="/static/question_images/{os.path.basename(path)}" alt="{name}结构式">'

    content = _COMMON_RE.sub(_repl, content)

    # 分子式 → 结构图（$CH_3CH_2OH$ 等；命中后保留原公式并追加结构图。
    # 分子式出现在选项/题干时结构图通常是题意所需，不做语境限制）
    def _formula_repl(m: re.Match) -> str:
        block = m.group(0)
        hit = COMMON_FORMULAS.get(_normalize_formula(block))
        if not hit:
            return block
        name, smiles = hit
        if name in inserted:
            return block
        path = render_smiles_png(smiles, out_dir=out_dir)
        if not path:
            return block
        inserted.add(name)
        return f'{block}<img src="/static/question_images/{os.path.basename(path)}" alt="{name}结构式">'

    return _FORMULA_BLOCK_RE.sub(_formula_repl, content)


def enrich_organic_content(content: str, out_dir: str = IMG_DIR) -> str:
    """[SMILES:...] 标记替换 + 常见有机结构名称兜底补图（一次调用全覆盖）"""
    content = replace_smiles_markers(content, out_dir=out_dir)
    return enrich_organic_structures(content, out_dir=out_dir)
