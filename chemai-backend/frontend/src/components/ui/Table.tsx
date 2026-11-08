import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react'

export interface Column<T> {
  key: string
  title: ReactNode
  /** 单元格渲染 */
  render?: (row: T, index: number) => ReactNode
  /** 直接取 row 字段 */
  dataIndex?: keyof T & string
  width?: string
  align?: 'left' | 'center' | 'right'
  thProps?: ThHTMLAttributes<HTMLTableCellElement>
  tdProps?: TdHTMLAttributes<HTMLTableCellElement>
}

export interface TableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T, index: number) => string
  loading?: boolean
  /** 空状态内容（默认简单文案） */
  empty?: ReactNode
  onRowClick?: (row: T) => void
  className?: string
}

function cellContent<T>(col: Column<T>, row: T, index: number): ReactNode {
  if (col.render) return col.render(row, index)
  if (col.dataIndex !== undefined) return String(row[col.dataIndex] ?? '')
  return null
}

export function Table<T>({
  columns,
  rows,
  rowKey,
  loading,
  empty,
  onRowClick,
  className = '',
}: TableProps<T>) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className="text-left text-xs font-medium text-ink-muted px-4 py-3 border-b border-border whitespace-nowrap"
                style={{ width: col.width, textAlign: col.align }}
                {...col.thProps}
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8">
                <div className="space-y-2">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="h-10 rounded-[var(--radius-sm)] bg-surface-muted animate-pulse"
                    />
                  ))}
                </div>
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-10">
                {empty ?? (
                  <div className="text-center text-sm text-ink-muted">暂无数据</div>
                )}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr
                key={rowKey(row, i)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`border-b border-border last:border-b-0 transition-colors ${
                  onRowClick ? 'cursor-pointer hover:bg-surface-muted/60' : 'hover:bg-surface-muted/40'
                }`}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className="px-4 py-3 text-sm text-ink"
                    style={{ textAlign: col.align }}
                    {...col.tdProps}
                  >
                    {cellContent(col, row, i)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
