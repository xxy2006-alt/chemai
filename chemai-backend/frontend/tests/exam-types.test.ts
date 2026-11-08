/* exam-types.test.ts — 出题题型清单回归测试（evals）
 * 用户反馈"题型选项被吃掉"（单选/多选/填空/计算缺失）后固化：
 * 主工作台与内联面板共用的题型清单必须完整包含 6 种题型。 */

import { describe, expect, it } from 'vitest'
import { EXAM_TYPE_CHIPS, EXAM_TYPE_LABELS } from '../src/lib/exam-types'
import { shouldShowThumbnail } from '../src/lib/exam-utils'

describe('题型清单（防"题型被吃掉"回归）', () => {
  it('必须包含 单选/多选/填空/计算/实验/推断 六种', () => {
    const labels = EXAM_TYPE_CHIPS.map((t) => t.label)
    expect(labels).toEqual(['单选', '多选', '填空', '计算', '实验', '推断'])
  })

  it('multiple_choice 题型存在且数量可调', () => {
    const multi = EXAM_TYPE_CHIPS.find((t) => t.val === 'multiple_choice')
    expect(multi).toBeDefined()
    expect(multi?.qty).toBeGreaterThan(0)
    expect(EXAM_TYPE_LABELS.multiple_choice).toBe('多选')
  })

  it('标签映射完整（single_choice/multiple_choice/fill_blank/calculation/experiment/inference）', () => {
    expect(EXAM_TYPE_LABELS).toEqual(
      expect.objectContaining({
        single_choice: '单选',
        multiple_choice: '多选',
        fill_blank: '填空',
        calculation: '计算',
        experiment: '实验',
        inference: '推断',
      }),
    )
  })
})

describe('shouldShowThumbnail（题目配图缩略图去重）', () => {
  it('内容已包含同名配图 → 不显示缩略图', () => {
    const content = '铑的配合物离子![](/static/figures/全国卷/2020/figures/ed9966.jpg)可催化'
    expect(shouldShowThumbnail(content, 'ed9966.jpg')).toBe(false)
  })

  it('内容不含该配图 → 显示缩略图', () => {
    expect(shouldShowThumbnail('无图内容', 'page_02.png')).toBe(true)
  })

  it('pageImage 为空 → 不显示', () => {
    expect(shouldShowThumbnail('内容', undefined)).toBe(false)
    expect(shouldShowThumbnail('内容', '')).toBe(false)
  })
})
