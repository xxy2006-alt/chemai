#!/usr/bin/env python3
"""Generate rich ChemAI business flow diagram v3 - swim lanes, clean, comprehensive."""

FONT = 12
FONT_S = 11
FONT_TITLE = 14
FONT_H1 = 18

FLOW_X = 20
FLOW_W = 1780

parts = []

# ══════════════════════════════════════════════════════════════
# TITLE
# ══════════════════════════════════════════════════════════════
parts.append(
    '<mxCell id="title" value="ChemAI 智辅化学 — 核心业务流程图" '
    'style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;'
    f'whiteSpace=wrap;rounded=0;fontSize={FONT_H1};fontStyle=1;fontColor=#333333;" vertex="1" parent="1">'
    '<mxGeometry x="20" y="8" width="1780" height="32" as="geometry"/></mxCell>'
)

# ══════════════════════════════════════════════════════════════
# FLOW 1: 教师出题 → 四维审核 → 发布  (3 lanes)
# ══════════════════════════════════════════════════════════════
f1_y = 50
f1_h = 270

parts.append(
    '<mxCell id="F1_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F1F8E9;strokeColor=#558B2F;strokeWidth=1.5;arcSize=2;" '
    f'vertex="1" parent="1">'
    f'<mxGeometry x="{FLOW_X}" y="{f1_y}" width="{FLOW_W}" height="{f1_h}" as="geometry"/></mxCell>'
)
parts.append(
    '<mxCell id="F1_title" value="流程一：教师出题 → 四维审核 → 发布" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#558B2F;fontColor=#FFFFFF;'
    f'fontStyle=1;fontSize={FONT_TITLE};align=left;verticalAlign=middle;spacingLeft=10;strokeColor=#558B2F;strokeWidth=1.5;" '
    f'vertex="1" parent="1">'
    f'<mxGeometry x="{FLOW_X}" y="{f1_y}" width="{FLOW_W}" height="34" as="geometry"/></mxCell>'
)

f1_cy = f1_y + 40
f1_ch = f1_h - 44
f1_lw = (FLOW_W - 40) // 3

f1_lane_defs = [
    ("教师", "#2E7D32", "#E8F5E9"),
    ("Agent引擎", "#E65100", "#FFF3E0"),
    ("业务服务", "#6A1B9A", "#F3E5F5"),
]
for li, (lname, lcolor, lbg) in enumerate(f1_lane_defs):
    lx = FLOW_X + 20 + li * f1_lw
    parts.append(
        f'<mxCell id="F1L{li}" value="" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fillColor={lbg};strokeColor={lcolor};strokeWidth=1;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{lx}" y="{f1_cy}" width="{f1_lw}" height="{f1_ch}" as="geometry"/></mxCell>'
    )
    parts.append(
        f'<mxCell id="F1LT{li}" value="{lname}" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fillColor={lcolor};fontColor=#FFFFFF;'
        f'fontStyle=1;fontSize={FONT};align=center;verticalAlign=middle;strokeColor={lcolor};strokeWidth=1;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{lx}" y="{f1_cy}" width="{f1_lw}" height="24" as="geometry"/></mxCell>'
    )

# F1 Steps
f1_s_h = 42
f1_s_gap = 12
f1_s_y = f1_cy + 32

# Lane 0: 教师 (3 steps)
l0x = FLOW_X + 28
l0w = f1_lw - 16
f1_l0 = ["发起出题请求\n指定知识点/难度", "收到题目\n确认发布", "题目进入真题库\n学生可作答"]
for j, item in enumerate(f1_l0):
    iy = f1_s_y + j * (f1_s_h + f1_s_gap + 6)
    bg = "#C8E6C9" if j == 2 else "#FFFFFF"
    sw = 2 if j == 2 else 1.5
    fs = 1 if j == 2 else 0
    fc = "#1B5E20" if j == 2 else "#333333"
    parts.append(
        f'<mxCell id="F1A{j}" value="{item}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fillColor={bg};strokeColor=#2E7D32;strokeWidth={sw};'
        f'fontSize={FONT};fontColor={fc};arcSize=12;fontStyle={fs};" vertex="1" parent="1">'
        f'<mxGeometry x="{l0x}" y="{iy}" width="{l0w}" height="{f1_s_h}" as="geometry"/></mxCell>'
    )

# Lane 1: Agent (3 steps)
l1x = FLOW_X + 20 + f1_lw + 8
l1w = f1_lw - 16
f1_l1 = ["解析出题意图\n匹配题型模板", "调用题目生成\n组织化学题目", "组装题目包\n标注审核结果"]
for j, item in enumerate(f1_l1):
    iy = f1_s_y + j * (f1_s_h + f1_s_gap + 6)
    parts.append(
        f'<mxCell id="F1B{j}" value="{item}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#E65100;strokeWidth=1.5;'
        f'fontSize={FONT};fontColor=#333333;arcSize=12;" vertex="1" parent="1">'
        f'<mxGeometry x="{l1x}" y="{iy}" width="{l1w}" height="{f1_s_h}" as="geometry"/></mxCell>'
    )

# Lane 2: 业务服务 (4审核 diamonds 2x2 + 2 results)
l2x = FLOW_X + 20 + 2 * f1_lw + 8
l2w = f1_lw - 16
reviews = ["系数配平校验", "反应条件校验", "产物稳定性校验", "分子结构校验"]
dw = (l2w - 12) // 2
dh = 44
for j, item in enumerate(reviews):
    row = j // 2
    col = j % 2
    dx = l2x + col * (dw + 12)
    dy = f1_s_y + row * (dh + 10)
    parts.append(
        f'<mxCell id="F1R{j}" value="{item}" '
        f'style="rhombus;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#6A1B9A;strokeWidth=1.5;'
        f'fontSize={FONT_S};fontColor=#333333;" vertex="1" parent="1">'
        f'<mxGeometry x="{dx}" y="{dy}" width="{dw}" height="{dh}" as="geometry"/></mxCell>'
    )

result_y = f1_s_y + 2 * (dh + 10) + 6
rw = (l2w - 12) // 2
parts.append(
    f'<mxCell id="F1ROK" value="全部通过\n题目入库" '
    f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#C8E6C9;strokeColor=#2E7D32;strokeWidth=2;'
    f'fontSize={FONT_S};fontColor=#1B5E20;arcSize=12;fontStyle=1;" vertex="1" parent="1">'
    f'<mxGeometry x="{l2x}" y="{result_y}" width="{rw}" height="{f1_s_h}" as="geometry"/></mxCell>'
)
parts.append(
    f'<mxCell id="F1RFAIL" value="任一不通过\n退回重新生成" '
    f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFCDD2;strokeColor=#C62828;strokeWidth=2;'
    f'fontSize={FONT_S};fontColor=#B71C1C;arcSize=12;fontStyle=1;" vertex="1" parent="1">'
    f'<mxGeometry x="{l2x + rw + 12}" y="{result_y}" width="{rw}" height="{f1_s_h}" as="geometry"/></mxCell>'
)

# F1 arrows
def f_arrow(eid, src, dst, color, dashed=False):
    d = "1" if dashed else "0"
    parts.append(
        f'<mxCell id="{eid}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;'
        f'html=1;strokeColor={color};strokeWidth=1.5;endArrow=block;endFill=1;dashed={d};'
        f'exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" '
        f'edge="1" parent="1" source="{src}" target="{dst}">'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )

def v_arrow(eid, src, dst, color, dashed=False):
    d = "1" if dashed else "0"
    parts.append(
        f'<mxCell id="{eid}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;'
        f'html=1;strokeColor={color};strokeWidth=1.5;endArrow=block;endFill=1;dashed={d};'
        f'exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" '
        f'edge="1" parent="1" source="{src}" target="{dst}">'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )

f_arrow("F1E1", "F1A0", "F1B0", "#558B2F")
v_arrow("F1E2", "F1B0", "F1B1", "#E65100")
f_arrow("F1E3", "F1B1", "F1R0", "#6A1B9A")
v_arrow("F1E4", "F1R0", "F1ROK", "#2E7D32")
parts.append(
    '<mxCell id="F1E5" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;'
    'html=1;strokeColor=#C62828;strokeWidth=1.5;endArrow=block;endFill=1;dashed=1;'
    'exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" '
    'edge="1" parent="1" source="F1R1" target="F1RFAIL">'
    '<mxGeometry relative="1" as="geometry"/></mxCell>'
)
f_arrow("F1E6", "F1ROK", "F1B2", "#6A1B9A")
f_arrow("F1E7", "F1B2", "F1A1", "#558B2F")
v_arrow("F1E8", "F1A1", "F1A2", "#2E7D32")
# Fail loop back
parts.append(
    '<mxCell id="F1E9" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;'
    'html=1;strokeColor=#C62828;strokeWidth=1.5;endArrow=block;endFill=1;dashed=1;'
    'exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" '
    'edge="1" parent="1" source="F1RFAIL" target="F1B1">'
    '<mxGeometry relative="1" as="geometry"/></mxCell>'
)

# ══════════════════════════════════════════════════════════════
# FLOW 2: 答题卡OCR批改 → 诊断闭环  (4 lanes)
# ══════════════════════════════════════════════════════════════
f2_y = 330
f2_h = 340

parts.append(
    '<mxCell id="F2_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E3F2FD;strokeColor=#1565C0;strokeWidth=1.5;arcSize=2;" '
    f'vertex="1" parent="1">'
    f'<mxGeometry x="{FLOW_X}" y="{f2_y}" width="{FLOW_W}" height="{f2_h}" as="geometry"/></mxCell>'
)
parts.append(
    '<mxCell id="F2_title" value="流程二：答题卡OCR批改 → 诊断闭环" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#1565C0;fontColor=#FFFFFF;'
    f'fontStyle=1;fontSize={FONT_TITLE};align=left;verticalAlign=middle;spacingLeft=10;strokeColor=#1565C0;strokeWidth=1.5;" '
    f'vertex="1" parent="1">'
    f'<mxGeometry x="{FLOW_X}" y="{f2_y}" width="{FLOW_W}" height="34" as="geometry"/></mxCell>'
)

f2_cy = f2_y + 40
f2_ch = f2_h - 44
f2_lw = (FLOW_W - 40) // 4

f2_lane_defs = [
    ("教师", "#2E7D32", "#E8F5E9"),
    ("Agent引擎", "#E65100", "#FFF3E0"),
    ("业务服务", "#6A1B9A", "#F3E5F5"),
    ("学生/家长", "#00838F", "#E0F7FA"),
]
for li, (lname, lcolor, lbg) in enumerate(f2_lane_defs):
    lx = FLOW_X + 20 + li * f2_lw
    parts.append(
        f'<mxCell id="F2L{li}" value="" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fillColor={lbg};strokeColor={lcolor};strokeWidth=1;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{lx}" y="{f2_cy}" width="{f2_lw}" height="{f2_ch}" as="geometry"/></mxCell>'
    )
    parts.append(
        f'<mxCell id="F2LT{li}" value="{lname}" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fillColor={lcolor};fontColor=#FFFFFF;'
        f'fontStyle=1;fontSize={FONT};align=center;verticalAlign=middle;strokeColor={lcolor};strokeWidth=1;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{lx}" y="{f2_cy}" width="{f2_lw}" height="24" as="geometry"/></mxCell>'
    )

f2_s_y = f2_cy + 30
f2_s_h = 38
f2_s_gap = 8
f2_pad = 8

# Lane 0: 教师 (4 steps)
f2_l0 = [
    "上传答题卡图片\n（分批次）",
    "语音/文字指令\n发起批改",
    "查看批改进度",
    "确认批改结果",
]
l0x2 = FLOW_X + 28
l0w2 = f2_lw - 16
for j, item in enumerate(f2_l0):
    iy = f2_s_y + j * (f2_s_h + f2_s_gap)
    parts.append(
        f'<mxCell id="F2A{j}" value="{item}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#2E7D32;strokeWidth=1.5;'
        f'fontSize={FONT_S};fontColor=#333333;arcSize=10;" vertex="1" parent="1">'
        f'<mxGeometry x="{l0x2}" y="{iy}" width="{l0w2}" height="{f2_s_h}" as="geometry"/></mxCell>'
    )

# Lane 1: Agent (4 steps)
f2_l1 = [
    "接收上传任务\n创建OCR任务",
    "返回任务ID\n启动异步解析",
    "查询处理进度\n返回状态",
    "调用批改工具\n生成批改结果",
]
l1x2 = FLOW_X + 20 + f2_lw + f2_pad
l1w2 = f2_lw - 16
for j, item in enumerate(f2_l1):
    iy = f2_s_y + j * (f2_s_h + f2_s_gap)
    parts.append(
        f'<mxCell id="F2B{j}" value="{item}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#E65100;strokeWidth=1.5;'
        f'fontSize={FONT_S};fontColor=#333333;arcSize=10;" vertex="1" parent="1">'
        f'<mxGeometry x="{l1x2}" y="{iy}" width="{l1w2}" height="{f2_s_h}" as="geometry"/></mxCell>'
    )

# Lane 2: 业务服务 (4 steps)
f2_l2 = [
    "OCR文档解析\n双引擎并行",
    "图像预处理\n版面分析",
    "文字识别\n结构化输出",
    "答案比对\n智能评分",
]
l2x2 = FLOW_X + 20 + 2 * f2_lw + f2_pad
l2w2 = f2_lw - 16
for j, item in enumerate(f2_l2):
    iy = f2_s_y + j * (f2_s_h + f2_s_gap)
    parts.append(
        f'<mxCell id="F2C{j}" value="{item}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#6A1B9A;strokeWidth=1.5;'
        f'fontSize={FONT_S};fontColor=#333333;arcSize=10;" vertex="1" parent="1">'
        f'<mxGeometry x="{l2x2}" y="{iy}" width="{l2w2}" height="{f2_s_h}" as="geometry"/></mxCell>'
    )

# Lane 3: 学生/家长 (1 step at bottom)
f2_l3 = [
    "",
    "",
    "",
    "接收批改报告\n查看诊断结果",
]
l3x2 = FLOW_X + 20 + 3 * f2_lw + f2_pad
l3w2 = f2_lw - 16
for j, item in enumerate(f2_l3):
    iy = f2_s_y + j * (f2_s_h + f2_s_gap)
    if item:
        parts.append(
            f'<mxCell id="F2D{j}" value="{item}" '
            f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B2EBF2;strokeColor=#00838F;strokeWidth=2;'
            f'fontSize={FONT_S};fontColor=#006064;arcSize=10;fontStyle=1;" vertex="1" parent="1">'
            f'<mxGeometry x="{l3x2}" y="{iy}" width="{l3w2}" height="{f2_s_h}" as="geometry"/></mxCell>'
        )

# F2 arrows (horizontal cross-lane)
f2c = "#1565C0"
for s in range(4):
    parts.append(
        f'<mxCell id="F2H{s}a" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={f2c};strokeWidth=1.5;'
        f'endArrow=block;endFill=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="F2A{s}" target="F2B{s}">'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )
    parts.append(
        f'<mxCell id="F2H{s}b" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={f2c};strokeWidth=1.5;'
        f'endArrow=block;endFill=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="F2B{s}" target="F2C{s}">'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )

# Lane2 step4 -> Lane3 step4
parts.append(
    f'<mxCell id="F2H3c" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={f2c};strokeWidth=1.5;'
    f'endArrow=block;endFill=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="F2C3" target="F2D3">'
    f'<mxGeometry relative="1" as="geometry"/></mxCell>'
)

# F2 vertical arrows within lanes (step to step)
for s in range(3):
    for li in range(3):
        src_id = f"F2{'ABCD'[li]}{s}"
        dst_id = f"F2{'ABCD'[li]}{s+1}"
        parts.append(
            f'<mxCell id="F2V{li}{s}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#BDBDBD;strokeWidth=1.5;'
            f'endArrow=block;endFill=1;exitX=0.5;exitY=1;entryX=0.5;entryY=0;" edge="1" parent="1" source="{src_id}" target="{dst_id}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>'
        )

# ══════════════════════════════════════════════════════════════
# FLOW 3: 学生AI辅导 → 苏格拉底式引导  (3 lanes)
# ══════════════════════════════════════════════════════════════
f3_y = 680
f3_h = 280

parts.append(
    '<mxCell id="F3_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF3E0;strokeColor=#E65100;strokeWidth=1.5;arcSize=2;" '
    f'vertex="1" parent="1">'
    f'<mxGeometry x="{FLOW_X}" y="{f3_y}" width="{FLOW_W}" height="{f3_h}" as="geometry"/></mxCell>'
)
parts.append(
    '<mxCell id="F3_title" value="流程三：学生AI辅导 → 苏格拉底式引导" '
    'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#E65100;fontColor=#FFFFFF;'
    f'fontStyle=1;fontSize={FONT_TITLE};align=left;verticalAlign=middle;spacingLeft=10;strokeColor=#E65100;strokeWidth=1.5;" '
    f'vertex="1" parent="1">'
    f'<mxGeometry x="{FLOW_X}" y="{f3_y}" width="{FLOW_W}" height="34" as="geometry"/></mxCell>'
)

f3_cy = f3_y + 40
f3_ch = f3_h - 44
f3_lw = (FLOW_W - 40) // 3

f3_lane_defs = [
    ("学生", "#2E7D32", "#E8F5E9"),
    ("Agent引擎", "#E65100", "#FFF8E1"),
    ("辅导工具链", "#6A1B9A", "#F3E5F5"),
]
for li, (lname, lcolor, lbg) in enumerate(f3_lane_defs):
    lx = FLOW_X + 20 + li * f3_lw
    parts.append(
        f'<mxCell id="F3L{li}" value="" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fillColor={lbg};strokeColor={lcolor};strokeWidth=1;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{lx}" y="{f3_cy}" width="{f3_lw}" height="{f3_ch}" as="geometry"/></mxCell>'
    )
    parts.append(
        f'<mxCell id="F3LT{li}" value="{lname}" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fillColor={lcolor};fontColor=#FFFFFF;'
        f'fontStyle=1;fontSize={FONT};align=center;verticalAlign=middle;strokeColor={lcolor};strokeWidth=1;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{lx}" y="{f3_cy}" width="{f3_lw}" height="24" as="geometry"/></mxCell>'
    )

f3_s_y = f3_cy + 32
f3_s_h = 40
f3_s_gap = 10
f3_pad = 8

# Lane 0: 学生
f3_l0 = ["提出化学问题", "回答引导问题", "获得知识点拨\n（非直接答案）", "完成练习巩固"]
l0x3 = FLOW_X + 28
l0w3 = f3_lw - 16
for j, item in enumerate(f3_l0):
    iy = f3_s_y + j * (f3_s_h + f3_s_gap)
    parts.append(
        f'<mxCell id="F3A{j}" value="{item}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#2E7D32;strokeWidth=1.5;'
        f'fontSize={FONT_S};fontColor=#333333;arcSize=10;" vertex="1" parent="1">'
        f'<mxGeometry x="{l0x3}" y="{iy}" width="{l0w3}" height="{f3_s_h}" as="geometry"/></mxCell>'
    )

# Lane 1: Agent
f3_l1 = ["解析学生意图\n加载学生人设", "判断知识盲点\n设计引导问题", "苏格拉底式追问\n逐步引导思考", "诊断学习障碍\n推荐练习题"]
l1x3 = FLOW_X + 20 + f3_lw + f3_pad
l1w3 = f3_lw - 16
for j, item in enumerate(f3_l1):
    iy = f3_s_y + j * (f3_s_h + f3_s_gap)
    parts.append(
        f'<mxCell id="F3B{j}" value="{item}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#E65100;strokeWidth=1.5;'
        f'fontSize={FONT_S};fontColor=#333333;arcSize=10;" vertex="1" parent="1">'
        f'<mxGeometry x="{l1x3}" y="{iy}" width="{l1w3}" height="{f3_s_h}" as="geometry"/></mxCell>'
    )

# Lane 2: 辅导工具链
f3_l2 = ["知识图谱检索", "方程式配平工具", "物质结构分析", "错题本+间隔复习"]
l2x3 = FLOW_X + 20 + 2 * f3_lw + f3_pad
l2w3 = f3_lw - 16
for j, item in enumerate(f3_l2):
    iy = f3_s_y + j * (f3_s_h + f3_s_gap)
    parts.append(
        f'<mxCell id="F3C{j}" value="{item}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#6A1B9A;strokeWidth=1.5;'
        f'fontSize={FONT_S};fontColor=#333333;arcSize=10;" vertex="1" parent="1">'
        f'<mxGeometry x="{l2x3}" y="{iy}" width="{l2w3}" height="{f3_s_h}" as="geometry"/></mxCell>'
    )

# F3 arrows
f3c = "#E65100"
for s in range(4):
    parts.append(
        f'<mxCell id="F3H{s}a" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={f3c};strokeWidth=1.5;'
        f'endArrow=block;endFill=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="F3A{s}" target="F3B{s}">'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )
    parts.append(
        f'<mxCell id="F3H{s}b" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={f3c};strokeWidth=1.5;'
        f'endArrow=block;endFill=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="F3B{s}" target="F3C{s}">'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )

# F3 vertical arrows in Agent lane (reasoning loop, dashed)
for s in range(3):
    parts.append(
        f'<mxCell id="F3V{s}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#FFB74D;strokeWidth=1.5;'
        f'endArrow=block;endFill=1;dashed=1;exitX=0.5;exitY=1;entryX=0.5;entryY=0;" edge="1" parent="1" source="F3B{s}" target="F3B{s+1}">'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )

# ══════════════════════════════════════════════════════════════
# BOTTOM: KPI看板
# ══════════════════════════════════════════════════════════════
kpi_y = 970
kpi_h = 80

parts.append(
    '<mxCell id="KPI_bg" value="" '
    'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FAFAFA;strokeColor=#455A64;strokeWidth=1.5;arcSize=2;" '
    f'vertex="1" parent="1">'
    f'<mxGeometry x="{FLOW_X}" y="{kpi_y}" width="{FLOW_W}" height="{kpi_h}" as="geometry"/></mxCell>'
)

kpi_items = [
    ("OCR准确率", "100%", "#2E7D32"),
    ("批改效率", "6h → 45min", "#1565C0"),
    ("出题采纳率", "82%", "#6A1B9A"),
    ("学生提分", "+4.3分", "#E65100"),
    ("流式输出", "SSE + 心跳", "#00838F"),
    ("对话持久化", "Checkpoint", "#AD1457"),
    ("递归控制", "≤12轮", "#B71C1C"),
    ("工具数", "25领域+5浏览器", "#455A64"),
]
kpi_w = (FLOW_W - 40) // len(kpi_items)
for k, (label, value, color) in enumerate(kpi_items):
    kx = FLOW_X + 20 + k * kpi_w
    parts.append(
        f'<mxCell id="KPIL{k}" value="{label}" '
        f'style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;'
        f'whiteSpace=wrap;rounded=0;fontSize=10;fontColor=#757575;" vertex="1" parent="1">'
        f'<mxGeometry x="{kx}" y="{kpi_y + 6}" width="{kpi_w}" height="20" as="geometry"/></mxCell>'
    )
    parts.append(
        f'<mxCell id="KPIV{k}" value="{value}" '
        f'style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;'
        f'whiteSpace=wrap;rounded=0;fontSize={FONT_TITLE};fontStyle=1;fontColor={color};" vertex="1" parent="1">'
        f'<mxGeometry x="{kx}" y="{kpi_y + 28}" width="{kpi_w}" height="28" as="geometry"/></mxCell>'
    )
    if k < len(kpi_items) - 1:
        parts.append(
            f'<mxCell id="KPIS{k}" value="" '
            f'style="line;strokeColor=#E0E0E0;strokeWidth=1;fillColor=none;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{kx + kpi_w - 1}" y="{kpi_y + 15}" width="1" height="50" as="geometry"/></mxCell>'
        )

# ══════════════════════════════════════════════════════════════
# Assemble XML
# ══════════════════════════════════════════════════════════════
cells_xml = "\n        ".join(parts)
xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<mxfile>\n'
    '  <diagram name="核心业务流程图" id="chemai_flow_v3">\n'
    '    <mxGraphModel dx="1900" dy="1150" grid="0" gridSize="10" guides="1" '
    'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
    'pageWidth="1820" pageHeight="1080" math="0" shadow="0">\n'
    '      <root>\n'
    '        <mxCell id="0"/>\n'
    '        <mxCell id="1" parent="0"/>\n'
    f'        {cells_xml}\n'
    '      </root>\n'
    '    </mxGraphModel>\n'
    '  </diagram>\n'
    '</mxfile>'
)

out_path = r"D:\化学\architecture-diagrams\ChemAI-核心业务流程图.drawio"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(xml)

print(f"Saved: {out_path}")
print(f"Total cells: {len(parts)}")
