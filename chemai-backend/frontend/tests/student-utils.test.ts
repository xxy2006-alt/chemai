/* student-utils.test.ts — 学生列表排序（evals）
 * 回归用户反馈：「李世睿（202610201）直接没了」——演示学生必须置顶可见 */
import { describe, expect, it } from 'vitest'
import { DEMO_STUDENT_ID, sortStudentsForDisplay } from '../src/lib/student-utils'

describe('sortStudentsForDisplay：演示学生置顶', () => {
  it('202610201（李世睿）排在第一，即使练习数不是最多', () => {
    const out = sortStudentsForDisplay([
      { student_id: '202610101', name: '张浩宇', exercises_completed: 99 },
      { student_id: DEMO_STUDENT_ID, name: '李世睿', exercises_completed: 50 },
      { student_id: '202610102', name: '王佳怡', exercises_completed: 60 },
    ])
    expect(out[0].student_id).toBe(DEMO_STUDENT_ID)
  })

  it('其余按练习数降序', () => {
    const out = sortStudentsForDisplay([
      { student_id: 'A', exercises_completed: 5 },
      { student_id: DEMO_STUDENT_ID, exercises_completed: 1 },
      { student_id: 'B', exercises_completed: 9 },
      { student_id: 'C' },
    ])
    const rest = out.filter((s) => s.student_id !== DEMO_STUDENT_ID)
    expect(rest.map((s) => s.student_id)).toEqual(['B', 'A', 'C'])
  })

  it('原数组不被修改', () => {
    const input = [{ student_id: 'B' }, { student_id: DEMO_STUDENT_ID }]
    sortStudentsForDisplay(input)
    expect(input[0].student_id).toBe('B')
  })

  it('无演示学生时按练习数降序', () => {
    const out = sortStudentsForDisplay([
      { student_id: 'X', exercises_completed: 2 },
      { student_id: 'Y', exercises_completed: 7 },
    ])
    expect(out[0].student_id).toBe('Y')
  })
})
