import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { Button } from './Button'

export interface ModalProps {
  open: boolean
  title?: ReactNode
  onClose: () => void
  onConfirm?: () => void
  confirmText?: string
  cancelText?: string
  /** 危险操作确认（红色确认按钮） */
  danger?: boolean
  /** 大内容可滚动 */
  wide?: boolean
  /** 顶部对齐（内容较长时避免居中被裁/需要滚动才看到全貌） */
  top?: boolean
  children: ReactNode
  /** 隐藏底部按钮区 */
  hideFooter?: boolean
}

export function Modal({
  open,
  title,
  onClose,
  onConfirm,
  confirmText = '确认',
  cancelText = '取消',
  danger,
  wide,
  top,
  children,
  hideFooter,
}: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  /* createPortal 到 body：脱离页面根（animate-fade-in-up 动画 transform 会创建
   * stacking context），否则弹窗 z-index 只在页面子树内生效，压不过 portal 到
   * body 的 antd Drawer/Modal（2026-08 实测：elementFromPoint 命中 drawer-mask）。 */
  return createPortal(
    <div
      /* z-[1100]：必须盖过 antd 弹层（Drawer/Modal 默认 z-1000）。 */
      className={`fixed inset-0 z-[1100] flex p-4 ${
        wide || top ? 'items-start justify-center pt-5' : 'items-center justify-center'
      }`}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="absolute inset-0 bg-ink/50 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        className={`relative bg-surface rounded-[var(--radius-lg)] shadow-[var(--shadow-lg)] w-full flex flex-col animate-fade-in-up ${
          wide
            ? 'max-w-[1120px] max-h-[calc(100vh-2.5rem)]'
            : 'max-w-md max-h-[85vh]'
        }`}
      >
        {title !== undefined && (
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <h3 className="text-[15px] font-semibold text-ink m-0">{title}</h3>
            <button
              className="p-1 rounded-[var(--radius-sm)] text-ink-muted hover:bg-surface-muted hover:text-ink-secondary cursor-pointer transition-colors"
              onClick={onClose}
              aria-label="关闭"
            >
              <X size={18} />
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {!hideFooter && (
          <div className="flex justify-end gap-2 px-5 py-3.5 border-t border-border">
            <Button variant="secondary" onClick={onClose}>
              {cancelText}
            </Button>
            {onConfirm && (
              <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>
                {confirmText}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
