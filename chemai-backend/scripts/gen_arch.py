#!/usr/bin/env python3
"""Generate clean ChemAI architecture diagram - no code names, no meta text, uniform fonts."""

# ── Layout constants ──
LAYER_X = 180
LAYER_W = 1440
TITLE_W = 130
COMP_H = 58
COMP_GAP = 12
COMP_PAD = 10

layers = [
    {"name": "用户交互层", "y": 45, "h": 90, "color": "#43A047", "bg": "#E8F5E9",
     "components": ["教师端", "学生端", "家长端", "管理后台", "LMS对接"]},
    {"name": "API网关层", "y": 150, "h": 90, "color": "#1E88E5", "bg": "#E3F2FD",
     "components": ["统一路由", "JWT认证", "SSE流式输出", "请求限流", "参数校验"]},
    {"name": "Agent引擎层", "y": 255, "h": 105, "color": "#FB8C00", "bg": "#FFF3E0",
     "components": ["ReAct推理引擎", "Persona人设系统", "GuardState安全护栏", "Checkpoint持久化", "工具动态注册", "SSE适配器"]},
    {"name": "业务服务层", "y": 375, "h": 105, "color": "#8E24AA", "bg": "#F3E5F5",
     "components": ["四维审核引擎", "LLM多模型调度", "OCR双引擎", "真题检索", "智能批改", "学情诊断", "间隔复习", "定时任务"]},
    {"name": "技能层", "y": 495, "h": 90, "color": "#E91E63", "bg": "#FCE4EC",
     "components": ["化学方程式", "物质结构", "实验模拟", "计算化学", "有机化学"]},
    {"name": "数据层", "y": 600, "h": 90, "color": "#00ACC1", "bg": "#E0F7FA",
     "components": ["SQLite主库", "对话快照", "ChromaDB向量库", "题库文件", "文件存储"]},
    {"name": "基础设施层", "y": 705, "h": 75, "color": "#546E7A", "bg": "#ECEFF1",
     "components": ["Docker容器", "环境配置", "日志监控", "部署脚本"]},
]

parts = []

# ── Title ──
parts.append(
    '<mxCell id="title" value="ChemAI 智辅化学 — 系统架构图" '
    'style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;'
    'whiteSpace=wrap;rounded=0;fontSize=18;fontStyle=1;fontColor=#333333;" vertex="1" parent="1">'
    '<mxGeometry x="180" y="8" width="1440" height="30" as="geometry"/></mxCell>'
)

# ── 7 Layers ──
for i, layer in enumerate(layers):
    ly = layer["y"]
    lh = layer["h"]
    color = layer["color"]
    bg = layer["bg"]
    lid = "L{}".format(i + 1)

    # Layer background
    parts.append(
        '<mxCell id="{}_bg" value="" '
        'style="rounded=1;whiteSpace=wrap;html=1;fillColor={};strokeColor={};strokeWidth=1;arcSize=3;" '
        'vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
            lid, bg, color, LAYER_X, ly, LAYER_W, lh
        )
    )

    # Layer title bar (colored left strip)
    parts.append(
        '<mxCell id="{}_title" value="{}" '
        'style="rounded=0;whiteSpace=wrap;html=1;fillColor={};fontColor=#FFFFFF;'
        'fontStyle=1;fontSize=14;align=center;verticalAlign=middle;" '
        'vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
            lid, layer["name"], color, LAYER_X, ly, TITLE_W, lh
        )
    )

    # Components
    comps = layer["components"]
    n = len(comps)
    area_x = LAYER_X + TITLE_W + COMP_PAD
    area_w = LAYER_W - TITLE_W - 2 * COMP_PAD
    comp_w = int((area_w - (n - 1) * COMP_GAP) / n)
    comp_y = int(ly + (lh - COMP_H) / 2)

    for j, comp in enumerate(comps):
        cx = int(area_x + j * (comp_w + COMP_GAP))
        parts.append(
            '<mxCell id="{}_c{}" value="{}" '
            'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={};'
            'strokeWidth=1;fontSize=13;fontColor=#333333;arcSize=10;" '
            'vertex="1" parent="1">'
            '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
                lid, j + 1, comp, color, cx, comp_y, comp_w, COMP_H
            )
        )

# ── Left panel: 评测体系 ──
lp_x, lp_y, lp_w, lp_h = 20, 45, 140, 735
parts.append(
    '<mxCell id="LP_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF8E1;strokeColor=#FF8F00;strokeWidth=1;arcSize=3;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
        lp_x, lp_y, lp_w, lp_h
    )
)
parts.append(
    '<mxCell id="LP_title" value="评测体系" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#FF8F00;fontColor=#FFFFFF;'
    'fontStyle=1;fontSize=14;align=center;verticalAlign=middle;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="38" as="geometry"/></mxCell>'.format(
        lp_x, lp_y, lp_w, )
)
left_items = [
    "三层评测框架", "14个维度", "111个场景",
    "确定性评测 86", "API评测 36",
    "路由准确率 100%", "OCR准确率 100%", "化学LLM 100%",
]
for k, item in enumerate(left_items):
    iy = lp_y + 48 + k * 40
    parts.append(
        '<mxCell id="LP_{}" value="{}" '
        'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#FF8F00;'
        'strokeWidth=1;fontSize=12;fontColor=#333333;arcSize=10;" '
        'vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="32" as="geometry"/></mxCell>'.format(
            k, item, lp_x + 10, iy, lp_w - 20
        )
    )

# ── Right panel: 安全治理 ──
rp_x, rp_y, rp_w, rp_h = 1640, 45, 140, 735
parts.append(
    '<mxCell id="RP_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFEBEE;strokeColor=#C62828;strokeWidth=1;arcSize=3;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
        rp_x, rp_y, rp_w, rp_h
    )
)
parts.append(
    '<mxCell id="RP_title" value="安全治理" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#C62828;fontColor=#FFFFFF;'
    'fontStyle=1;fontSize=14;align=center;verticalAlign=middle;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="38" as="geometry"/></mxCell>'.format(
        rp_x, rp_y, rp_w, )
)
right_items = [
    "JWT四角色认证", "权限矩阵", "调用去重",
    "频率限制", "审批门禁", "递归控制 ≤12轮",
    "危化品红线", "操作审计",
]
for k, item in enumerate(right_items):
    iy = rp_y + 48 + k * 40
    parts.append(
        '<mxCell id="RP_{}" value="{}" '
        'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#C62828;'
        'strokeWidth=1;fontSize=12;fontColor=#333333;arcSize=10;" '
        'vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="32" as="geometry"/></mxCell>'.format(
            k, item, rp_x + 10, iy, rp_w - 20
        )
    )

# ── Bottom: 关键数据流 ──
btm_y, btm_h = 795, 70
parts.append(
    '<mxCell id="BT_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F5F5F5;strokeColor=#757575;strokeWidth=1;arcSize=3;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
        LAYER_X, btm_y, LAYER_W, btm_h
    )
)
parts.append(
    '<mxCell id="BT_title" value="关键数据流" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#757575;fontColor=#FFFFFF;'
    'fontStyle=1;fontSize=14;align=center;verticalAlign=middle;" '
    'vertex="1" parent="1">'
    '<mxGeometry x="{}" y="{}" width="{}" height="{}" as="geometry"/></mxCell>'.format(
        LAYER_X, btm_y, TITLE_W, btm_h
    )
)
flows = [
    "出题流: 教师 → Agent → 四维审核 → 发布",
    "批改流: 上传 → OCR → 批改 → 诊断 → 报告",
    "辅导流: 学生 → Agent → 工具调用 → 引导输出",
]
flow_w = int((LAYER_W - TITLE_W - 2 * COMP_PAD - 2 * COMP_GAP) / 3)
for k, flow in enumerate(flows):
    fx = LAYER_X + TITLE_W + COMP_PAD + k * (flow_w + COMP_GAP)
    parts.append(
        '<mxCell id="BT_{}" value="{}" '
        'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#757575;'
        'strokeWidth=1;fontSize=12;fontColor=#333333;arcSize=10;" '
        'vertex="1" parent="1">'
        '<mxGeometry x="{}" y="{}" width="{}" height="50" as="geometry"/></mxCell>'.format(
            k, flow, fx, btm_y + 10, flow_w
        )
    )

# ── Assemble XML ──
cells_xml = "\n        ".join(parts)
xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<mxfile>\n'
    '  <diagram name="系统架构图" id="chemai_arch">\n'
    '    <mxGraphModel dx="1800" dy="950" grid="0" gridSize="10" guides="1" '
    'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
    'pageWidth="1800" pageHeight="900" math="0" shadow="0">\n'
    '      <root>\n'
    '        <mxCell id="0"/>\n'
    '        <mxCell id="1" parent="0"/>\n'
    '        {}\n'
    '      </root>\n'
    '    </mxGraphModel>\n'
    '  </diagram>\n'
    '</mxfile>'
).format(cells_xml)

out_path = r"D:\化学\architecture-diagrams\ChemAI-系统架构图.drawio"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(xml)

print("Saved: {}".format(out_path))
print("Total cells: {}".format(len(parts)))
