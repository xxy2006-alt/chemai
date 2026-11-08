import { useCallback, useEffect, useRef, useState } from 'react'
import { UploadCloud, X, FileText, RotateCcw, Play, Save, Clock, CheckCircle2, Undo2 } from 'lucide-react'
import { api, getTeacherId } from '../../lib/api'
import { Button, Card, EmptyState, Select, useToast } from '../../components/ui'

interface BatchTask {
  task_id: string
  title?: string
  status?: 'pend' | 'done' | 'failed' | string
  progress?: number
  student_name?: string
  student_id?: string
}

interface Batch {
  created_at?: string
  tasks: BatchTask[]
}

interface GradeResult {
  student_name?: string
  task_id?: string
  score?: number
  total?: number
  error?: string
}

interface ExamOption {
  id: string
  name: string
}

interface QueueBatch {
  batch_id: string
  tasks: number
}

interface SubmissionAnswer {
  answer_id: string
  question_id: string
  content: string
  student_answer: string | null
  is_correct: boolean
  reason?: string | null
  source?: string | null
}

interface SubmissionStudent {
  student_id: string
  name?: string
  questions: SubmissionAnswer[]
}

interface UnconfirmedExam {
  exam_record_id: string
  name?: string
  class_id?: string
  answers: number
  student_count: number
}

type Tab = 'upload' | 'queue' | 'online'

/** 判卷中心 · 答题卡批量批改 + 待确认队列 + 线上作答改判 */
export function OcrSheetsPage() {
  const toast = useToast()
  const uid = getTeacherId()
  const [tab, setTab] = useState<Tab>('upload')
  const [files, setFiles] = useState<(File & { _title?: string })[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [batches, setBatches] = useState<Record<string, Batch>>({})
  const [examOptions, setExamOptions] = useState<ExamOption[]>([])
  const [gradeInputs, setGradeInputs] = useState<Record<string, string>>({})
  const [gradeExam, setGradeExam] = useState<Record<string, string>>({})
  const [gradeResults, setGradeResults] = useState<Record<string, { kind: 'ok' | 'err'; text: string }[]>>({})
  const [saving, setSaving] = useState<Record<string, boolean>>({})
  const [queue, setQueue] = useState<QueueBatch[]>([])
  const [unconfirmed, setUnconfirmed] = useState<UnconfirmedExam[]>([])
  const [confirming, setConfirming] = useState<Record<string, boolean>>({})
  const [onlineExam, setOnlineExam] = useState('')
  const [submissions, setSubmissions] = useState<SubmissionStudent[]>([])
  const [subLoading, setSubLoading] = useState(false)
  const [overriding, setOverriding] = useState<Record<string, boolean>>({})
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadBatches = useCallback(async () => {
    try {
      const d = await api.get<{ batches?: Record<string, Batch> }>(`/api/ocr/tasks?teacher_id=${uid}`)
      setBatches(d.batches || {})
    } catch {
      /* ignore */
    }
  }, [uid])

  const loadExams = useCallback(async () => {
    try {
      const c = await api.get<{ classes?: { class_id?: string }[] }>(`/api/classes?teacher_id=${uid}`)
      const classes = (c.classes || []).slice(0, 5)
      const lists = await Promise.all(
        classes.map((cls) =>
          api
            .get<{ exams?: { record_id: string; name: string }[] }>(`/api/exam/list/${cls.class_id}`)
            .catch(() => ({ exams: [] })),
        ),
      )
      const options: ExamOption[] = []
      lists.forEach((l) => (l.exams || []).forEach((e) => options.push({ id: e.record_id, name: e.name })))
      setExamOptions(options)
    } catch {
      /* ignore */
    }
  }, [uid])

  const loadQueue = useCallback(async () => {
    try {
      const d = await api.get<{ pending_confirm?: QueueBatch[]; unconfirmed_exams?: UnconfirmedExam[] }>(
        '/api/ocr/grading/queue',
      )
      setQueue(d.pending_confirm || [])
      setUnconfirmed(d.unconfirmed_exams || [])
    } catch {
      /* ignore */
    }
  }, [])

  const loadSubmissions = useCallback(async (examId: string) => {
    if (!examId) {
      setSubmissions([])
      return
    }
    setSubLoading(true)
    try {
      const d = await api.get<{ students?: SubmissionStudent[] }>(
        `/api/ocr/grading/submissions?exam_id=${examId}`,
      )
      setSubmissions(d.students || [])
    } catch {
      setSubmissions([])
    } finally {
      setSubLoading(false)
    }
  }, [])

  useEffect(() => {
    loadBatches()
    loadExams()
    loadQueue()
    // 每 5s 轮询批次状态
    const timer = window.setInterval(loadBatches, 5000)
    return () => window.clearInterval(timer)
  }, [loadBatches, loadExams, loadQueue])

  async function confirmGrades(examId: string) {
    setConfirming((prev) => ({ ...prev, [examId]: true }))
    try {
      const d = await api.post<{ detail?: string; confirmed?: number }>(`/api/exam/${examId}/confirm`)
      if (d.detail) {
        toast.error(d.detail)
      } else {
        toast.success(`成绩已生效（${d.confirmed ?? 0} 条作答），诊断已重新计算`)
        loadQueue()
      }
    } catch {
      toast.error('确认失败')
    } finally {
      setConfirming((prev) => ({ ...prev, [examId]: false }))
    }
  }

  async function overrideAnswer(a: SubmissionAnswer) {
    setOverriding((prev) => ({ ...prev, [a.answer_id]: true }))
    try {
      await api.post('/api/ocr/grading/override', {
        answer_id: a.answer_id,
        is_correct: !a.is_correct,
        reason: '判卷中心页改判',
      })
      toast.success(`已改判为${!a.is_correct ? '正确' : '错误'}，诊断将重新计算`)
      loadSubmissions(onlineExam)
    } catch {
      toast.error('改判失败')
    } finally {
      setOverriding((prev) => ({ ...prev, [a.answer_id]: false }))
    }
  }

  function addFiles(list: FileList | File[]) {
    setFiles((prev) => {
      const next = [...prev]
      for (const f of Array.from(list)) {
        if (next.length >= 10) break
        next.push(f as File & { _title?: string })
      }
      return next
    })
  }

  function removeFile(i: number) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i))
  }

  async function submitBatch() {
    if (!files.length) return
    setSubmitting(true)
    const fd = new FormData()
    fd.append('teacher_id', uid)
    files.forEach((f) => fd.append('files', f))
    try {
      const d = await api.post<{ success?: boolean; detail?: string }>('/api/ocr/tasks/batch', fd)
      if (d.success !== false) {
        setFiles([])
        await loadBatches()
        toast.success('已提交，可继续上传下一批')
      } else {
        toast.error(`失败: ${d.detail || ''}`)
      }
    } catch (e) {
      toast.error(`网络错误: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setSubmitting(false)
    }
  }

  async function retry(taskId: string) {
    try {
      await api.post(`/api/ocr/tasks/${taskId}/retry`)
      loadBatches()
    } catch {
      /* ignore */
    }
  }

  async function gradeBatch(bid: string) {
    const text = (gradeInputs[bid] || '').trim()
    const exam = gradeExam[bid] || ''
    if (!text && !exam) {
      setGradeResults((prev) => ({ ...prev, [bid]: [{ kind: 'err', text: '请先粘贴标准答案或选择关联考试' }] }))
      return
    }
    setGradeResults((prev) => ({ ...prev, [bid]: [{ kind: 'ok', text: '批改中…' }] }))
    const body: Record<string, unknown> = { batch_id: bid, teacher_id: uid }
    if (text) body.correct_answers = text
    else body.exam_id = exam
    try {
      const d = await api.post<{ detail?: string; results?: GradeResult[] }>('/api/ocr/grading/grade', body)
      if (d.detail) {
        setGradeResults((prev) => ({ ...prev, [bid]: [{ kind: 'err', text: d.detail! }] }))
        return
      }
      const lines: { kind: 'ok' | 'err'; text: string }[] = []
      ;(d.results || []).forEach((r) => {
        if (r.error) lines.push({ kind: 'err', text: `${r.student_name || r.task_id}：${r.error}` })
        else lines.push({ kind: 'ok', text: `${r.student_name || r.task_id}：${r.score}/${r.total} 分` })
      })
      setGradeResults((prev) => ({ ...prev, [bid]: lines }))
    } catch {
      setGradeResults((prev) => ({ ...prev, [bid]: [{ kind: 'err', text: '网络错误' }] }))
    }
  }

  async function saveBatch(bid: string) {
    const exam = gradeExam[bid] || ''
    if (!exam) {
      setGradeResults((prev) => ({ ...prev, [bid]: [{ kind: 'err', text: '保存必须关联一场考试（下拉选择）' }] }))
      return
    }
    setSaving((prev) => ({ ...prev, [bid]: true }))
    try {
      const d = await api.post<{ detail?: string; message?: string; diagnosis?: string }>('/api/ocr/grading/save', {
        batch_id: bid,
        teacher_id: uid,
        exam_id: exam,
      })
      if (d.detail) {
        setGradeResults((prev) => ({ ...prev, [bid]: [{ kind: 'err', text: d.detail! }] }))
      } else {
        setGradeResults((prev) => ({ ...prev, [bid]: [{ kind: 'ok', text: `${d.message || '已保存'} · 诊断：${d.diagnosis || '-'}` }] }))
        loadBatches()
      }
    } catch {
      setGradeResults((prev) => ({ ...prev, [bid]: [{ kind: 'err', text: '网络错误' }] }))
    } finally {
      setSaving((prev) => ({ ...prev, [bid]: false }))
    }
  }

  const batchIds = Object.keys(batches).sort().reverse()

  const tabBtn = (id: Tab, label: string, badge?: number) => (
    <button
      onClick={() => setTab(id)}
      className={`px-4 py-2 text-sm rounded-full transition-colors cursor-pointer border ${
        tab === id
          ? 'bg-teal-soft text-teal border-teal/40 font-medium'
          : 'bg-transparent text-ink-secondary border-transparent hover:bg-surface-muted'
      }`}
    >
      {label}
      {badge ? (
        <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full bg-error text-white">{badge}</span>
      ) : null}
    </button>
  )

  return (
    <div className="animate-fade-in-up">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h1 className="text-[22px] font-semibold text-ink m-0">判卷中心</h1>
          <p className="mt-1 text-sm text-ink-secondary">答题卡批量批改 · 线上作答 · 教师改判 — 所有判卷经同一入口</p>
        </div>
      </div>

      <div className="flex items-center gap-1 mb-5 flex-wrap">
        {tabBtn('upload', '答题卡批量')}
        {tabBtn('queue', '待确认队列', queue.length + unconfirmed.length)}
        {tabBtn('online', '线上提交与改判')}
      </div>

      {tab === 'upload' && (
      <>
      {/* 上传区 */}
      <Card className="mb-6">
        <div
          onDragOver={(e) => {
            e.preventDefault()
          }}
          onDrop={(e) => {
            e.preventDefault()
            addFiles(e.dataTransfer.files)
          }}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-border-strong rounded-[var(--radius-md)] p-8 text-center hover:border-teal/50 hover:bg-surface-muted/40 transition-colors cursor-pointer"
        >
          <UploadCloud size={30} className="mx-auto text-teal mb-2.5" />
          <div className="text-sm font-medium text-ink">拖拽答题卡到此处，或点击选择（最多 10 张）</div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files)
              e.target.value = ''
            }}
          />
        </div>

        {files.length > 0 && (
          <div className="mt-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {files.map((f, i) => (
                <div key={i} className="relative border border-border rounded-[var(--radius-md)] overflow-hidden group">
                  <img src={URL.createObjectURL(f)} alt={f.name} className="w-full h-[90px] object-cover bg-surface-muted" />
                  <div className="px-2 py-1.5 text-xs text-ink-secondary truncate">{f._title || f.name}</div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFile(i)
                    }}
                    className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-ink/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-3 mt-4">
              <Button onClick={submitBatch} loading={submitting}>
                <UploadCloud size={15} />
                提交识别
              </Button>
              <Button variant="secondary" onClick={() => setFiles([])}>
                清空
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* 批次列表 */}
      <div className="space-y-4">
        {batchIds.length === 0 ? (
          <Card>
            <EmptyState title="暂无批改记录" description="上传答题卡后，批次状态会显示在这里" />
          </Card>
        ) : (
          batchIds.map((bid) => {
            const b = batches[bid]
            const pending = b.tasks.filter((t) => t.status === 'pend').length
            const failed = b.tasks.filter((t) => t.status === 'failed').length
            const done = b.tasks.filter((t) => t.status === 'done').length
            return (
              <Card key={bid} id={`batch-${bid}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-xs text-ink-muted">
                    <Clock size={13} />
                    {b.created_at || bid}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-ink-muted">
                      {done} 完成 · {pending} 排队 · {failed} 失败
                    </span>
                  </div>
                </div>
                <div className="space-y-2">
                  {b.tasks.map((t) => {
                    const statusCls =
                      t.status === 'done'
                        ? 'text-success bg-success-soft'
                        : t.status === 'failed'
                          ? 'text-error bg-error-soft'
                          : 'text-teal bg-teal-soft'
                    const statusLabel =
                      t.status === 'done' ? '已完成' : t.status === 'failed' ? '失败' : '排队中'
                    return (
                      <div key={t.task_id} className="flex items-center gap-3 px-3 py-2.5 bg-surface-muted/50 rounded-[var(--radius-md)]">
                        <div className="w-8 h-8 rounded-[var(--radius-sm)] bg-surface border border-border flex items-center justify-center shrink-0">
                          <FileText size={14} className="text-ink-muted" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 text-[13px]">
                            <span className="font-medium text-ink truncate">{t.title || '答题卡'}</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${statusCls}`}>{statusLabel}</span>
                          </div>
                          {(t.student_name || t.student_id) && (
                            <div className="text-[11px] text-ink-muted mt-0.5">
                              {t.student_name} · {t.student_id}
                            </div>
                          )}
                          <div className="h-1.5 bg-border/60 rounded-full mt-1.5 overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${
                                t.status === 'failed' ? 'bg-error' : t.status === 'done' ? 'bg-success' : 'bg-teal animate-pulse'
                              }`}
                              style={{ width: `${t.progress || 0}%` }}
                            />
                          </div>
                        </div>
                        {t.status === 'failed' && (
                          <Button size="sm" variant="secondary" onClick={() => retry(t.task_id)}>
                            <RotateCcw size={12} />
                            重试
                          </Button>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* 批改面板 */}
                <div className="mt-3 pt-3 border-t border-border">
                  <textarea
                    value={gradeInputs[bid] || ''}
                    onChange={(e) => setGradeInputs((prev) => ({ ...prev, [bid]: e.target.value }))}
                    placeholder={'标准答案，每行一题，如：\n1.A 2.B 3.C\n13. Cu + 2H2SO4(浓)…'}
                    className="w-full min-h-[70px] px-3.5 py-2.5 rounded-[var(--radius-md)] border border-border text-sm text-ink placeholder:text-ink-muted outline-none focus:border-primary focus:ring-2 focus:ring-primary/15 resize-y"
                  />
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <div className="w-[200px]">
                      <Select
                        value={gradeExam[bid] || ''}
                        onChange={(e) => setGradeExam((prev) => ({ ...prev, [bid]: e.target.value }))}
                      >
                        <option value="">关联考试（可选）</option>
                        {examOptions.map((e) => (
                          <option key={e.id} value={e.id}>
                            {e.name}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <Button size="sm" variant="ai" onClick={() => gradeBatch(bid)}>
                      <Play size={13} />
                      开始批改
                    </Button>
                    <Button size="sm" variant="secondary" loading={saving[bid]} onClick={() => saveBatch(bid)}>
                      <Save size={13} />
                      确认保存
                    </Button>
                  </div>
                  {gradeResults[bid]?.length ? (
                    <div className="mt-2.5 space-y-1">
                      {gradeResults[bid].map((r, i) => (
                        <div key={i} className={`text-[13px] ${r.kind === 'err' ? 'text-error' : 'text-ink-secondary'}`}>
                          {r.text}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </Card>
            )
          })
        )}
      </div>
      </>
      )}

      {tab === 'queue' && (
        <div className="space-y-4">
          {unconfirmed.map((e) => (
            <Card key={e.exam_record_id}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-ink">{e.name || e.exam_record_id}</div>
                  <div className="text-xs text-ink-muted mt-0.5">
                    {e.student_count} 名学生 · {e.answers} 条作答已判待确认，确认前成绩不计入统计
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ai"
                  loading={confirming[e.exam_record_id]}
                  onClick={() => confirmGrades(e.exam_record_id)}
                >
                  <CheckCircle2 size={13} />
                  确认成绩生效
                </Button>
              </div>
            </Card>
          ))}
          {queue.length === 0 && unconfirmed.length === 0 ? (
            <Card>
              <EmptyState title="暂无待确认批次" description="批改完成但尚未保存的答题卡批会出现在这里" />
            </Card>
          ) : (
            queue.map((b) => (
              <Card key={b.batch_id}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-ink">{b.batch_id}</div>
                    <div className="text-xs text-ink-muted mt-0.5">{b.tasks} 张答题卡已批改，待确认保存</div>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setTab('upload')
                      const bid = b.batch_id
                      setTimeout(() => {
                        document.getElementById(`batch-${bid}`)?.scrollIntoView({ behavior: 'smooth' })
                      }, 50)
                    }}
                  >
                    去确认保存
                  </Button>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {tab === 'online' && (
        <div className="space-y-4">
          <Card>
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm text-ink-secondary">选择考试：</span>
              <div className="w-[260px]">
                <Select
                  value={onlineExam}
                  onChange={(e) => {
                    setOnlineExam(e.target.value)
                    loadSubmissions(e.target.value)
                  }}
                >
                  <option value="">— 选择一场考试/练习 —</option>
                  {examOptions.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name}
                    </option>
                  ))}
                </Select>
              </div>
              {subLoading && <span className="text-sm text-ink-muted">加载中…</span>}
            </div>
          </Card>

          {onlineExam && unconfirmed.some((e) => e.exam_record_id === onlineExam) && (
            <Card>
              <div className="flex items-center justify-between gap-3">
                <div className="text-[13px] text-ink-secondary">
                  这场考试的成绩尚未确认生效：确认前不计入统计与诊断
                </div>
                <Button
                  size="sm"
                  variant="ai"
                  loading={confirming[onlineExam]}
                  onClick={() => confirmGrades(onlineExam)}
                >
                  <CheckCircle2 size={13} />
                  确认成绩生效
                </Button>
              </div>
            </Card>
          )}

          {!onlineExam ? (
            <Card>
              <EmptyState title="选择考试查看作答" description="可逐题改判 AI 判定结果，改判后诊断自动重算" />
            </Card>
          ) : submissions.length === 0 ? (
            <Card>
              <EmptyState title="暂无作答记录" description="该考试还没有学生作答入库" />
            </Card>
          ) : (
            submissions.map((s) => (
              <Card key={s.student_id}>
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-medium text-ink">
                    {s.name || s.student_id}
                    <span className="ml-2 text-xs text-ink-muted">{s.student_id}</span>
                  </div>
                  <span className="text-xs text-ink-muted">
                    {s.questions.filter((q) => q.is_correct).length}/{s.questions.length} 正确
                  </span>
                </div>
                <div className="space-y-2">
                  {s.questions.map((q) => (
                    <div
                      key={q.answer_id}
                      className="flex items-start gap-3 px-3 py-2.5 bg-surface-muted/50 rounded-[var(--radius-md)]"
                    >
                      {q.is_correct ? (
                        <CheckCircle2 size={16} className="text-success mt-0.5 shrink-0" />
                      ) : (
                        <Undo2 size={16} className="text-error mt-0.5 shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="text-[13px] text-ink truncate">{q.content || q.question_id}</div>
                        <div className="text-xs text-ink-muted mt-0.5">
                          作答：{q.student_answer || '（空）'}
                          {q.reason ? ` · ${q.reason}` : ''}
                          {q.source ? ` · ${q.source}` : ''}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={overriding[q.answer_id]}
                        onClick={() => overrideAnswer(q)}
                      >
                        改判为{q.is_correct ? '错误' : '正确'}
                      </Button>
                    </div>
                  ))}
                </div>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  )
}
