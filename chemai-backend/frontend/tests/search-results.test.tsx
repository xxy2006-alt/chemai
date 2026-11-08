/* search-results.test.tsx — agent 找真题结果卡片渲染（evals）
 * 回归用户反馈：「agent 找出来的真题有些真题不显示图片」——
 * 后端 search_exam_bank 的题目附图（exam_images）必须展示，
 * 且正文已内联的图不得重复显示。 */

import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { SearchResults } from '../src/components/chat/tool-renderers'

const PAGE_IMG = '/static/figures/01_全国卷/2020/figures/page_02.png'

describe('SearchResults：题目附图展示 + 去重', () => {
  it('正文没有的附图（page_image）→ 渲染为图片（真题不丢图）', () => {
    const { container } = render(
      <SearchResults
        data={{
          text: '**第1题** 🏫 本地题库 · 2020 全国卷 第T2题\n> 紫花前胡醇…',
          images: [{ q_index: 0, title: '第1题 · 题目附图', urls: [PAGE_IMG] }],
        }}
      />
    )
    const imgs = container.querySelectorAll('img')
    expect(imgs.length).toBe(1)
    expect(imgs[0].getAttribute('src')).toBe(PAGE_IMG)
    expect(container.textContent).toContain('第1题 · 题目附图')
  })

  it('正文已内联的图 → 附图列表不重复显示', () => {
    const hash = '633625dfe5370c0abe9543cb785143ecf0a61e149e01701d1c13bc5f328ecabf.jpg'
    const { container } = render(
      <SearchResults
        data={{
          text: `> 题目内容 ![配图](/static/figures/全国卷/2020/figures/${hash})`,
          images: [
            { q_index: 0, title: '第1题 · 题目附图', urls: [`/static/figures/01_全国卷/2020/figures/${hash}`] },
            { q_index: 1, title: '第2题 · 题目附图', urls: [PAGE_IMG] },
          ],
        }}
      />
    )
    // 仅第 2 题的附图展示（第 1 题正文已有）
    const imgs = container.querySelectorAll('img')
    expect(imgs.length).toBe(1)
    expect(imgs[0].getAttribute('src')).toBe(PAGE_IMG)
  })

  it('有结构化 questions 时照常展示题目与答案', () => {
    const { container } = render(
      <SearchResults
        data={{
          total: 3,
          questions: [{ source: '全国卷', year: '2020', content: '下列叙述正确的是（　　）', answer: 'B' }],
        }}
      />
    )
    expect(container.textContent).toContain('找到 3 道真题')
    expect(container.textContent).toContain('全国卷 · 2020')
    // AnswerMd：答案标签 + 内容（公式走 KaTeX 渲染）
    expect(container.textContent).toContain('答案B')
  })

  it('无题目也无附图 → 提示暂无匹配', () => {
    const { container } = render(<SearchResults data={{ raw: '未找到' }} />)
    expect(container.textContent).toContain('暂无匹配结果')
  })
})
