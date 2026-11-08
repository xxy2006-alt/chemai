/* modal.test.tsx — Modal 布局回归测试（evals）
 * 用户反馈"弹窗要在页面顶端、填充满容器"后固化：
 * wide 弹窗置顶（items-start）+ 撑满（max-w-[1120px]、max-h 视口）；
 * 普通弹窗保持居中。
 * 2026-08 追加：
 * ① z-[1100] 必须高于 antd 弹层（Drawer/Modal 默认 z-1000）；
 * ② createPortal 到 body —— 脱离页面根 stacking context（animate-fade-in-up
 *    的动画 transform 会把弹窗锁在页面子树内，压不过 portal 的 antd Drawer；
 *    实测 elementFromPoint 命中 drawer-mask）。 */

import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { Modal } from '../src/components/ui'

function dialog() {
  return document.body.querySelector('[role="dialog"]')
}

describe('Modal 布局（置顶 + 撑满容器 + portal 层级）', () => {
  it('wide 弹窗：置顶 + 大宽度 + 视口高度内，且渲染在 body（portal）', () => {
    render(
      <Modal open title="试卷题目" onClose={() => {}} wide hideFooter>
        <div>内容</div>
      </Modal>,
    )
    const overlay = dialog()
    expect(overlay).not.toBeNull()
    // portal：直接挂在 body 下（脱离页面根 stacking context）
    expect(overlay!.parentElement).toBe(document.body)
    expect(overlay!.className).toContain('items-start')
    const panel = overlay!.querySelector('.bg-surface')
    expect(panel!.className).toContain('max-w-[1120px]')
    expect(panel!.className).toContain('max-h-[calc(100vh-2.5rem)]')
  })

  it('普通弹窗：居中 + 标准宽度', () => {
    render(
      <Modal open title="确认" onClose={() => {}} hideFooter>
        <div>内容</div>
      </Modal>,
    )
    const overlay = dialog()
    expect(overlay!.className).toContain('items-center')
    const panel = overlay!.querySelector('.bg-surface')
    expect(panel!.className).toContain('max-w-md')
  })

  it('关闭后不渲染', () => {
    render(
      <Modal open={false} title="x" onClose={() => {}} hideFooter>
        <div>内容</div>
      </Modal>,
    )
    expect(dialog()).toBeNull()
  })

  it('z 层级高于 antd 弹层（Drawer/Modal 默认 z-1000），不被抽屉盖住', () => {
    render(
      <Modal open title="历史计划" onClose={() => {}} hideFooter>
        <div>内容</div>
      </Modal>,
    )
    const overlay = dialog()
    expect(overlay!.className).toContain('z-[1100]')
  })

  it('top 顶部对齐：内容较长时贴顶显示（避免需要滚动才看到全貌）', () => {
    render(
      <Modal open title="历史学习计划" onClose={() => {}} top hideFooter>
        <div>内容</div>
      </Modal>,
    )
    const overlay = dialog()
    expect(overlay!.className).toContain('items-start')
    expect(overlay!.className).toContain('pt-5')
  })
})
