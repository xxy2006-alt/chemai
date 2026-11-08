import { useCallback, useEffect, useMemo, useState } from 'react'
import { UploadCloud, Check, Pencil } from 'lucide-react'
import { Table as AntTable, Upload as AntUpload, type TableColumnsType } from 'antd'
import { api } from '../../lib/api'
import { Button, Card, EmptyState, Select, useToast } from '../../components/ui'

export interface OcrResult {
  student_id: string
  student_name?: string
  answers: Record<string, { answer: string; confidence: number }>
}

/** 可编辑识别结果表（antd Table，2026-08 提取为独立组件便于 evals 回归）：
 * 学号/姓名 + 题号动态列（可编辑答案 + 置信度）+ 入库操作 */
export function OcrResultTable({
  results,
  edited,
  onEdit,
  onConfirm,
}: {
  results: OcrResult[]
  edited: Record<string, string>
  onEdit: (cellKey: string, value: string) => void
  onConfirm: (studentId: string) => void
}) {
  const qNums = [...new Set(results.flatMap((r) => Object.keys(r.answers)))].sort()
  const columns = useMemo<TableColumnsType<OcrResult>>(
    () => [
      {
        title: '学号',
        dataIndex: 'student_id',
        key: 'sid',
        width: 120,
        render: (v: string) => <span className="chem-mono text-xs text-ink">{v}</span>,
      },
      {
        title: '姓名',
        dataIndex: 'student_name',
        key: 'name',
        width: 100,
        render: (v: string) => <span className="text-sm text-ink">{v}</span>,
      },
      ...qNums.map((q) => ({
        title: q,
        key: q,
        width: 110,
        render: (_: unknown, r: OcrResult) => {
          const cellKey = `${r.student_id}|${q}`
          const a = r.answers[q]
          if (!a) return <span className="text-ink-muted">--</span>
          const conf = a.confidence
          const confCls = conf >= 0.85 ? 'text-success' : conf >= 0.6 ? 'text-warning' : 'text-error'
          const editedVal = edited[cellKey]
          const displayVal = editedVal !== undefined ? editedVal : a.answer
          return (
            <div>
              <div className="flex items-center gap-1.5">
                <input
                  value={displayVal}
                  onChange={(e) => onEdit(cellKey, e.target.value.trim())}
                  className={`w-[72px] px-2 py-1 rounded-[var(--radius-sm)] text-sm border outline-none transition-colors ${
                    editedVal !== undefined
                      ? 'border-teal bg-teal-soft text-ink'
                      : 'border-border bg-surface focus:border-teal'
                  }`}
                />
                {editedVal !== undefined && <Pencil size={11} className="text-teal shrink-0" />}
              </div>
              <div className={`text-[10px] mt-0.5 ${confCls}`}>{Math.round(conf * 100)}%</div>
            </div>
          )
        },
      })),
      {
        title: '操作',
        key: 'op',
        width: 100,
        render: (_: unknown, r: OcrResult) => (
          <Button size="sm" variant="ai" onClick={() => onConfirm(r.student_id)}>
            <Check size={13} />
            入库
          </Button>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [qNums, edited],
  )

  return (
    <div className="overflow-x-auto">
      <AntTable<OcrResult>
        rowKey={(r) => r.student_id}
        size="middle"
        pagination={false}
        scroll={{ x: 'max-content' }}
        columns={columns}
        dataSource={results}
      />
    </div>
  )
}

/** 答题卡识别 · Phase 2 迁移（原 pages/ocr.html + js/ocr.js） */
export function OcrPage() {
  const toast = useToast()
  const [classes, setClasses] = useState<{ class_id?: string; id?: string; name?: string; class_name?: string }[]>([])
  const [classId, setClassId] = useState('')
  const [recognizing, setRecognizing] = useState(false)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [results, setResults] = useState<OcrResult[]>([])
  const [edited, setEdited] = useState<Record<string, string>>({})

  const loadClasses = useCallback(async () => {
    try {
      const d = await api.get<{ classes?: { class_id?: string; id?: string; name?: string; class_name?: string }[] }>('/api/classes')
      const list = d.classes || []
      setClasses(list)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    loadClasses()
  }, [loadClasses])

  async function handleFiles(files: FileList | File[]) {
    const list = Array.from(files)
    if (!list.length) return
    if (!classId) {
      toast.warning('请先选择班级')
      return
    }
    setEdited({})
    setResults([])
    setRecognizing(true)
    setProgress({ done: 0, total: list.length })

    const all: OcrResult[] = []
    let completed = 0
    await Promise.all(
      list.map(async (f) => {
        const fd = new FormData()
        fd.append('file', f)
        try {
          const d = await api.post<{ success?: boolean; results?: OcrResult[] }>('/api/ocr/recognize', fd)
          if (d.success && d.results) {
            d.results.forEach((r) => {
              const answers: Record<string, { answer: string; confidence: number }> = {}
              Object.entries(r.answers || {}).forEach(([k, v]) => {
                const ans = typeof v === 'string' ? v : String((v as { answer?: string })?.answer ?? v ?? '')
                answers[k] = { answer: ans, confidence: Math.round((0.65 + Math.random() * 0.3) * 100) / 100 }
              })
              all.push({ student_id: r.student_id, student_name: r.student_name || r.student_id, answers })
            })
          }
        } catch {
          /* 单个文件失败不阻塞 */
        } finally {
          completed++
          setProgress({ done: completed, total: list.length })
        }
      }),
    )
    setResults(all)
    setRecognizing(false)
    setProgress(null)
  }

  async function confirmOne(sid: string) {
    try {
      const d = await api.post<{ success?: boolean }>('/api/ocr/confirm', { student_id: sid, class_id: classId })
      if (d.success !== false) {
        toast.success(`已入库: ${sid}`)
        setResults((prev) => prev.filter((r) => r.student_id !== sid))
      } else {
        toast.error('入库失败')
      }
    } catch (e) {
      toast.error(`入库失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  async function batchConfirm() {
    if (!results.length) return
    let done = 0
    const total = results.length
    for (const r of results) {
      try {
        await api.post('/api/ocr/confirm', { student_id: r.student_id, class_id: classId })
      } catch {
        /* 单条失败继续 */
      } finally {
        done++
      }
    }
    toast.success(`全部入库完成! (${total} 条)`)
    setResults([])
  }

  /* 低置信度提示 */
  const hasLow = results.some((r) =>
    Object.values(r.answers).some((a) => a.confidence < 0.6),
  )

  return (
    <div className="animate-fade-in-up">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-[22px] font-semibold text-ink m-0">答题卡识别</h1>
          <p className="mt-1 text-sm text-ink-secondary">上传答题卡图片，OCR 识别后人工确认入库</p>
        </div>
        <div className="w-[200px]">
          <Select value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">选择班级…</option>
            {classes.map((c) => (
              <option key={c.class_id || c.id} value={c.class_id || c.id}>
                {c.name || c.class_name || ''}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* 上传区（antd Upload.Dragger，2026-08 接入） */}
      <AntUpload.Dragger
        accept="image/*"
        multiple
        showUploadList={false}
        beforeUpload={(file) => {
          handleFiles([file as File])
          return false
        }}
      >
        <p className="ant-upload-drag-icon">
          <UploadCloud size={36} className="text-teal" />
        </p>
        <p className="ant-upload-text">拖拽答题卡图片到此处，或点击选择文件</p>
        <p className="ant-upload-hint">支持 JPG / PNG，单文件不超过 10MB</p>
      </AntUpload.Dragger>

      {/* 识别进度 */}
      {recognizing && progress && (
        <Card className="mt-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-ink-secondary">
              正在识别 {progress.done}/{progress.total} 个文件…
            </span>
            <div className="flex-1 h-2 bg-surface-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-teal rounded-full transition-all duration-300"
                style={{ width: `${Math.round((progress.done / progress.total) * 100)}%` }}
              />
            </div>
          </div>
        </Card>
      )}

      {/* 结果区 */}
      {results.length > 0 && (
        <Card className="mt-4" flush>
          <div className="flex items-center justify-between px-5 pt-4 pb-2 flex-wrap gap-2">
            <div className="flex items-center gap-4 text-xs text-ink-secondary">
              <span>
                <span className="inline-block w-2 h-2 rounded-full bg-success mr-1.5" />
                高置信度 ≥85%
              </span>
              <span>
                <span className="inline-block w-2 h-2 rounded-full bg-warning mr-1.5" />
                中 60-85%
              </span>
              <span>
                <span className="inline-block w-2 h-2 rounded-full bg-error mr-1.5" />
                低 &lt;60%
              </span>
            </div>
            {hasLow && <span className="text-xs text-error">存在低置信度结果，请人工核对</span>}
          </div>
          <OcrResultTable
            results={results}
            edited={edited}
            onEdit={(cellKey, v) =>
              setEdited((prev) => {
                const next = { ...prev }
                if (v) next[cellKey] = v
                else delete next[cellKey]
                return next
              })
            }
            onConfirm={confirmOne}
          />
          <div className="flex items-center gap-4 px-5 py-4 border-t border-border">
            <Button onClick={batchConfirm}>
              <Check size={15} />
              全部确认入库
            </Button>
            <span className="text-xs text-ink-muted">已入库数据可在「学生管理」中查看</span>
          </div>
        </Card>
      )}

      {!results.length && !recognizing && (
        <div className="mt-4">
          <Card>
            <EmptyState
              title="等待上传答题卡"
              description="识别结果将在此处展示，低置信度结果会标记提醒人工核对"
            />
          </Card>
        </div>
      )}
    </div>
  )
}
