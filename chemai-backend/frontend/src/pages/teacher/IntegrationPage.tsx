import { useCallback, useEffect, useState } from 'react'
import { KeyRound, Webhook, Plus, Trash2, TriangleAlert } from 'lucide-react'
import { Checkbox, Table as AntTable, type TableColumnsType } from 'antd'
import { api, can } from '../../lib/api'
import { Button, Card, EmptyState, Field, Input, Modal, Select, Tabs, Tag, useToast } from '../../components/ui'

/* 权限项 —— 与后端 `permissions_for()` 同形："资源:动作" */
const PERMISSION_PRESETS = [
  { value: 'student:read', label: '读取学生' },
  { value: 'class:read', label: '读取班级' },
  { value: 'exam:read', label: '读取考试' },
  { value: 'analysis:read', label: '读取学情分析' },
  { value: 'notification:create', label: '发送通知' },
]

interface ApiKey {
  api_key: string
  name?: string
  permissions?: string[]
  created_at?: string
}

interface WebhookRow {
  event_type: string
  url: string
  enabled: boolean
  registered_at?: string
}

/**
 * 顶部横幅：把「展示性占位」说清楚。
 *
 * 后端现状（阶段 4.7 时核实）：`GET /api-keys` 是硬编码空列表 + TODO，密钥不落库；
 * `WebhookService.webhooks` 是**进程内存字典**，重启即丢。不说清楚的话，
 * 管理员创建完密钥一刷新就没了，会当成 bug 报上来。
 */
function PlaceholderNotice() {
  return (
    <div className="flex items-start gap-3 px-4 py-3 rounded-[var(--radius-md)] bg-warning-soft border border-warning/20">
      <TriangleAlert size={16} className="text-warning shrink-0 mt-0.5" />
      <div className="text-[13px] text-ink-secondary leading-relaxed">
        <span className="font-medium text-ink">当前为展示性占位。</span>
        API 密钥没有任何地方校验、也不落库；Webhook 存在服务进程内存里、重启即丢。
        这一页现在只用于确认入口权限与交互正常，真正生效需要后端补持久化与校验。
      </div>
    </div>
  )
}

/* ── Tab 1：API 密钥 ────────────────────────────────────── */

function ApiKeysTab() {
  const toast = useToast()
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [perms, setPerms] = useState<string[]>(['student:read'])
  const [issued, setIssued] = useState<{ api_key: string; api_secret: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await api.get<{ keys: ApiKey[] }>('/api/integration/api-keys')
      setKeys(d.keys || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

  async function handleCreate() {
    if (!name.trim() || perms.length === 0) {
      toast.error('请填写名称并至少选一项权限')
      return
    }
    try {
      // 后端这两个参数是**查询参数**（端点没有 Pydantic 模型），列表用重复 key 传
      const qs = new URLSearchParams({ name: name.trim() })
      perms.forEach((p) => qs.append('permissions', p))
      const d = await api.post<{ api_key: string; api_secret: string }>(
        `/api/integration/api-keys?${qs.toString()}`,
      )
      setCreating(false)
      setName('')
      setIssued({ api_key: d.api_key, api_secret: d.api_secret })
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '创建失败')
    }
  }

  async function handleDelete(key: ApiKey) {
    try {
      await api.del(`/api/integration/api-keys/${encodeURIComponent(key.api_key)}`)
      toast.success('已删除')
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const columns: TableColumnsType<ApiKey> = [
    {
      title: '密钥',
      dataIndex: 'api_key',
      render: (v: string) => <span className="font-mono text-xs">{v}</span>,
    },
    { title: '名称', dataIndex: 'name', width: 160 },
    {
      title: '权限',
      dataIndex: 'permissions',
      render: (v: string[] | undefined) => (
        <span className="flex flex-wrap gap-1">
          {(v || []).map((p) => (
            <Tag key={p} tone="blue">
              {p}
            </Tag>
          ))}
        </span>
      ),
    },
    {
      title: '',
      key: 'ops',
      width: 70,
      render: (_: unknown, row: ApiKey) =>
        can('integration:delete') ? (
          <Button variant="ghost" size="sm" onClick={() => void handleDelete(row)} title="删除">
            <Trash2 size={14} />
          </Button>
        ) : null,
    },
  ]

  return (
    <div className="space-y-4">
      <Card
        title="API 密钥"
        action={
          can('integration:create') ? (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus size={14} className="mr-1" />
              创建密钥
            </Button>
          ) : null
        }
        flush={keys.length > 0}
      >
        {loading ? (
          <div className="py-10 text-center text-sm text-ink-muted">加载中…</div>
        ) : keys.length === 0 ? (
          <EmptyState
            illustration={<KeyRound size={22} className="text-ink-muted" />}
            title="还没有 API 密钥"
            description="后端目前不持久化密钥，创建后只在弹窗里显示一次。"
          />
        ) : (
          <AntTable<ApiKey> rowKey="api_key" columns={columns} dataSource={keys} pagination={false} size="small" />
        )}
      </Card>

      <Modal
        open={creating}
        title="创建 API 密钥"
        onClose={() => setCreating(false)}
        onConfirm={() => void handleCreate()}
        confirmText="创建"
      >
        <div className="space-y-4">
          <Field label="名称">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="如：教务系统对接" />
          </Field>
          <Field label="权限" hint="该密钥可调用的范围">
            <Checkbox.Group
              options={PERMISSION_PRESETS}
              value={perms}
              onChange={(v) => setPerms(v as string[])}
            />
          </Field>
        </div>
      </Modal>

      {/* 一次性展示密钥 —— 只有「我已保存」一个动作，不要通用底部按钮 */}
      <Modal
        open={!!issued}
        title="密钥已生成"
        onClose={() => setIssued(null)}
        onConfirm={() => setIssued(null)}
        confirmText="我已保存"
        hideFooter={false}
        cancelText=""
      >
        <p className="text-[13px] text-ink-secondary mb-3">
          <span className="font-medium text-ink">Secret 只显示这一次</span>，关闭后无法再查看。
        </p>
        <div className="space-y-3">
          <Field label="API Key">
            <Input readOnly value={issued?.api_key || ''} />
          </Field>
          <Field label="API Secret">
            <Input readOnly value={issued?.api_secret || ''} />
          </Field>
        </div>
      </Modal>
    </div>
  )
}

/* ── Tab 2：Webhook ─────────────────────────────────────── */

function WebhooksTab() {
  const toast = useToast()
  const [rows, setRows] = useState<WebhookRow[]>([])
  const [events, setEvents] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [eventType, setEventType] = useState('')
  const [url, setUrl] = useState('')
  const [secret, setSecret] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await api.get<{ webhooks: WebhookRow[]; available_events: string[] }>(
        '/api/integration/webhooks',
      )
      setRows(d.webhooks || [])
      setEvents(d.available_events || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

  async function handleRegister() {
    if (!eventType || !url.trim()) {
      toast.error('请选择事件类型并填写回调地址')
      return
    }
    try {
      await api.post('/api/integration/webhooks', { event_type: eventType, url: url.trim(), secret })
      toast.success('已注册')
      setAdding(false)
      setEventType('')
      setUrl('')
      setSecret('')
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '注册失败')
    }
  }

  async function handleUnregister(row: WebhookRow) {
    try {
      await api.del(`/api/integration/webhooks/${encodeURIComponent(row.event_type)}`)
      toast.success('已取消注册')
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '取消失败')
    }
  }

  const columns: TableColumnsType<WebhookRow> = [
    {
      title: '事件',
      dataIndex: 'event_type',
      width: 200,
      render: (v: string) => <span className="font-mono text-xs">{v}</span>,
    },
    { title: '回调地址', dataIndex: 'url', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'enabled',
      width: 90,
      render: (v: boolean) => <Tag tone={v ? 'green' : 'gray'}>{v ? '启用' : '停用'}</Tag>,
    },
    {
      title: '',
      key: 'ops',
      width: 70,
      render: (_: unknown, row: WebhookRow) =>
        can('integration:delete') ? (
          <Button variant="ghost" size="sm" onClick={() => void handleUnregister(row)} title="取消注册">
            <Trash2 size={14} />
          </Button>
        ) : null,
    },
  ]

  return (
    <div className="space-y-4">
      <Card
        title="已注册的 Webhook"
        action={
          can('integration:create') ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              <Plus size={14} className="mr-1" />
              注册
            </Button>
          ) : null
        }
        flush={rows.length > 0}
      >
        {loading ? (
          <div className="py-10 text-center text-sm text-ink-muted">加载中…</div>
        ) : rows.length === 0 ? (
          <EmptyState
            illustration={<Webhook size={22} className="text-ink-muted" />}
            title="还没有注册 Webhook"
            description="把练习布置、考试批改这类事件推给你的教务系统。"
          />
        ) : (
          <AntTable<WebhookRow>
            rowKey="event_type"
            columns={columns}
            dataSource={rows}
            pagination={false}
            size="small"
          />
        )}
      </Card>

      <Modal
        open={adding}
        title="注册 Webhook"
        onClose={() => setAdding(false)}
        onConfirm={() => void handleRegister()}
        confirmText="注册"
      >
        <div className="space-y-4">
          <Field label="事件类型">
            {/* 自研 Select 是原生 <select>，所以用 <option> 子元素 + 事件回调 */}
            <Select value={eventType} onChange={(e) => setEventType(e.target.value)}>
              <option value="">选择要推送的事件</option>
              {events.map((ev) => (
                <option key={ev} value={ev}>
                  {ev}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="回调地址">
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/hooks/chemai"
            />
          </Field>
          <Field label="签名密钥" hint="可选，用于校验推送来源">
            <Input value={secret} onChange={(e) => setSecret(e.target.value)} />
          </Field>
        </div>
      </Modal>
    </div>
  )
}

/**
 * LMS 集成 · API 密钥 + Webhook（阶段 5.4）。
 *
 * 入口只对 `integration` 菜单可见 —— 普通教师看不到这一页（后端 4.7 也限管理员）。
 */
export function IntegrationPage() {
  const [tab, setTab] = useState('api-keys')

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-ink">LMS 集成</h1>
        <p className="text-sm text-ink-muted mt-1">把智辅化学接到学校的教务系统 / 学习平台。</p>
      </header>

      <PlaceholderNotice />

      <Tabs
        items={[
          { key: 'api-keys', label: 'API 密钥', icon: <KeyRound size={14} /> },
          { key: 'webhooks', label: 'Webhook', icon: <Webhook size={14} /> },
        ]}
        active={tab}
        onChange={setTab}
        variant="segmented"
      />

      {tab === 'api-keys' ? <ApiKeysTab /> : <WebhooksTab />}
    </div>
  )
}
