#!/usr/bin/env python3
"""ChemAI architecture diagram v4 - auto-height layers, no overflow, clean."""

# ── Constants ──
LAYER_X = 190
LAYER_W = 1460
TITLE_W = 130
COMP_H = 42       # component height (reduced from 52)
COMP_GAP = 8      # gap between components
COMP_PAD = 10     # padding inside layer
LABEL_H = 20      # group label height
LABEL_TOP = 4     # gap above label
ROW_GAP = 5       # gap between rows
LAYER_PAD_V = 12  # vertical padding (top+bottom combined)

layers_data = [
    {
        "name": "用户交互层", "color": "#2E7D32", "bg": "#E8F5E9",
        "groups": [
            {"label": "教师端", "items": ["出题组卷", "答题卡批改", "学情分析", "班级管理"]},
            {"label": "学生端", "items": ["AI辅导对话", "作业作答", "错题本", "学情报告"]},
            {"label": "家长端", "items": ["周报查看", "学习监督"]},
            {"label": "管理端", "items": ["后台管理", "LMS对接"]},
        ]
    },
    {
        "name": "API网关层", "color": "#1565C0", "bg": "#E3F2FD",
        "groups": [
            {"label": None, "items": ["统一路由分发", "JWT四角色认证", "SSE流式输出", "请求限流", "参数校验", "CORS跨域"]},
        ]
    },
    {
        "name": "Agent引擎层", "color": "#E65100", "bg": "#FFF3E0",
        "groups": [
            {"label": "推理核心", "items": ["ReAct推理引擎", "意图路由", "工具动态注册", "递归控制≤12轮"]},
            {"label": "人设系统", "items": ["学生人设(7工具)", "教师人设(8工具)", "辅导员人设(6工具)", "家长人设(2工具)"]},
            {"label": "安全护栏", "items": ["调用去重", "频率限制", "审批门禁", "敏感路由剥离"]},
            {"label": "运行时", "items": ["Checkpoint持久化", "SSE适配器", "文本去重", "15s心跳保活"]},
        ]
    },
    {
        "name": "业务服务层", "color": "#6A1B9A", "bg": "#F3E5F5",
        "groups": [
            {"label": "审核引擎", "items": ["系数配平校验", "反应条件校验", "产物稳定性校验", "分子结构校验"]},
            {"label": "AI能力", "items": ["LLM多模型调度", "三路Fallback", "题目智能生成", "学习障碍诊断"]},
            {"label": "OCR管道", "items": ["MinerU文档解析", "百度OCR", "分批次上传", "进度查询"]},
            {"label": "教学服务", "items": ["真题检索", "智能批改", "学情诊断", "间隔复习引擎"]},
            {"label": "调度", "items": ["定时任务", "报告生成", "通知推送"]},
        ]
    },
    {
        "name": "工具与技能层", "color": "#AD1457", "bg": "#FCE4EC",
        "groups": [
            {"label": "领域工具", "items": ["方程式配平", "物质结构分析", "实验模拟", "计算化学", "有机化学"]},
            {"label": "浏览器工具", "items": ["网页搜索", "真题检索", "资料抓取", "内容解析", "结果缓存"]},
        ]
    },
    {
        "name": "数据层", "color": "#00838F", "bg": "#E0F7FA",
        "groups": [
            {"label": "关系数据", "items": ["SQLite主库(WAL)", "23个数据模型", "版本迁移", "对话快照"]},
            {"label": "向量与文件", "items": ["ChromaDB向量库", "题库文件", "OCR结果存储", "文件存储"]},
        ]
    },
    {
        "name": "基础设施层", "color": "#455A64", "bg": "#ECEFF1",
        "groups": [
            {"label": None, "items": ["Docker容器化", "环境配置管理", "日志收集", "健康监控", "部署脚本"]},
        ]
    },
]


def calc_layer_height(layer):
    """Calculate the minimum height needed for a layer based on its content."""
    groups = layer["groups"]
    has_label = any(g["label"] for g in groups)
    max_items = max(len(g["items"]) for g in groups)

    if not has_label:
        # Single row of items
        return COMP_H + LAYER_PAD_V + 8
    else:
        # label + rows (cols = ceil(items/2), rows = ceil(items/cols))
        cols = (max_items + 1) // 2
        rows = (max_items + cols - 1) // cols
        content_h = LABEL_TOP + LABEL_H + rows * COMP_H + (rows - 1) * ROW_GAP
        return content_h + LAYER_PAD_V + 4


def render_layer(layer, y_offset):
    """Render a layer and return (cells, height)."""
    cells = []
    lh = calc_layer_height(layer)
    ly = y_offset
    color = layer["color"]
    bg = layer["bg"]
    lid = "L{}".format(layer["name"][:2])

    # Layer background
    cells.append(
        '<mxCell id="{}_bg" value="" '
        'style="rounded=1;whiteSpace=wrap;html=1;fillColor={};strokeColor={};strokeWidth=1.5;arcSize=2;" '
        'vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
            lid, bg, color, LAYER_X, ly, LAYER_W, lh
        )
    )

    # Layer title bar
    cells.append(
        '<mxCell id="{}_title" value="{}" '
        'style="rounded=0;whiteSpace=wrap;html=1;fillColor={};fontColor=#FFFFFF;'
        'fontStyle=1;fontSize=13;align=center;verticalAlign=middle;strokeColor={};strokeWidth=1.5;" '
        'vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
            lid, layer["name"], color, color, LAYER_X, ly, TITLE_W, lh
        )
    )

    groups = layer["groups"]
    area_x = LAYER_X + TITLE_W + COMP_PAD
    area_w = LAYER_W - TITLE_W - 2 * COMP_PAD
    n_groups = len(groups)

    if n_groups == 1:
        # Single group - spread items horizontally
        items = groups[0]["items"]
        n = len(items)
        comp_w = (area_w - (n - 1) * COMP_GAP) // n
        comp_y = ly + (lh - COMP_H) // 2
        for j, comp in enumerate(items):
            cx = area_x + j * (comp_w + COMP_GAP)
            cells.append(
                '<mxCell id="{}_c{}" value="{}" '
                'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={};'
                'strokeWidth=1;fontSize=12;fontColor=#333333;arcSize=12;" '
                'vertex="1" parent="1">'
                '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
                    lid, j, comp, color, cx, comp_y, comp_w, COMP_H
                )
            )
    else:
        # Multiple groups
        group_w = (area_w - (n_groups - 1) * COMP_GAP) // n_groups
        has_label = any(g["label"] for g in groups)

        for gi, group in enumerate(groups):
            gx = area_x + gi * (group_w + COMP_GAP)
            items = group["items"]
            n = len(items)

            if group["label"]:
                # Group label
                cells.append(
                    '<mxCell id="{}_g{}_lbl" value="{}" '
                    'style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;'
                    'whiteSpace=wrap;rounded=0;fontSize=11;fontStyle=1;fontColor={};" vertex="1" parent="1">'
                    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
                        lid, gi, group["label"], color, gx, ly + LABEL_TOP, group_w, LABEL_H
                    )
                )

                # Items below label
                label_bottom = ly + LABEL_TOP + LABEL_H + 2
                remaining_h = lh - (label_bottom - ly) - LAYER_PAD_V // 2

                if n <= 2:
                    # 1 row
                    comp_w = (group_w - (n - 1) * 5) // n
                    comp_y = label_bottom + (remaining_h - COMP_H) // 2
                    if comp_y < label_bottom:
                        comp_y = label_bottom
                    for j, comp in enumerate(items):
                        cx = gx + j * (comp_w + 5)
                        cells.append(
                            '<mxCell id="{}_g{}_c{}" value="{}" '
                            'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={};'
                            'strokeWidth=1;fontSize=11;fontColor=#333333;arcSize=10;" '
                            'vertex="1" parent="1">'
                            '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
                                lid, gi, j, comp, color, cx, comp_y, comp_w, COMP_H
                            )
                        )
                else:
                    # 2 rows
                    cols = (n + 1) // 2
                    comp_w = (group_w - (cols - 1) * 5) // cols
                    total_rows_h = 2 * COMP_H + ROW_GAP
                    start_y = label_bottom + max(0, (remaining_h - total_rows_h) // 2)
                    for j, comp in enumerate(items):
                        row = j // cols
                        col = j % cols
                        cx = gx + col * (comp_w + 5)
                        cy = start_y + row * (COMP_H + ROW_GAP)
                        cells.append(
                            '<mxCell id="{}_g{}_c{}" value="{}" '
                            'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={};'
                            'strokeWidth=1;fontSize=11;fontColor=#333333;arcSize=10;" '
                            'vertex="1" parent="1">'
                            '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
                                lid, gi, j, comp, color, cx, cy, comp_w, COMP_H
                            )
                        )
            else:
                # No label - spread items
                comp_w = (group_w - (n - 1) * 5) // n
                comp_y = ly + (lh - COMP_H) // 2
                for j, comp in enumerate(items):
                    cx = gx + j * (comp_w + 5)
                    cells.append(
                        '<mxCell id="{}_g{}_c{}" value="{}" '
                        'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={};'
                        'strokeWidth=1;fontSize=12;fontColor=#333333;arcSize=12;" '
                        'vertex="1" parent="1">'
                        '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
                            lid, gi, j, comp, color, cx, comp_y, comp_w, COMP_H
                        )
                    )

    return cells, lh


# ── Build all layers ──
all_cells = []

# Title
all_cells.append(
    '<mxCell id="title" value="ChemAI 智辅化学 — 系统架构图" '
    'style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;'
    'whiteSpace=wrap;rounded=0;fontSize=20;fontStyle=1;fontColor=#333333;" vertex="1" parent="1">'
    '<mxGeometry x="190" y="8" width="1460" height="32" as="geometry"/></mxCell>'
)

# Place layers sequentially with dynamic heights
LAYER_GAP = 10
start_y = 48
current_y = start_y
layer_heights = []

for layer in layers_data:
    cells, lh = render_layer(layer, current_y)
    all_cells.extend(cells)
    layer_heights.append((layer["name"], lh, current_y))
    current_y += lh + LAYER_GAP

# ── Left panel: 评测体系 ──
total_layers_h = current_y - start_y
panel_h = total_layers_h

lp_x = 20
lp_y = start_y
lp_w = 150

all_cells.append(
    '<mxCell id="LP_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF8E1;strokeColor=#E65100;strokeWidth=1.5;arcSize=2;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
        lp_x, lp_y, lp_w, panel_h
    )
)
all_cells.append(
    '<mxCell id="LP_title" value="评测体系" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#E65100;fontColor=#FFFFFF;'
    'fontStyle=1;fontSize=13;align=center;verticalAlign=middle;strokeColor=#E65100;strokeWidth=1.5;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="36" as="geometry"/></mxCell>'.format(
        lp_x, lp_y, lp_w
    )
)

left_groups = [
    {"label": "评测框架", "items": ["三层评测", "14个维度", "111个场景"]},
    {"label": "评测类型", "items": ["确定性评测 86", "API评测 36"]},
    {"label": "关键指标", "items": ["路由准确率 100%", "OCR准确率 100%", "化学LLM 100%"]},
]
ly_cursor = lp_y + 42
for gi, grp in enumerate(left_groups):
    all_cells.append(
        '<mxCell id="LP_g{}_lbl" value="{}" '
        'style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;'
        'whiteSpace=wrap;rounded=0;fontSize=11;fontStyle=1;fontColor=#E65100;" vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="18" as="geometry"/></mxCell>'.format(
            gi, grp["label"], lp_x + 5, ly_cursor, lp_w - 10
        )
    )
    ly_cursor += 22
    for j, item in enumerate(grp["items"]):
        all_cells.append(
            '<mxCell id="LP_g{}_c{}" value="{}" '
            'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#E65100;'
            'strokeWidth=1;fontSize=11;fontColor=#333333;arcSize=10;" '
            'vertex="1" parent="1">'
            '<mxGeometry x="{}" y="{}" width="{}" height="28" as="geometry"/></mxCell>'.format(
                gi, j, item, lp_x + 10, ly_cursor, lp_w - 20
            )
        )
        ly_cursor += 32
    ly_cursor += 6

# ── Right panel: 安全治理 ──
rp_x = 1660
rp_y = start_y
rp_w = 150

all_cells.append(
    '<mxCell id="RP_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFEBEE;strokeColor=#B71C1C;strokeWidth=1.5;arcSize=2;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
        rp_x, rp_y, rp_w, panel_h
    )
)
all_cells.append(
    '<mxCell id="RP_title" value="安全治理" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#B71C1C;fontColor=#FFFFFF;'
    'fontStyle=1;fontSize=13;align=center;verticalAlign=middle;strokeColor=#B71C1C;strokeWidth=1.5;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="36" as="geometry"/></mxCell>'.format(
        rp_x, rp_y, rp_w
    )
)

right_groups = [
    {"label": "身份认证", "items": ["JWT四角色认证", "权限矩阵控制"]},
    {"label": "运行护栏", "items": ["调用去重", "频率限制", "审批门禁", "递归控制≤12轮"]},
    {"label": "内容安全", "items": ["危化品红线", "敏感路由剥离", "操作审计日志"]},
]
ry_cursor = rp_y + 42
for gi, grp in enumerate(right_groups):
    all_cells.append(
        '<mxCell id="RP_g{}_lbl" value="{}" '
        'style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;'
        'whiteSpace=wrap;rounded=0;fontSize=11;fontStyle=1;fontColor=#B71C1C;" vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="18" as="geometry"/></mxCell>'.format(
            gi, grp["label"], rp_x + 5, ry_cursor, rp_w - 10
        )
    )
    ry_cursor += 22
    for j, item in enumerate(grp["items"]):
        all_cells.append(
            '<mxCell id="RP_g{}_c{}" value="{}" '
            'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#B71C1C;'
            'strokeWidth=1;fontSize=11;fontColor=#333333;arcSize=10;" '
            'vertex="1" parent="1">'
            '<mxGeometry x="{}" y="{}" width="{}" height="28" as="geometry"/></mxCell>'.format(
                gi, j, item, rp_x + 10, ry_cursor, rp_w - 20
            )
        )
        ry_cursor += 32
    ry_cursor += 6

# ── Bottom: 关键数据流 ──
btm_y = current_y + 4
btm_h = 72

all_cells.append(
    '<mxCell id="BT_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F5F5F5;strokeColor=#455A64;strokeWidth=1.5;arcSize=2;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
        LAYER_X, btm_y, LAYER_W, btm_h
    )
)
all_cells.append(
    '<mxCell id="BT_title" value="关键数据流" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#455A64;fontColor=#FFFFFF;'
    'fontStyle=1;fontSize=13;align=center;verticalAlign=middle;strokeColor=#455A64;strokeWidth=1.5;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
        LAYER_X, btm_y, TITLE_W, btm_h
    )
)
flows = [
    "出题流: 教师 → Agent → 四维审核 → 发布",
    "批改流: 上传 → OCR → 批改 → 诊断 → 报告",
    "辅导流: 学生 → Agent → 工具调用 → 苏格拉底引导",
]
flow_w = (LAYER_W - TITLE_W - 2 * COMP_PAD - 2 * COMP_GAP) // 3
for k, flow in enumerate(flows):
    fx = LAYER_X + TITLE_W + COMP_PAD + k * (flow_w + COMP_GAP)
    all_cells.append(
        '<mxCell id="BT_{}" value="{}" '
        'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#455A64;'
        'strokeWidth=1;fontSize=12;fontColor=#333333;arcSize=10;" '
        'vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="52" as="geometry"/></mxCell>'.format(
            k, flow, fx, btm_y + 10, flow_w
        )
    )

# ── Debug: print layer heights ──
for name, h, y in layer_heights:
    print(f"  {name}: y={y}, h={h}")

print(f"\nTotal height: {btm_y + btm_h - start_y + 20}")

# ── Assemble XML ──
cells_xml = "\n        ".join(all_cells)
canvas_h = btm_y + btm_h + 20

xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<mxfile>\n'
    '  <diagram name="系统架构图" id="chemai_arch_v4">\n'
    '    <mxGraphModel dx="1900" dy="1100" grid="0" gridSize="10" guides="1" '
    'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
    'pageWidth="1820" pageHeight="{}" math="0" shadow="0">\n'
    '      <root>\n'
    '        <mxCell id="0"/>\n'
    '        <mxCell id="1" parent="0"/>\n'
    '        {}\n'
    '      </root>\n'
    '    </mxGraphModel>\n'
    '  </diagram>\n'
    '</mxfile>'
).format(canvas_h, cells_xml)

out_path = r"D:\化学\architecture-diagrams\ChemAI-系统架构图.drawio"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(xml)

print(f"\nSaved: {out_path}")
print(f"Total cells: {len(all_cells)}")
