import { useEffect, useState, type ReactNode } from 'react'
import {
  Search,
  FileText,
  Activity,
  BookOpen,
  FlaskConical,
  Scale,
  ClipboardList,
  Upload,
  Send,
  Globe,
  Wrench,
  ChevronDown,
  ChevronRight,
  LayoutGrid,
  UserRound,
  FolderOpen,
  Pencil,
  Terminal,
  ListTree,
  ListChecks,
  ShieldCheck,
  FilePen,
  MousePointerClick,
  Keyboard,
  Camera,
} from 'lucide-react'
import { Badge } from '../ui'
import { ToolResultView } from './tool-renderers'
import type { ToolStatus } from '../../lib/agent-sse'

/** 全部工具的展示元数据（DSH 式工作卡：图标 + 中文动作说明） */
export const TOOL_META: Record<string, { label: string; icon: ReactNode }> = {
  search_exam_bank: { label: '搜索真题', icon: <Search size={14} /> },
  generate_questions: { label: 'AI 出题', icon: <FileText size={14} /> },
  diagnose_barrier: { label: '障碍诊断', icon: <Activity size={14} /> },
  chemistry_tutor: { label: '智能辅导', icon: <BookOpen size={14} /> },
  simulate_experiment: { label: '模拟实验', icon: <FlaskConical size={14} /> },
  balance_equation: { label: '配平审核', icon: <Scale size={14} /> },
  weekly_report: { label: '生成周报', icon: <ClipboardList size={14} /> },
  import_exam_paper: { label: '导入试卷', icon: <Upload size={14} /> },
  assign_adaptive_practice: { label: '布置练习', icon: <Send size={14} /> },
  web_search: { label: '联网搜索', icon: <Globe size={14} /> },
  /* 面板类工具（component 内联面板配套） */
  show_exam_workbench: { label: '打开出题工作台', icon: <LayoutGrid size={14} /> },
  show_diagnosis: { label: '展示学情诊断', icon: <Activity size={14} /> },
  show_students: { label: '查找学生', icon: <UserRound size={14} /> },
  /* 文件与命令（四件套） */
  read: { label: '读取文件', icon: <FileText size={14} /> },
  write: { label: '写入文件', icon: <FilePen size={14} /> },
  edit: { label: '编辑文件', icon: <Pencil size={14} /> },
  find: { label: '查找文件', icon: <FolderOpen size={14} /> },
  grep: { label: '搜索内容', icon: <ListTree size={14} /> },
  bash: { label: '执行命令', icon: <Terminal size={14} /> },
  plan_task: { label: '任务规划', icon: <ListChecks size={14} /> },
  request_approval: { label: '请求批准', icon: <ShieldCheck size={14} /> },
  /* 题库 */
  save_to_bank: { label: '保存题库', icon: <FileText size={14} /> },
  list_banks: { label: '题库列表', icon: <ListTree size={14} /> },
  delete_bank: { label: '删除题库', icon: <ListChecks size={14} /> },
  /* 学情记忆 / 学习计划 / 家长报告 */
  memory_student_get: { label: '查询学生记忆', icon: <BookOpen size={14} /> },
  memory_teacher_get: { label: '查询教师偏好', icon: <BookOpen size={14} /> },
  generate_learning_plan: { label: '生成学习计划', icon: <ClipboardList size={14} /> },
  send_learning_plan: { label: '发送学习计划', icon: <Send size={14} /> },
  generate_parent_report: { label: '生成家长报告', icon: <ClipboardList size={14} /> },
  send_report_to_parent: { label: '发送家长报告', icon: <Send size={14} /> },
  /* 辅导工具 */
  ionic_equation_tutor: { label: '离子方程式辅导', icon: <BookOpen size={14} /> },
  stoichiometry_tutor: { label: '化学计量辅导', icon: <BookOpen size={14} /> },
  redox_tutor: { label: '氧化还原辅导', icon: <BookOpen size={14} /> },
  equilibrium_tutor: { label: '化学平衡辅导', icon: <BookOpen size={14} /> },
  periodic_law_tutor: { label: '元素周期律辅导', icon: <BookOpen size={14} /> },
  organic_tutor: { label: '有机化学辅导', icon: <BookOpen size={14} /> },
  /* OCR / 批改 */
  query_ocr_progress: { label: '查询识别进度', icon: <Activity size={14} /> },
  grade_answer_sheets: { label: '批改答题卡', icon: <ClipboardList size={14} /> },
  save_grading_results: { label: '保存批改结果', icon: <FileText size={14} /> },
  query_batch_grades: { label: '查询批次成绩', icon: <ListTree size={14} /> },
  list_teacher_exams: { label: '我的考试列表', icon: <ListTree size={14} /> },
  /* 文档解析 */
  parse_chemistry_document: { label: '解析化学文档', icon: <FileText size={14} /> },
  import_question_bank: { label: '导入题库', icon: <Upload size={14} /> },
  check_parser_services: { label: '检查解析服务', icon: <ShieldCheck size={14} /> },

  /* 浏览器工具（2026-08 补齐：避免裸英文名回退） */
  browse_navigate: { label: '网页导航', icon: <Globe size={14} /> },
  browse_read: { label: '读取网页', icon: <FileText size={14} /> },
  browse_click: { label: '点击页面元素', icon: <MousePointerClick size={14} /> },
  browse_input: { label: '页面输入文本', icon: <Keyboard size={14} /> },
  browse_screenshot: { label: '页面截图', icon: <Camera size={14} /> },
}

export function toolLabel(tool: string): string {
  return TOOL_META[tool]?.label ?? tool
}

export function toolIcon(tool: string): ReactNode {
  return TOOL_META[tool]?.icon ?? <Wrench size={14} />
}

export interface ToolCardData {
  tool: string
  status: ToolStatus
  data?: unknown
  error?: string
}

/** 工具调用内联卡片：图标 + 名称 + 状态 + 结果（完成/失败自动展开，与旧版即时可见一致） */
export function ToolCard({ card }: { card: ToolCardData }) {
  const [open, setOpen] = useState(false)
  const paused = card.status === 'paused'
  const hasResult = (card.status === 'done' || card.status === 'error' || paused) && card.data !== undefined

  useEffect(() => {
    // 结果到达自动展开（旧版行为：工具结果直接可见；2026-08：失败结果同样可见）
    if ((card.status === 'done' || card.status === 'error' || paused) && card.data !== undefined) setOpen(true)
  }, [card.status, card.data])

  return (
    <div
      className={`shrink-0 self-start max-w-[92%] bg-surface border rounded-[var(--radius-md)] shadow-[var(--shadow-sm)] overflow-hidden animate-fade-in-up ${
        card.status === 'error'
          ? 'border-error/40'
          : card.status === 'running' || paused
            ? 'border-teal/30'
            : 'border-border'
      }`}
    >
      <button
        className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-left hover:bg-surface-muted/60 transition-colors cursor-pointer"
        onClick={() => setOpen((v) => !v)}
      >
        <span
          className={`w-7 h-7 rounded-[var(--radius-sm)] flex items-center justify-center shrink-0 ${
            card.status === 'error' ? 'bg-error-soft text-error' : 'bg-teal-soft text-teal'
          }`}
        >
          {toolIcon(card.tool)}
        </span>
        <span className="flex-1 text-[13px] font-medium text-ink">{toolLabel(card.tool)}</span>
        {card.status === 'running' ? (
          <Badge status="running" label="执行中" />
        ) : paused ? (
          <Badge status="running" label="等待确认" />
        ) : card.status === 'error' ? (
          <Badge status="blocked" label="失败" />
        ) : (
          <Badge status="pass" label="完成" />
        )}
        {hasResult && (open ? <ChevronDown size={14} className="text-ink-muted" /> : <ChevronRight size={14} className="text-ink-muted" />)}
      </button>
      {hasResult && open && (
        <div className="px-3.5 pb-3.5 pt-1 border-t border-border/60">
          <ToolResultView tool={card.tool} data={card.data} />
        </div>
      )}
      {card.status === 'error' && card.error && (
        <div className="px-3.5 pb-3 text-xs text-error">{card.error}</div>
      )}
    </div>
  )
}
