/* exam-types.ts — 出题题型清单（唯一事实来源）
 * 2026 用户反馈"题型选项被吃掉"后固化：主工作台与内联面板共用，
 * 任何一处改动题型都必须同步此文件（evals: tests/exam-types.test.ts） */

export interface ExamTypeChip {
  val: string
  label: string
  active: boolean
  qty: number
}

export const EXAM_TYPE_CHIPS: ExamTypeChip[] = [
  { val: 'single_choice', label: '单选', active: true, qty: 3 },
  { val: 'multiple_choice', label: '多选', active: false, qty: 2 },
  { val: 'fill_blank', label: '填空', active: false, qty: 2 },
  { val: 'calculation', label: '计算', active: false, qty: 1 },
  { val: 'experiment', label: '实验', active: false, qty: 1 },
  { val: 'inference', label: '推断', active: false, qty: 1 },
]

export const EXAM_TYPE_LABELS: Record<string, string> = {
  single_choice: '单选',
  multiple_choice: '多选',
  fill_blank: '填空',
  calculation: '计算',
  experiment: '实验',
  inference: '推断',
  choice: '单选',
}
