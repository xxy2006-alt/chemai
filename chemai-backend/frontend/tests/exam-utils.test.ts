/* exam-utils.test.ts — 题目配图位置整理 / 附图去重（evals）
 * 回归的用户反馈：
 *  - 「图片放在题目的位置有问题，图片应该在答案和题目内容的中间或者它该出现的位置」
 *  - 「agent 找出来的真题有些真题不显示图片」 */

import { describe, expect, it } from 'vitest'
import {
  collectImageRefs,
  filterExamImages,
  reorganizeQuestionImages,
  shouldShowThumbnail,
} from '../src/lib/exam-utils'

const FIG = '/static/figures/全国卷/2020/figures/633625dfe5370c0abe9543cb785143ecf0a61e149e01701d1c13bc5f328ecabf.jpg'

describe('collectImageRefs：收集 markdown 与 <img> 两种图片引用，去重保序', () => {
  it('markdown ![]() 与 <img> 均收集', () => {
    const out = collectImageRefs(`题干\n![图](${FIG})\n<img src="/static/question_images/abc.png">`)
    expect(out).toEqual([FIG, '/static/question_images/abc.png'])
  })

  it('相同图片只出现一次（保留首次位置）', () => {
    const out = collectImageRefs(`![a](${FIG})\n![b](${FIG})`)
    expect(out).toEqual([FIG])
  })

  it('无图片返回空数组', () => {
    expect(collectImageRefs('纯文本')).toEqual([])
  })
})

describe('reorganizeQuestionImages：配图移到题干之后（答案/解析之前）', () => {
  it('回归①：图片在【点评】之后（题目底部）→ 移到题干之后', () => {
    const content = `下列叙述正确的是（　　）\n【分析】略\n【解答】解：略\n【点评】难度不大。\n\n![配图](${FIG})`
    const out = reorganizeQuestionImages(content)
    // 图片必须出现在【分析】之前（即题干之后）
    expect(out.indexOf(FIG)).toBeGreaterThan(-1)
    expect(out.indexOf(FIG)).toBeLessThan(out.indexOf('【分析】'))
    // 原文的底部图片引用被移除（不重复）
    expect(out.endsWith(`![配图](${FIG})`)).toBe(false)
    // 题干与解析文本都保留
    expect(out).toContain('下列叙述正确的是')
    expect(out).toContain('【解答】解：略')
  })

  it('题干内原位的图片不动（真题 T6：图紧跟「如图」之后）', () => {
    const content = `电池示意图如图：\n\n![图](${FIG})\n\n下列叙述错误的是（　　）\n【分析】略`
    const out = reorganizeQuestionImages(content)
    // 图片仍在题干内原位置（【分析】之前），且不重复
    expect(out).toContain(`![图](${FIG})`)
    expect(out.indexOf('![图]')).toBeLessThan(out.indexOf('下列叙述错误的是'))
    expect(out.match(/633625dfe537/g)).toHaveLength(1)
  })

  it('回归②：解析部分多张图（含重复）→ 去重后移到题干后（真题 T4 反应机理）', () => {
    const a = `${FIG}`
    const b = '/static/figures/全国卷/2020/figures/90d68f3bd4af1c7d88fabf88e42251c8dbdc2efa0c4b693fe3e9d90171daf5ea.jpg'
    const content = `反应过程如图所示。下列叙述错误的是（　　）\n【分析】A、由图可知：\n\n![图A](${a})\n\ncoB、由图可知：\n\n![图B](${b})\n\n【解答】解：略\n\n![图A](${a})`
    const out = reorganizeQuestionImages(content)
    // 两张不同图各出现一次
    expect(out.match(/633625dfe537/g)).toHaveLength(1)
    expect(out.match(/90d68f3bd4af/g)).toHaveLength(1)
    // 都在【分析】之前
    expect(out.indexOf(a)).toBeLessThan(out.indexOf('【分析】'))
    expect(out.indexOf(b)).toBeLessThan(out.indexOf('【分析】'))
    // 解析部分不再含图片
    const solution = out.slice(out.indexOf('【分析】'))
    expect(solution.includes('![')).toBe(false)
  })

  it('无【分析】/【解答】/【点评】标记 → 原样返回', () => {
    const content = `纯题干 ![图](${FIG})`
    expect(reorganizeQuestionImages(content)).toBe(content)
  })

  it('无图片 → 原样返回', () => {
    const content = `题干\n【分析】略`
    expect(reorganizeQuestionImages(content)).toBe(content)
  })

  it('幂等：整理后再整理结果不变', () => {
    const content = `题干\n【分析】略\n![图](${FIG})`
    const once = reorganizeQuestionImages(content)
    expect(reorganizeQuestionImages(once)).toBe(once)
  })

  it('空值安全', () => {
    expect(reorganizeQuestionImages(null)).toBe('')
    expect(reorganizeQuestionImages(undefined)).toBe('')
  })
})

describe('filterExamImages：正文已展示的附图不重复显示', () => {
  it('正文含同名文件（basename）→ 过滤掉', () => {
    const text = `> 题目内容 ![配图](/static/figures/全国卷/2020/figures/hash123.jpg)`
    const images = [
      { q_index: 0, title: '第1题 · 题目附图', urls: ['/static/figures/01_全国卷/2020/figures/hash123.jpg'] },
      { q_index: 1, title: '第2题 · 题目附图', urls: ['/static/figures/01_全国卷/2020/figures/page_02.png'] },
    ]
    const out = filterExamImages(text, images)
    expect(out).toHaveLength(1)
    expect(out[0].q_index).toBe(1)
  })

  it('正文无该图 → 全部保留（真题不丢图）', () => {
    const images = [{ q_index: 0, title: '第1题 · 题目附图', urls: ['/static/figures/01_全国卷/2020/figures/page_02.png'] }]
    expect(filterExamImages('只有文字', images)).toHaveLength(1)
  })

  it('无 images / 空数组 → 空结果', () => {
    expect(filterExamImages('x', undefined)).toEqual([])
    expect(filterExamImages('x', [])).toEqual([])
  })

  it('非对象条目被忽略', () => {
    expect(filterExamImages('x', ['junk', null, 42])).toEqual([])
  })
})

describe('shouldShowThumbnail：内容已含同名配图时不显示缩略图（防重复展示）', () => {
  it('内容包含 page_image → false', () => {
    expect(shouldShowThumbnail(`题干 ![x](/static/figures/全国卷/2020/figures/${FIG.split('/').pop()})`, FIG.split('/').pop())).toBe(false)
  })

  it('内容不含 page_image → true', () => {
    expect(shouldShowThumbnail('题干无图', 'page_02.png')).toBe(true)
  })
})
