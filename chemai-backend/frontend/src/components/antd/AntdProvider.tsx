/* AntdProvider.tsx — Ant Design v6 主题接入（2026-08 用户选型 / 2026-09 v2 升级）
 * 渐进式接入策略：全局 ConfigProvider 把 antd 组件视觉拉向 ChemAI 设计语言
 * （design/教师端.md v2 · Academic Catalyst × Linear）：
 *  - 主色 牛津蓝 #002147 / 交互微强调 薰衣草蓝 #5e6ad2（link/info）/ 语义色沿用 tokens
 *  - 圆角 8px、字体栈、背景/边框/文字色与 tokens 同源
 * DarkPanelProvider：深色 AI 嵌板专用嵌套 Provider（darkAlgorithm + Linear 深色 token），
 * 供 AI 对话工作台与登录页深色时刻使用（R-T-L1 / R-T-F1）。
 * 包 antd <App>：提供 message/notification/modal 上下文（Toast 桥接用）。
 */

import type { ReactNode } from 'react'
import { App, ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'

const FONT = "'PingFang SC','Microsoft YaHei','Noto Sans SC',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"

export function AntdProvider({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          /* 品牌色（tokens.css 同源） */
          colorPrimary: '#002147',
          colorInfo: '#5e6ad2',
          colorSuccess: '#2c6e49',
          colorWarning: '#b45309',
          colorError: '#b43c28',
          colorLink: '#5e6ad2',
          /* 表面与文字（v2 Linear 中性色） */
          colorBgLayout: '#ffffff',
          colorBgContainer: '#ffffff',
          colorBgElevated: '#ffffff',
          colorBorder: '#e5e7eb',
          colorBorderSecondary: '#f0f1f3',
          colorText: '#111318',
          colorTextSecondary: '#5b616e',
          colorTextTertiary: '#9aa0ab',
          colorTextQuaternary: '#d1d5db',
          /* 几何与字体 */
          borderRadius: 8,
          borderRadiusLG: 12,
          fontFamily: FONT,
          fontSize: 14,
          controlHeight: 34,
          boxShadowSecondary: '0 4px 12px rgb(15 23 42 / 0.08)',
        },
        components: {
          Button: { borderRadius: 8, fontWeight: 500 },
          Card: { borderRadiusLG: 12, headerBg: 'transparent' },
          Table: {
            headerBg: '#f5f6f6',
            headerColor: '#5b616e',
            headerSplitColor: 'transparent',
            borderColor: '#eceef0',
            rowHoverBg: '#f5f6f6',
          },
          Modal: { borderRadiusLG: 12 },
          Drawer: { borderRadiusLG: 12 },
          Menu: { itemBorderRadius: 8 },
          Input: { activeShadow: '0 0 0 3px rgb(94 106 210 / 0.14)' },
          Select: { activeOutlineColor: 'rgb(94 106 210 / 0.18)' },
          Tabs: { itemSelectedColor: '#002147', inkBarColor: '#002147' },
        },
      }}
    >
      <App className="h-full">{children}</App>
    </ConfigProvider>
  )
}

/* 深色 AI 嵌板 / 登录页深色时刻的嵌套主题（design/教师端.md dark_panel 区）。
   焦点/主色用嵌板焦点紫，AI 元素用 teal-bright；表面阶梯取 Linear 原值。 */
export function DarkPanelProvider({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#5e69d1',
          colorInfo: '#2dd4bf',
          colorSuccess: '#27a644',
          colorWarning: '#ffa42b',
          colorError: '#f3727f',
          colorLink: '#828fff',
          colorBgBase: '#010102',
          colorBgLayout: '#010102',
          colorBgContainer: '#0f1011',
          colorBgElevated: '#141516',
          colorBorder: '#23252a',
          colorBorderSecondary: '#1a1c20',
          colorText: '#f7f8f8',
          colorTextSecondary: '#d0d6e0',
          colorTextTertiary: '#8a8f98',
          colorTextQuaternary: '#62666d',
          borderRadius: 8,
          borderRadiusLG: 12,
          fontFamily: FONT,
          fontSize: 14,
          controlHeight: 34,
          boxShadowSecondary: '0 8px 24px rgb(0 0 0 / 0.5)',
        },
        components: {
          Button: { borderRadius: 8, fontWeight: 500, primaryColor: '#ffffff' },
          Input: { activeShadow: '0 0 0 3px rgb(94 105 209 / 0.25)' },
          Select: { activeOutlineColor: 'rgb(94 105 209 / 0.3)' },
        },
      }}
    >
      {children}
    </ConfigProvider>
  )
}
