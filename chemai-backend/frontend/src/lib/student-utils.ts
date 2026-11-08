/* student-utils.ts — 学生列表相关纯函数
 * sortStudentsForDisplay：演示学生置顶 + 练习数降序。
 * 2026-08-14 用户反馈「李世睿（202610201）直接没了」：学生管理分页 12 人/页时
 * 她在第 3 页首屏不可见。演示数据（202610201 李世睿，长期演示用）固定置顶。 */

export interface StudentLike {
  student_id?: string
  id?: string
  name?: string
  exercises_completed?: number
}

export const DEMO_STUDENT_ID = '202610201'

export function studentKey(s: StudentLike): string {
  return s.student_id || s.id || ''
}

export function sortStudentsForDisplay<T extends StudentLike>(students: T[]): T[] {
  return [...students].sort((a, b) => {
    const aDemo = studentKey(a) === DEMO_STUDENT_ID ? 1 : 0
    const bDemo = studentKey(b) === DEMO_STUDENT_ID ? 1 : 0
    if (aDemo !== bDemo) return bDemo - aDemo
    return (b.exercises_completed || 0) - (a.exercises_completed || 0)
  })
}
