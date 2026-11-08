/* exam-utils.ts — 出题相关纯函数
 * shouldShowThumbnail：试卷题目缩略图去重——内容已包含同名配图时不再显示缩略图
 * reorganizeQuestionImages：存量 OCR 数据配图位置整理（配图被格式化到解析/解答/点评
 *   之后 → 移到题干之后；题干内原位的图保留），全站题目展示共用
 * filterExamImages：agent 找真题的题目附图（exam_images 事件）去重——
 *   正文已包含该图（同名文件）时不重复展示 */

const IMG_MD_RE = /!\[[^\]]*\]\(([^)\s]+)\)/g
const IMG_HTML_RE = /<img\b[^>]*\bsrc="([^"]+)"[^>]*\/?>/g
const SOLUTION_MARKER_RE = /【分析】|【解答】|【点评】/

/** 收集文本中的图片引用（markdown ![]() 与 <img> 两种写法），按出现顺序去重 */
export function collectImageRefs(text: string): string[] {
  const out: string[] = []
  const push = (src: string) => {
    if (src && !out.includes(src)) out.push(src)
  }
  for (const m of text.matchAll(IMG_MD_RE)) push(m[1])
  for (const m of text.matchAll(IMG_HTML_RE)) push(m[1])
  return out
}

/** 题目内容配图位置整理：
 * 存量数据中配图常被格式化到【分析】/【解答】/【点评】之后（题目底部），
 * 或嵌在解析文字中间。规则：
 *  - 题干（首个【分析】/【解答】/【点评】之前）内的图片原位保留；
 *  - 解析部分中的图片提取、去重后移到题干之后；
 *  - 解析部分的图片引用移除。
 * 幂等：二次调用时图片已在题干内，解析部分无图 → 不变。 */
export function reorganizeQuestionImages(content: string | null | undefined): string {
  const text = content ?? ''
  if (!text.includes('![') && !/<img\b/i.test(text)) return text
  const m = text.search(SOLUTION_MARKER_RE)
  if (m < 0) return text
  const stem = text.slice(0, m)
  const solution = text.slice(m)
  const moved = collectImageRefs(solution)
  if (!moved.length) return text
  const cleanSolution = solution.replace(IMG_MD_RE, '').replace(IMG_HTML_RE, '')
  return `${stem}\n${moved.map((src) => `![配图](${src})`).join('\n')}\n${cleanSolution}`
}

export function shouldShowThumbnail(content: string | undefined, pageImage: string | undefined): boolean {
  return Boolean(pageImage && !(content || '').includes(pageImage))
}

export interface ExamImageEntry {
  q_index?: number
  title?: string
  urls?: string[]
}

/** 过滤已在正文出现的题目附图：URL 的文件名（basename）出现在正文里，
 * 说明该图已在题目内容内联展示，附图列表不再重复显示 */
export function filterExamImages(
  text: string | undefined,
  images: unknown[] | undefined,
): ExamImageEntry[] {
  if (!images || !images.length) return []
  const body = text ?? ''
  return images.filter((img): img is ExamImageEntry => {
    if (!img || typeof img !== 'object') return false
    const entry = img as ExamImageEntry
    const urls = Array.isArray(entry.urls) ? entry.urls : []
    return !urls.some((u) => {
      const base = String(u ?? '').split('/').pop()
      return base ? body.includes(base) : false
    })
  })
}
