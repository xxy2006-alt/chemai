import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Sparkles,
  Search,
  FolderOpen,
  Upload,
  Trash2,
  Save,
  Eye,
  Send,
  Plus,
  Check,
  X,
  Pencil,
  Loader2,
  Printer,
} from 'lucide-react'
import { App as AntApp, Checkbox, Input as AntInput, InputNumber, Modal as AntModal, Segmented, Select as AntSelect, Tabs as AntTabs, Tag as AntdTag, Upload as AntUpload } from 'antd'
import { api } from '../../lib/api'
import { renderChemMD } from '../../lib/chem-markdown'
import { EXAM_TYPE_CHIPS, EXAM_TYPE_LABELS } from '../../lib/exam-types'
import { shouldShowThumbnail } from '../../lib/exam-utils'
import { useLiveTimer } from '../../lib/use-live-timer'
import { Badge, Button, Card, EmptyState, Input, Modal, Select, Tag, useToast } from '../../components/ui'
import { QuestionMd } from '../../components/QuestionMd'
import { AnswerMd } from '../../components/AnswerMd'
import { OptionsRow } from '../../components/OptionsRow'
import { VariantBrowserModal } from '../../components/chat/VariantBrowserModal'

/* ── 类型 ── */

interface KnowledgePoint {
  name: string
  active: boolean
}

interface QuestionTypeChip {
  val: string
  label: string
  active: boolean
  qty: number
}

interface GeneratedQuestion {
  content?: string
  options?: string[] | string
  answer?: string
  analysis?: string
  knowledge_points?: string[]
  difficulty?: string
  overall_status?: 'passed' | 'warning' | 'blocked' | string
  audits?: Record<string, unknown>
  _typeLabel?: string
  _saved?: boolean
  _removed?: boolean
  _editing?: boolean
  /** 已保存到题库后才有（组卷打印/加入考试用） */
  question_id?: string
  id?: string
}

interface ExamSet {
  set_id: string
  name?: string
  question_count?: number
}

interface Paper {
  name?: string
  source_key?: string
  year?: string
  question_count?: number
}

interface PaperGroup {
  region?: string
  years?: { year?: string; papers?: Paper[] }[]
}

interface BankQuestion {
  question_id?: string
  id?: string
  exam_id?: string
  question_number?: string
  source?: string
  region?: string
  year?: string
  page_image?: string
  content?: string
  options?: string[] | string
  answer?: string
  analysis?: string
  knowledge_points?: string[]
  difficulty?: string
}

interface ExamItem {
  record_id: string
  name?: string
  class_id?: string
  exam_date?: string
  total_students?: number
  question_stats?: { question_count?: number }
}

const TYPE_LABELS = EXAM_TYPE_LABELS

/** 出题工作台 · Phase 2 迁移（原 pages/exam-v2.html，Vue 单页） */
export function ExamPage() {
  const toast = useToast()
  const { modal } = AntApp.useApp()
  const [tab, setTab] = useState('workbench')
  const [sourceMode, setSourceMode] = useState<'ai' | 'manual' | 'upload'>('ai')

  /* ── 公共数据 ── */
  const [kps, setKps] = useState<KnowledgePoint[]>([])
  const [kpSearch, setKpSearch] = useState('')
  const [folders, setFolders] = useState<ExamSet[]>([])
  const [selectedFolder, setSelectedFolder] = useState<string | undefined>(undefined)

  /* ── AI 生成 ── */
  const [types, setTypes] = useState<QuestionTypeChip[]>(EXAM_TYPE_CHIPS.map((t) => ({ ...t })))
  const [difficulty, setDifficulty] = useState('medium')
  const [generating, setGenerating] = useState(false)
  // 旧版行为恢复：AI 生成计时器（⚡ AI 出题 + live-timer，主工作台）
  const genSec = useLiveTimer(generating)
  const [questions, setQuestions] = useState<GeneratedQuestion[]>([])
  const [useVariant, setUseVariant] = useState(false)
  const [variantLabel, setVariantLabel] = useState('')
  const [variantQid, setVariantQid] = useState('')
  const [savingAll, setSavingAll] = useState(false)
  const [variantOpen, setVariantOpen] = useState(false)

  /* ── 手动录入 ── */
  const [mq, setMq] = useState({ content: '', options: '', answer: '', kps: '', diff: 'medium' })

  /* ── OCR 上传 ── */
  const [ocrLoading, setOcrLoading] = useState(false)
  const [ocrText, setOcrText] = useState('')

  /* ── 题库管理 ── */
  const [bankFolder, setBankFolder] = useState('')
  const [bankQuestions, setBankQuestions] = useState<BankQuestion[]>([])
  /* 题库多选（批量加入考试） */
  const [selectedBankIds, setSelectedBankIds] = useState<string[]>([])

  /* ── 题库加入考试弹窗 ── */
  const [addToExamOpen, setAddToExamOpen] = useState(false)
  const [addToExamId, setAddToExamId] = useState('')
  const [addToExamBusy, setAddToExamBusy] = useState(false)

  /* ── 历史真题库 ── */
  const [histGroups, setHistGroups] = useState<PaperGroup[]>([])

  /* ── 考试列表 ── */
  const [examName, setExamName] = useState('')
  const [examClass, setExamClass] = useState('')
  const [examList, setExamList] = useState<ExamItem[]>([])
  const [classes, setClasses] = useState<{ class_id?: string; name?: string }[]>([])
  const [previewExam, setPreviewExam] = useState<ExamItem | null>(null)
  const [previewQuestions, setPreviewQuestions] = useState<BankQuestion[]>([])
  /* 打印版本：学生版(无答案) / 教师版(含答案+解析) */
  const [printWithAnswers, setPrintWithAnswers] = useState(false)

  /* ── 加载 ── */
  const loadKps = useCallback(async () => {
    try {
      const d = await api.get<{ knowledge_points?: { name?: string }[]; data?: { name?: string }[] }>('/api/knowledge/list')
      const items = d.knowledge_points || d.data || []
      setKps(items.map((k) => ({ name: k.name || String(k), active: false })))
    } catch {
      /* ignore */
    }
  }, [])

  const loadFolders = useCallback(async () => {
    try {
      const d = await api.get<{ data?: { exam_sets?: ExamSet[] } }>('/api/exam-bank/exam-sets')
      const list = d.data?.exam_sets || []
      setFolders(list)
      if (list.length && !selectedFolder) setSelectedFolder(list[0].set_id)
    } catch {
      /* ignore */
    }
  }, [selectedFolder])

  const loadHistory = useCallback(async () => {
    try {
      const d = await api.get<{ success?: boolean; data?: { groups?: PaperGroup[]; total_papers?: number } }>(
        '/api/exam-bank/papers',
      )
      setHistGroups(d.data?.groups || [])
    } catch {
      /* ignore */
    }
  }, [])

  const loadExams = useCallback(async () => {
    try {
      const c = await api.get<{ classes?: { class_id?: string; name?: string }[] }>('/api/classes')
      const clist = c.classes || []
      setClasses(clist)
      const all: ExamItem[] = []
      await Promise.all(
        clist.map(async (cls) => {
          try {
            const r = await api.get<{ success?: boolean; exams?: ExamItem[] }>(`/api/exam/list/${cls.class_id}`)
            ;(r.exams || []).forEach((e) => all.push(e))
          } catch {
            /* ignore */
          }
        }),
      )
      setExamList(all)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    loadKps()
    loadFolders()
    loadHistory()
    loadExams()
  }, [loadKps, loadFolders, loadHistory, loadExams])

  const filteredKps = useMemo(() => {
    const s = kpSearch.toLowerCase()
    return kps.filter((k) => !s || k.name.toLowerCase().includes(s))
  }, [kps, kpSearch])

  /* ── AI 生成 ── */
  async function aiGenerate() {
    if (useVariant && variantQid) {
      setGenerating(true)
      setQuestions([])
      try {
        const d = await api.post<{ questions?: GeneratedQuestion[] }>('/api/question/generate', {
          knowledge_points: [],
          difficulty,
          quantity: 3,
          question_types: ['choice'],
          variant_source_id: variantQid,
        })
        setQuestions(
          (d.questions || []).map((q) => ({ ...q, _typeLabel: '变种题', _source: '(变种)', _saved: false, _removed: false })),
        )
        toast.success(`已生成 ${(d.questions || []).length} 道变种题`)
      } catch {
        toast.error('生成失败')
      } finally {
        setGenerating(false)
      }
      return
    }
    const kpNames = kps.filter((k) => k.active).map((k) => k.name)
    const activeTypes = types.filter((t) => t.active)
    if (!kpNames.length) {
      toast.warning('请选择至少一个知识点')
      return
    }
    if (!activeTypes.length) {
      toast.warning('请选择至少一种题型')
      return
    }
    setGenerating(true)
    setQuestions([])
    const allQs: GeneratedQuestion[] = []
    let pending = activeTypes.length
    for (const t of activeTypes) {
      try {
        const d = await api.post<{ questions?: GeneratedQuestion[] }>('/api/question/generate', {
          knowledge_points: kpNames,
          difficulty,
          quantity: t.qty || 2,
          question_types: [t.val],
        })
        allQs.push(
          ...(d.questions || []).map((q) => ({
            ...q,
            _typeLabel: TYPE_LABELS[t.val] || t.val,
            _saved: false,
            _removed: false,
          })),
        )
      } catch {
        /* 单类型失败继续 */
      } finally {
        pending--
        if (!pending) {
          setQuestions(allQs)
          setGenerating(false)
          toast.success(`已生成 ${allQs.length} 题`)
        }
      }
    }
  }

  async function saveOne(i: number) {
    const q = questions[i]
    if (!q || q._removed || q._saved) return
    if (!selectedFolder) {
      toast.warning('请先选择保存目标题库')
      return
    }
    try {
      const d = await api.post<{ success?: boolean; message?: string }>('/api/exam-bank/import-questions', {
        set_id: selectedFolder,
        questions: [
          {
            content: q.content,
            options: Array.isArray(q.options) ? q.options : typeof q.options === 'string' ? q.options.split(',').filter(Boolean) : [],
            answer: q.answer || '',
            analysis: q.analysis || '',
            knowledge_points: q.knowledge_points || [],
            difficulty: q.difficulty || 'medium',
          },
        ],
      })
      if (d.success !== false) {
        setQuestions((prev) => prev.map((x, idx) => (idx === i ? { ...x, _saved: true, _removed: true } : x)))
        toast.success('已保存到题库')
      } else {
        toast.error(d.message || '保存失败')
      }
    } catch {
      toast.error('网络错误')
    }
  }

  async function saveAll() {
    const active = questions.filter((q) => !q._removed && !q._saved)
    if (!active.length) return
    if (!selectedFolder) {
      toast.warning('请先选择保存目标题库')
      return
    }    setSavingAll(true)
    let ok = 0
    for (const q of active) {
      try {
        await api.post('/api/exam-bank/import-questions', {
          set_id: selectedFolder,
          questions: [
            {
              content: q.content,
              options: Array.isArray(q.options) ? q.options : typeof q.options === 'string' ? q.options.split(',').filter(Boolean) : [],
              answer: q.answer || '',
              analysis: q.analysis || '',
              knowledge_points: q.knowledge_points || [],
              difficulty: q.difficulty || 'medium',
            },
          ],
        })
        ok++
      } catch {
        /* 继续 */
      }
    }
    setQuestions((prev) => prev.map((q) => (q._removed || q._saved ? q : { ...q, _saved: true, _removed: true })))
    setSavingAll(false)
    toast.success(`已保存 ${ok}/${active.length} 题到题库`)
  }

  /* ── 新建题库（旧版 + 新建 行为） ── */
  async function createFolder() {
    const name = window.prompt('新题库名称：', '')
    if (!name || !name.trim()) return
    try {
      const d = await api.post<{ success?: boolean; set_id?: string; message?: string }>('/api/exam-bank/exam-sets', {
        name: name.trim(),
      })
      if (d.success !== false) {
        toast.success(`已创建题库「${name.trim()}」`)
        loadFolders()
      } else {
        toast.error(d.message || '创建失败')
      }
    } catch (e) {
      toast.error(`创建失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  /* ── 试卷打印（考试列表「预览」入口；出题工作台不做打印 ——
   * 2026-08 用户确认：打印属于试卷（考试）的事，出题区不留打印按钮） ── */
  function printPaper(title: string, items: GeneratedQuestion[], withAnswers: boolean) {
    const w = window.open('', '_blank')
    if (!w) {
      toast.error('请允许浏览器弹出窗口以打印预览')
      return
    }
    const d = new Date()
    const dateStr = `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
    const versionLabel = withAnswers ? '教师版（含答案与解析）' : '学生版'
    const answerKeyHtml = withAnswers
      ? `<div class="answer-key"><div class="answer-key-title">参考答案与解析</div>` +
        items
          .map((q, i) => {
            const ans = q.answer ? renderChemMD(String(q.answer)) : '（无）'
            const ana = q.analysis
              ? `<div class="ak-analysis">解析：${renderChemMD(String(q.analysis))}</div>`
              : ''
            return `<div class="ak"><div class="ak-no">${i + 1}. 答案：${ans}</div>${ana}</div>`
          })
          .join('') +
        `</div>`
      : ''
    const html = `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>${title}</title>
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
      <style>
        /* token-lint:disable-frame — 试卷打印纸张样式（黑白印刷域，不走 UI token） */
        body{font-family:"Noto Serif SC","SimSun","PingFang SC","Microsoft YaHei",serif;color:#000;margin:0;padding:32px;line-height:1.7}
        .paper-title{text-align:center;font-size:22px;font-weight:700;margin-bottom:4px}
        .paper-sub{text-align:center;color:#555;font-size:13px;margin-bottom:20px;padding-bottom:10px;border-bottom:2px solid #000}
        .q{margin-bottom:18px;page-break-inside:avoid}
        .qno{font-weight:600;margin-bottom:4px}
        .qbody{font-size:15px}
        .qopts{font-size:14px;margin-top:4px}
        .qopts span{margin-right:16px}
        img{max-width:100%}
        table{border-collapse:collapse;margin:8px 0}table th,table td{border:1px solid #000;padding:4px 8px}
        .answer-key{page-break-before:always;margin-top:24px}
        .answer-key-title{text-align:center;font-size:18px;font-weight:700;margin-bottom:14px}
        .ak{margin-bottom:10px;page-break-inside:avoid}
        .ak-no{font-weight:600}
        .ak-answer{margin-top:2px}
        .ak-analysis{margin-top:2px;color:#333}
        @media print{body{padding:16px}.no-print{display:none}}
        /* token-lint:enable-frame */
      </style></head><body>
      <div class="paper-title">${title}</div>
      <div class="paper-sub">${dateStr} · 共 ${items.length} 题 · ${versionLabel}</div>
      ${items
        .map(
          (q, i) => `<div class="q"><div class="qno">${i + 1}. ${q._typeLabel || '题目'}</div>
          <div class="qbody">${renderChemMD(String(q.content || ''))}</div>
          ${
            Array.isArray(q.options) && q.options.length
              ? `<div class="qopts">${q.options.map((o) => `<span>${o}</span>`).join('')}</div>`
              : ''
          }</div>`,
        )
        .join('')}
      ${answerKeyHtml}
      <button class="no-print" onclick="window.print()" style="position:fixed;right:20px;top:20px;padding:8px 20px;cursor:pointer">打印</button>
      </body></html>`
    w.document.write(html)
    w.document.close()
  }

  /* ── 手动录入 ── */
  async function saveManual() {
    if (!mq.content.trim()) {
      toast.warning('请输入题目内容')
      return
    }
    if (!selectedFolder) {
      toast.warning('请先选择保存目标题库')
      return
    }
    try {
      const d = await api.post<{ success?: boolean; message?: string }>('/api/exam-bank/import-questions', {
        set_id: selectedFolder,
        questions: [
          {
            content: mq.content.trim(),
            options: mq.options.split(/[,，、]/).filter(Boolean),
            answer: mq.answer.trim(),
            analysis: '',
            knowledge_points: mq.kps.split(/[,，、]/).filter(Boolean),
            difficulty: mq.diff,
          },
        ],
      })
      if (d.success !== false) {
        toast.success('已录入题库')
        setMq({ content: '', options: '', answer: '', kps: '', diff: 'medium' })
      } else {
        toast.error(d.message || '录入失败')
      }
    } catch {
      toast.error('网络错误')
    }
  }

  /* ── OCR 上传 ── */
  async function handleOcrFile(file: File) {
    if (file.size > 10 * 1024 * 1024) {
      toast.warning('文件不能超过 10MB')
      return
    }
    setOcrLoading(true)
    try {
      const b64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result).split(',')[1] || '')
        reader.onerror = reject
        reader.readAsDataURL(file)
      })
      const d = await api.post<{ success?: boolean; text?: string; questions?: unknown[]; content?: string }>(
        '/api/ocr/parse/document',
        { file_data: b64, file_type: 'auto', source: 'auto' },
      )
      const text = d.text || d.content || ''
      setOcrText(text ? `【${file.name}】\n${text.slice(0, 4000)}` : '解析完成，未提取到文本')
      toast.success('解析完成')
    } catch (e) {
      toast.error(`解析失败: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setOcrLoading(false)
    }
  }

  /* ── 题库管理 ── */
  async function loadBankQuestions(setId: string) {
    setBankFolder(setId)
    try {
      const d = await api.get<{ data?: { questions?: BankQuestion[] }; questions?: BankQuestion[] }>(
        `/api/exam-bank/exam-sets/${setId}`,
      )
      setBankQuestions(d.data?.questions || d.questions || [])
    } catch {
      setBankQuestions([])
    }
  }

  async function deleteSet(setId: string) {
    const name = folders.find((f) => f.set_id === setId)?.name || '该题库'
    modal.confirm({
      title: '删除题库',
      content: `确定删除「${name}」？题目关联将被移除（题目本身保留）。`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.del(`/api/exam-bank/exam-sets/${setId}`)
          toast.success('已删除题库')
          setBankQuestions([])
          setBankFolder('')
          loadFolders()
        } catch (e) {
          toast.error(`删除失败: ${e instanceof Error ? e.message : ''}`)
        }
      },
    })
  }

  /* ── 题库单题删除（旧版功能恢复：原来只有整个题库删除） ── */
  async function deleteBankQuestion(qid: string) {
    if (!bankFolder) return
    modal.confirm({
      title: '删除题目',
      content: '确定从该题库中删除这道题？',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.del(`/api/exam-bank/exam-sets/${bankFolder}/questions/${qid}`)
          toast.success('已删除题目')
          setSelectedBankIds((prev) => prev.filter((x) => x !== qid))
          loadBankQuestions(bankFolder)
        } catch (e) {
          toast.error(`删除失败: ${e instanceof Error ? e.message : ''}`)
        }
      },
    })
  }

  /* ── 题库题目加入考试（旧版功能恢复：选题组卷 + 批量加入） ── */
  async function confirmAddToExam() {
    if (!addToExamId) {
      toast.warning('请选择目标考试')
      return
    }
    if (!selectedBankIds.length) {
      toast.warning('请先勾选题目')
      return
    }
    setAddToExamBusy(true)
    try {
      const d = await api.post<{ success?: boolean; updated?: number; message?: string }>(
        `/api/exam/${addToExamId}/questions`,
        { question_ids: selectedBankIds },
      )
      if (d.success !== false) {
        toast.success(`已加入 ${d.updated ?? selectedBankIds.length} 道题到考试`)
        setSelectedBankIds([])
        setAddToExamOpen(false)
        loadExams()
      } else {
        toast.error(d.message || '加入失败')
      }
    } catch (e) {
      toast.error(`加入失败: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setAddToExamBusy(false)
    }
  }

  /* ── 历史真题库 ── */
  const [histModal, setHistModal] = useState<{ title: string; questions: BankQuestion[]; loading: boolean } | null>(null)

  /** 点击试卷 → 弹窗展示该卷题目（旧版 openVariantPaper 行为） */
  async function openPaper(p: Paper, region: string) {
    const title = `${region} · ${p.year || ''} · ${p.name || '试卷'}`
    setHistModal({ title, questions: [], loading: true })
    try {
      const params = `region=${encodeURIComponent(p.source_key || p.name || region)}&year=${encodeURIComponent(p.year || '')}&page_size=200`
      const d = await api.get<{ data?: { questions?: BankQuestion[] } }>(`/api/exam-bank/historical?${params}`)
      setHistModal({ title, questions: d.data?.questions || [], loading: false })
    } catch {
      setHistModal({ title, questions: [], loading: false })
    }
  }

  function useAsVariant(q: BankQuestion) {
    setVariantQid(q.exam_id || q.question_id || '')
    setVariantLabel(`${q.source || ''} · #${q.question_number || ''}`)
    setUseVariant(true)
    setTab('workbench')
    toast.success(`已设置蓝本: ${variantLabel || '真题'}`)
  }

  /* ── 考试 ── */
  async function createExam() {
    if (!examName.trim() || !examClass) {
      toast.warning('请填写名称和班级')
      return
    }
    try {
      const d = await api.post<{ success?: boolean; record_id?: string; name?: string; exam_date?: string; total_students?: number }>(
        '/api/exam/create',
        { name: examName.trim(), class_id: examClass },
      )
      if (d.success !== false) {
        setExamList((prev) => [
          { record_id: d.record_id!, name: d.name || examName, exam_date: d.exam_date, total_students: d.total_students },
          ...prev,
        ])
        setExamName('')
        toast.success(`考试「${d.name || examName}」已创建`)
      } else {
        toast.error('创建失败')
      }
    } catch (e) {
      toast.error(`创建失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  async function openPreview(e: ExamItem) {
    setPreviewExam(e)
    setPreviewQuestions([])
    try {
      const d = await api.get<{ questions?: BankQuestion[] }>(`/api/exam/${e.record_id}/questions`)
      setPreviewQuestions(d.questions || [])
    } catch {
      setPreviewQuestions([])
    }
  }

  async function publishExam(e: ExamItem) {
    try {
      const d = await api.post<{ success?: boolean; message?: string }>(`/api/exam/${e.record_id}/publish`)
      if (d.success !== false) toast.success('已发布')
      else toast.error(d.message || '发布失败')
    } catch {
      toast.error('发布失败')
    }
  }

  async function deleteExam(e: ExamItem) {
    modal.confirm({
      title: '删除考试',
      content: `确定删除考试「${e.name}」？`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.del(`/api/exam/${e.record_id}`)
          setExamList((prev) => prev.filter((x) => x.record_id !== e.record_id))
          toast.success('已删除')
        } catch {
          toast.error('删除失败')
        }
      },
    })
  }

  /* ── 渲染 ── */
  return (
    <div className="animate-fade-in-up">
      <div className="mb-5">
        <h1 className="text-[22px] font-semibold text-ink m-0">出题工作台</h1>
        <p className="mt-1 text-sm text-ink-secondary">AI 生成 · 手动录入 · OCR 导入 · 题库与试卷管理</p>
      </div>

      <AntTabs
        className="mb-5"
        items={[
          { key: 'workbench', label: '出题工作台' },
          { key: 'bank', label: '题库管理' },
          { key: 'history', label: '历史真题库' },
          { key: 'exams', label: '考试列表' },
        ]}
        activeKey={tab}
        onChange={setTab}
      />

      {/* ═══ 出题工作台 ═══ */}
      {tab === 'workbench' && (
        <div className="grid grid-cols-1 xl:grid-cols-[280px_1fr] gap-4">
          {/* 左侧：保存目标 + 知识点 */}
          <div className="space-y-4">
            <Card title="保存目标题库">
              <AntSelect
                value={selectedFolder}
                onChange={setSelectedFolder}
                placeholder="选择题库…"
                className="w-full"
                options={folders.map((f) => ({
                  value: f.set_id,
                  label: `${f.name}（${f.question_count || 0} 题）`,
                }))}
              />
              <Button size="sm" variant="secondary" className="w-full justify-center mt-2" onClick={createFolder}>
                <Plus size={13} />
                新建题库
              </Button>
              {folders.length === 0 && (
                <p className="text-xs text-ink-muted mt-2">暂无题库，点击上方新建</p>
              )}
            </Card>
            <Card title="知识点选择">
              <AntInput
                value={kpSearch}
                onChange={(e) => setKpSearch(e.target.value)}
                placeholder="搜索知识点…"
                allowClear
                prefix={<Search size={13} className="text-ink-muted" />}
                className="mb-2.5"
              />
              <div className="max-h-[300px] overflow-y-auto space-y-0.5">
                {filteredKps.length === 0 && <p className="text-xs text-ink-muted py-2">暂无知识点</p>}
                {filteredKps.map((k) => (
                  <button
                    key={k.name}
                    onClick={() =>
                      setKps((prev) => prev.map((x) => (x.name === k.name ? { ...x, active: !x.active } : x)))
                    }
                    className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-[var(--radius-sm)] text-[13px] transition-colors cursor-pointer text-left ${
                      k.active ? 'bg-primary-soft text-primary font-medium' : 'text-ink-secondary hover:bg-surface-muted'
                    }`}
                  >
                    <span
                      className={`w-3.5 h-3.5 rounded-[4px] border flex items-center justify-center shrink-0 ${
                        k.active ? 'bg-primary border-primary text-white' : 'border-border-strong'
                      }`}
                    >
                      {k.active && <Check size={10} />}
                    </span>
                    {k.name}
                  </button>
                ))}
              </div>
            </Card>
          </div>

          {/* 右侧：子标签页（antd Segmented，2026-08 第二轮） */}
          <div className="space-y-4">
            <Segmented
              block
              value={sourceMode}
              onChange={(k) => setSourceMode(k as 'ai' | 'manual' | 'upload')}
              options={[
                { value: 'ai', label: 'AI 生成' },
                { value: 'manual', label: '手动录入' },
                { value: 'upload', label: 'OCR 上传' },
              ]}
            />

            {sourceMode === 'ai' && (
              <>
                <Card>
                  <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                    <div className="text-[13px] font-medium text-ink-secondary">题型与数量（点击选中，可调数量）</div>
                    {useVariant && (
                      <Tag tone="teal" size="sm">
                        蓝本: {variantLabel || '已设置'}
                        <button className="ml-1.5 hover:text-teal-hover cursor-pointer" onClick={() => setUseVariant(false)}>
                          <X size={11} />
                        </button>
                      </Tag>
                    )}
                  </div>
                  <div className="flex gap-2 flex-wrap mb-4 items-center">
                    {types.map((t) => (
                      <AntdTag.CheckableTag
                        key={t.val}
                        checked={t.active}
                        onChange={() =>
                          setTypes((prev) => prev.map((x) => (x.val === t.val ? { ...x, active: !x.active } : x)))
                        }
                        className={`!rounded-[var(--radius-md)] !px-3 !py-1 !text-[13px] !border !border-solid transition-all ${
                          t.active
                            ? '!border-primary !bg-primary-soft !text-primary !font-medium'
                            : '!border-border !text-ink-secondary hover:!border-border-strong'
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          <span className="text-[10px]">{t.active ? '●' : '○'}</span>
                          {t.label}
                          {t.active && (
                            <InputNumber
                              size="small"
                              min={1}
                              max={10}
                              value={t.qty}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(v) =>
                                setTypes((prev) =>
                                  prev.map((x) =>
                                    x.val === t.val ? { ...x, qty: Math.max(1, Math.min(10, Number(v) || 1)) } : x,
                                  ),
                                )
                              }
                              className="!w-[64px] !text-[13px]"
                            />
                          )}
                        </span>
                      </AntdTag.CheckableTag>
                    ))}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="w-[140px]">
                      <AntSelect
                        value={difficulty}
                        onChange={setDifficulty}
                        className="w-full"
                        options={[
                          { value: 'easy', label: '容易' },
                          { value: 'medium', label: '中等' },
                          { value: 'hard', label: '困难' },
                        ]}
                      />
                    </div>
                    <Button variant="secondary" onClick={() => setVariantOpen(true)} title="基于高考真题生成变种题">
                      <Pencil size={14} />
                      {useVariant ? '更换蓝本' : '选真题作蓝本'}
                    </Button>
                    <Button variant="ai" onClick={aiGenerate} loading={generating}>
                      <Sparkles size={14} />
                      AI 生成题目
                    </Button>
                    {generating && (
                      <span className="flex items-center gap-1.5 text-[13px] text-teal">
                        ⚡ AI 出题
                        <span className="live-timer ticking text-ink-muted chem-mono">{genSec.toFixed(1)}s</span>
                      </span>
                    )}
                    {questions.filter((q) => !q._removed && !q._saved).length > 0 && (
                      <Button onClick={saveAll} loading={savingAll}>
                        <Save size={14} />
                        全部保存到题库
                      </Button>
                    )}
                  </div>
                </Card>

                {/* 生成结果 */}
                {questions.length > 0 && (
                  <div className="space-y-3">
                    {questions.map((q, i) => {
                      if (q._removed) return null
                      const status = q.overall_status || 'passed'
                      return (
                        <Card key={i} padding="p-4">
                          <div className="flex items-center gap-2 mb-2 flex-wrap">
                            <Tag tone="blue" size="sm">
                              {q._typeLabel || '题目'} #{i + 1}
                            </Tag>
                            {status === 'passed' ? (
                              <Badge status="pass" label="四维审核通过" />
                            ) : status === 'warning' ? (
                              <Badge status="warning" label="需人工确认" />
                            ) : (
                              <Badge status="blocked" label="审核拦截" />
                            )}
                            {q.difficulty && (
                              <Tag tone={q.difficulty === 'hard' ? 'red' : q.difficulty === 'easy' ? 'teal' : 'blue'} size="sm">
                                {q.difficulty}
                              </Tag>
                            )}
                          </div>
                          <QuestionMd text={q.content || ''} />
                          <OptionsRow options={q.options} className="mt-2" />
                          <div className="mt-2.5 flex items-center gap-2 flex-wrap">
                            <AnswerMd text={q.answer || ''} />
                            {(q.knowledge_points || []).map((k) => (
                              <Tag key={k} tone="gray" size="sm">
                                {k}
                              </Tag>
                            ))}
                            <div className="ml-auto flex gap-2">
                              {q._saved ? (
                                <span className="text-xs text-success flex items-center gap-1">
                                  <Check size={13} /> 已保存
                                </span>
                              ) : (
                                <>
                                  <Button size="sm" variant="secondary" onClick={() => saveOne(i)}>
                                    <Save size={13} />
                                    保存
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setQuestions((prev) => prev.map((x, idx) => (idx === i ? { ...x, _removed: true } : x)))}
                                  >
                                    <Trash2 size={13} />
                                  </Button>
                                </>
                              )}
                            </div>
                          </div>
                        </Card>
                      )
                    })}
                  </div>
                )}
              </>
            )}

            {sourceMode === 'manual' && (
              <Card title="手动录入题目">
                <div className="space-y-4">
                  <div>
                    <div className="text-[13px] font-medium text-ink-secondary mb-1.5">题目内容</div>
                    <AntInput.TextArea
                      value={mq.content}
                      onChange={(e) => setMq((p) => ({ ...p, content: e.target.value }))}
                      rows={3}
                      placeholder="输入题目内容…"
                    />
                  </div>
                  <div>
                    <div className="text-[13px] font-medium text-ink-secondary mb-1.5">选项（逗号分隔，可选）</div>
                    <AntInput value={mq.options} onChange={(e) => setMq((p) => ({ ...p, options: e.target.value }))} placeholder="A. xxx, B. xxx, C. xxx, D. xxx" />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <div className="text-[13px] font-medium text-ink-secondary mb-1.5">答案</div>
                      <AntInput value={mq.answer} onChange={(e) => setMq((p) => ({ ...p, answer: e.target.value }))} placeholder="答案" />
                    </div>
                    <div>
                      <div className="text-[13px] font-medium text-ink-secondary mb-1.5">知识点（逗号分隔）</div>
                      <AntInput value={mq.kps} onChange={(e) => setMq((p) => ({ ...p, kps: e.target.value }))} placeholder="盐类水解, 电离平衡" />
                    </div>
                    <div>
                      <div className="text-[13px] font-medium text-ink-secondary mb-1.5">难度</div>
                      <AntSelect
                        value={mq.diff}
                        onChange={(v) => setMq((p) => ({ ...p, diff: v }))}
                        className="w-full"
                        options={[
                          { value: 'easy', label: '容易' },
                          { value: 'medium', label: '中等' },
                          { value: 'hard', label: '困难' },
                        ]}
                      />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <Button onClick={saveManual}>
                      <Save size={14} />
                      录入题库
                    </Button>
                  </div>
                </div>
              </Card>
            )}

            {sourceMode === 'upload' && (
              <Card title="OCR 上传导入">
                <AntUpload.Dragger
                  accept="image/*,.pdf"
                  maxCount={1}
                  beforeUpload={(file) => {
                    handleOcrFile(file as File)
                    return false
                  }}
                  showUploadList={false}
                >
                  <p className="text-teal mb-2 flex justify-center">
                    <Upload size={28} />
                  </p>
                  <p className="text-sm font-medium text-ink">点击或拖拽试卷图片 / PDF 到此处</p>
                  <p className="text-xs text-ink-muted mt-1">解析后的文本将展示在下方，可复制整理后手动录入</p>
                </AntUpload.Dragger>
                {ocrLoading && (
                  <div className="flex items-center gap-2 mt-4 text-sm text-ink-secondary">
                    <Loader2 size={15} className="animate-spin text-teal" />
                    正在解析文档…
                  </div>
                )}
                {ocrText && (
                  <div className="mt-4">
                    <div className="text-[13px] font-medium text-ink-secondary mb-1.5">解析结果</div>
                    <pre className="whitespace-pre-wrap text-[13px] text-ink-secondary bg-surface-muted/60 rounded-[var(--radius-md)] p-3.5 max-h-[300px] overflow-y-auto m-0">
                      {ocrText}
                    </pre>
                    <p className="text-xs text-ink-muted mt-2">
                      解析结果可直接复制，或到「手动录入」中整理入库（保存前请选择左侧目标题库）
                    </p>
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>
      )}

      {/* ═══ 题库管理 ═══ */}
      {tab === 'bank' && (
        <div className="grid grid-cols-1 xl:grid-cols-[280px_1fr] gap-4">
          <Card title="题库列表" flush>
            <div className="p-2">
              {folders.length === 0 ? (
                <p className="text-xs text-ink-muted text-center py-6">暂无题库</p>
              ) : (
                folders.map((f) => (
                  <button
                    key={f.set_id}
                    onClick={() => loadBankQuestions(f.set_id)}
                    className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-[var(--radius-md)] text-[13px] transition-colors cursor-pointer text-left group ${
                      bankFolder === f.set_id ? 'bg-primary-soft text-primary font-medium' : 'text-ink-secondary hover:bg-surface-muted'
                    }`}
                  >
                    <FolderOpen size={14} className="shrink-0" />
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="text-[11px] text-ink-muted">{f.question_count || 0} 题</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteSet(f.set_id)
                      }}
                      className="opacity-0 group-hover:opacity-100 text-ink-muted hover:text-error transition-all cursor-pointer"
                    >
                      <Trash2 size={13} />
                    </button>
                  </button>
                ))
              )}
            </div>
          </Card>
          <Card title={bankFolder ? (folders.find((f) => f.set_id === bankFolder)?.name || '题库') : '题库题目'} flush>
            {bankQuestions.length === 0 ? (
              <EmptyState
                title="暂无题目"
                description="在「出题工作台」生成题目并保存后，题目会出现在这里"
                action={
                  <Button size="sm" onClick={() => setTab('workbench')}>
                    <Sparkles size={13} />
                    去出题
                  </Button>
                }
              />
            ) : (
              <div>
                {/* 批量操作栏：勾选题目 → 加入考试 */}
                <div className="flex items-center gap-3 px-5 py-2.5 border-b border-border bg-surface-muted/40 flex-wrap">
                  <Checkbox
                    checked={bankQuestions.length > 0 && selectedBankIds.length === bankQuestions.length}
                    indeterminate={selectedBankIds.length > 0 && selectedBankIds.length < bankQuestions.length}
                    onChange={(e) =>
                      setSelectedBankIds(
                        e.target.checked ? bankQuestions.map((q) => String(q.question_id || q.id || '')) : [],
                      )
                    }
                  >
                    全选
                  </Checkbox>
                  <span className="text-xs text-ink-secondary">已选 {selectedBankIds.length} 题</span>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!selectedBankIds.length}
                    onClick={() => {
                      setAddToExamOpen(true)
                    }}
                  >
                    <Send size={13} />
                    加入考试
                  </Button>
                  <span className="ml-auto text-[11px] text-ink-muted">勾选后可批量加入考试，生成试卷</span>
                </div>
                {bankQuestions.map((q, i) => {
                  const qid = String(q.question_id || q.id || '')
                  const checked = selectedBankIds.includes(qid)
                  return (
                    <div key={qid || i} className="px-5 py-3.5 border-b border-border last:border-b-0">
                      <div className="flex items-start gap-3">
                        <Checkbox
                          checked={checked}
                          onChange={() =>
                            setSelectedBankIds((prev) =>
                              checked ? prev.filter((x) => x !== qid) : [...prev, qid],
                            )
                          }
                          className="mt-1 shrink-0"
                        />
                        <div className="min-w-0 flex-1">
                          <QuestionMd text={q.content || ''} />
                          {q.analysis && <div className="text-xs text-ink-muted mt-1.5">解析: {q.analysis}</div>}
                          <div className="flex items-center gap-2 mt-2 flex-wrap">
                            <AnswerMd text={q.answer || ''} />
                            {(q.knowledge_points || []).map((k) => (
                              <Tag key={k} tone="gray" size="sm">
                                {k}
                              </Tag>
                            ))}
                            <div className="ml-auto flex items-center gap-1.5">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setSelectedBankIds([qid])
                                  setAddToExamOpen(true)
                                }}
                                title="将本题加入考试试卷"
                              >
                                <Send size={12} />
                                加入考试
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => deleteBankQuestion(qid)}
                                title="删除本题"
                                className="text-error hover:bg-error-soft"
                              >
                                <Trash2 size={12} />
                                删除
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ═══ 历史真题库 ═══ */}
      {tab === 'history' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {histGroups.map((g) => (
              <Card key={g.region} title={g.region || '地区'} hoverable>
                <div className="space-y-3">
                  {(g.years || []).map((y) => (
                    <div key={y.year}>
                      <div className="text-xs font-semibold text-ink-secondary mb-1">{y.year} 年</div>
                      <div className="space-y-1">
                        {(y.papers || []).map((p, pi) => (
                          <button
                            key={`${y.year}-${pi}`}
                            onClick={() => openPaper(p, g.region || '')}
                            className="w-full flex items-center justify-between px-3 py-2 rounded-[var(--radius-sm)] text-[13px] border border-border/60 hover:border-teal/40 hover:bg-teal-soft/30 transition-colors cursor-pointer"
                          >
                            <span className="font-medium text-ink truncate">{p.name}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* 历史真题 · 试卷题目弹窗（旧版 openVariantPaper 弹窗行为） */}
      <Modal
        open={histModal !== null}
        onClose={() => setHistModal(null)}
        title={histModal?.title || '试卷题目'}
        wide
        hideFooter
      >
        {histModal?.loading ? (
          <div className="flex items-center gap-2 py-8 justify-center text-ink-secondary">
            <Loader2 size={18} className="animate-spin text-teal" />
            加载题目中…
          </div>
        ) : histModal && histModal.questions.length === 0 ? (
          <EmptyState title="该试卷暂无题目" />
        ) : (
          <div className="space-y-3">
            <div className="text-xs text-ink-muted">{histModal?.questions.length} 道题目 · 点击「作蓝本」可生成变种题</div>
            {histModal?.questions.map((q, i) => (
              <div key={q.question_id || q.id || i} className="border border-border rounded-[var(--radius-md)] p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="w-5 h-5 rounded-full bg-primary-soft text-primary text-[11px] font-semibold flex items-center justify-center shrink-0">
                        {q.question_number || i + 1}
                      </span>
                      {(q.knowledge_points || []).slice(0, 2).map((k) => (
                        <Tag key={k} tone="gray" size="sm">
                          {k}
                        </Tag>
                      ))}
                    </div>
                    {q.page_image && shouldShowThumbnail(String(q.content || ''), q.page_image) ? (
                      <img
                        src={`/static/figures/${encodeURIComponent(q.region || '')}/${q.year || ''}/figures/${q.page_image}`}
                        alt="题目配图"
                        className="w-[90px] h-[60px] object-cover rounded-[var(--radius-sm)] border border-border float-left mr-3 mb-1.5"
                      />
                    ) : null}
                    <QuestionMd text={q.content || ''} />
                    <AnswerMd text={q.answer || ''} className="mt-2" />
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setSelectedBankIds([String(q.question_id || q.id || '')])
                        setAddToExamOpen(true)
                      }}
                      title="将本题加入考试试卷"
                    >
                      <Send size={12} />
                      加入考试
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => useAsVariant(q)}
                      title="以本题为蓝本生成变种题"
                    >
                      <Pencil size={12} />
                      作蓝本
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* ═══ 考试列表 ═══ */}
      {tab === 'exams' && (
        <div className="space-y-4">
          <Card title="创建考试">
            <div className="flex items-end gap-3 flex-wrap">
              <div className="w-[220px]">
                <div className="text-[13px] font-medium text-ink-secondary mb-1.5">考试名称</div>
                <Input value={examName} onChange={(e) => setExamName(e.target.value)} placeholder="如：5 月月考" />
              </div>
              <div className="w-[180px]">
                <div className="text-[13px] font-medium text-ink-secondary mb-1.5">班级</div>
                <Select value={examClass} onChange={(e) => setExamClass(e.target.value)}>
                  <option value="">选择班级…</option>
                  {classes.map((c) => (
                    <option key={c.class_id} value={c.class_id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              </div>
              <Button onClick={createExam}>
                <Plus size={14} />
                创建考试
              </Button>
            </div>
          </Card>

          {examList.length === 0 ? (
            <Card>
              <EmptyState title="暂无考试" description="创建考试后，可在题库或历史真题库中选题加入" />
            </Card>
          ) : (
            <div className="space-y-2.5">
              {examList.map((e) => (
                <Card key={e.record_id} padding="p-4" hoverable>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-[15px] font-medium text-ink">{e.name}</span>
                    <span className="text-xs text-ink-muted">
                      {(e.exam_date || '').slice(0, 10)} · {e.total_students || 0} 人
                    </span>
                    {e.question_stats?.question_count ? (
                      <Tag tone="green" size="sm">
                        {e.question_stats.question_count} 题
                      </Tag>
                    ) : null}
                    <div className="ml-auto flex items-center gap-2">
                      <Button size="sm" variant="secondary" onClick={() => { setAddToExamId(e.record_id); setTab('bank') }}>
                        <Plus size={13} />
                        加题目
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => openPreview(e)}>
                        <Eye size={13} />
                        预览
                      </Button>
                      <Button size="sm" variant="ai" onClick={() => publishExam(e)}>
                        <Send size={13} />
                        发布
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => deleteExam(e)}>
                        <Trash2 size={13} />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 试卷预览 Modal */}
      <Modal open={previewExam !== null} onClose={() => setPreviewExam(null)} title={`试卷预览 · ${previewExam?.name || ''}`} wide hideFooter>
        {previewQuestions.length > 0 && (
          <div className="flex items-center justify-end gap-2 mb-2">
            <div className="flex rounded-[var(--radius-md)] border border-border overflow-hidden text-xs">
              <button
                type="button"
                onClick={() => setPrintWithAnswers(false)}
                className={`px-3 py-1.5 ${!printWithAnswers ? 'bg-primary text-white' : 'text-ink-muted'}`}
              >
                学生版
              </button>
              <button
                type="button"
                onClick={() => setPrintWithAnswers(true)}
                className={`px-3 py-1.5 ${printWithAnswers ? 'bg-primary text-white' : 'text-ink-muted'}`}
              >
                教师版(含解析)
              </button>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                printPaper(
                  `试卷：${previewExam?.name || '考试'}`,
                  previewQuestions.map((q) => ({
                    content: q.content,
                    options: q.options,
                    answer: q.answer,
                    analysis: q.analysis,
                    _typeLabel: '题目',
                  })),
                  printWithAnswers,
                )
              }
            >
              <Printer size={13} />
              打印试卷
            </Button>
          </div>
        )}
        {previewQuestions.length === 0 ? (
          <EmptyState title="该试卷暂无题目" description="尚未添加题目到这场考试" />
        ) : (
          <div className="space-y-3">
            {previewQuestions.map((q, i) => (
              <div key={q.question_id || q.id || i} className="border border-border rounded-[var(--radius-md)] p-3.5">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-5 h-5 rounded-full bg-primary-soft text-primary text-[11px] font-semibold flex items-center justify-center">
                    {i + 1}
                  </span>
                  {(q.knowledge_points || []).slice(0, 2).map((k) => (
                    <Tag key={k} tone="gray" size="sm">
                      {k}
                    </Tag>
                  ))}
                </div>
                <QuestionMd text={q.content || ''} />
                <AnswerMd text={q.answer || ''} className="mt-2" />
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* 选真题作蓝本（变种题入口） */}
      <VariantBrowserModal
        open={variantOpen}
        onClose={() => setVariantOpen(false)}
        onPick={(q, label) => {
          setVariantQid(q.exam_id || q.question_id || '')
          setVariantLabel(label)
          setUseVariant(true)
          setVariantOpen(false)
          toast.success(`已设置蓝本: ${label}`)
        }}
      />

      {/* ═══ 题库题目加入考试弹窗 ═══ */}
      <AntModal
        open={addToExamOpen}
        onCancel={() => setAddToExamOpen(false)}
        onOk={confirmAddToExam}
        okText="加入考试"
        cancelText="取消"
        confirmLoading={addToExamBusy}
        title="加入考试"
      >
        <div className="space-y-3">
          <p className="text-sm text-ink-secondary m-0">
            将把已选的 <b>{selectedBankIds.length}</b> 道题加入考试试卷。
          </p>
          <AntSelect
            value={addToExamId}
            onChange={setAddToExamId}
            placeholder="选择目标考试…"
            className="w-full"
            options={examList.map((e) => ({
              value: e.record_id,
              label: `${e.name}（${e.total_students || 0}人）`,
            }))}
          />
          {examList.length === 0 && (
            <p className="text-xs text-warning m-0">还没有考试，请先到「考试列表」创建考试</p>
          )}
        </div>
      </AntModal>
    </div>
  )
}
