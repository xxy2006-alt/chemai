import { Scale, FileText, FlaskConical, BookOpen, Search, Activity, type LucideIcon } from 'lucide-react'

interface Suggestion {
  icon: LucideIcon
  label: string
  prompt: string
}

const SUGGESTIONS: Suggestion[] = [
  { icon: Scale, label: '配平方程式', prompt: '请帮我配平化学方程式：' },
  { icon: FileText, label: '出题练习', prompt: '请出几道关于' },
  { icon: FlaskConical, label: '模拟实验', prompt: '请模拟' },
  { icon: BookOpen, label: '讲解概念', prompt: '请讲解' },
  { icon: Search, label: '查真题', prompt: '请搜索关于' },
  { icon: Activity, label: '错题诊断', prompt: '请分析' },
]

/** 快捷提问建议卡（带图标分组，替换旧版文本 chips） */
export function SuggestionGroup({ onPick, disabled }: { onPick: (prompt: string) => void; disabled?: boolean }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
      {SUGGESTIONS.map((s) => (
        <button
          key={s.label}
          disabled={disabled}
          onClick={() => onPick(s.prompt)}
          className="flex items-center gap-2.5 px-3.5 py-3 bg-surface border border-border rounded-[var(--radius-md)] text-left text-[13px] font-medium text-ink-secondary hover:border-teal/40 hover:text-teal hover:shadow-[var(--shadow-sm)] transition-all cursor-pointer disabled:opacity-40 disabled:pointer-events-none"
        >
          <span className="w-8 h-8 rounded-[var(--radius-sm)] bg-teal-soft text-teal flex items-center justify-center shrink-0">
            <s.icon size={16} />
          </span>
          {s.label}
        </button>
      ))}
    </div>
  )
}
