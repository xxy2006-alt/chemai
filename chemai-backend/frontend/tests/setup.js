// Vitest setup — 把 katex（含 mhchem \ce）挂到全局，供 chem-markdown.js 等 IIFE 加载时使用
import katex from 'katex'
import 'katex/contrib/mhchem'
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

globalThis.katex = katex

// antd 组件在 jsdom 下需要的浏览器 API polyfill（2026-08 antd 接入后新增）
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = function matchMedia(query) {
    return {
      matches: false,
      media: query,
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent() {
        return false
      },
    }
  }
}

if (typeof window !== 'undefined' && !window.ResizeObserver) {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  window.ResizeObserver = ResizeObserverMock
  globalThis.ResizeObserver = ResizeObserverMock
}

// antd message / modal / notification 会创建临时挂载节点，测试间清理
afterEach(() => {
  document.body
    .querySelectorAll('.ant-message, .ant-modal-wrap, .ant-notification, .ant-drawer')
    .forEach((el) => el.remove())
})
