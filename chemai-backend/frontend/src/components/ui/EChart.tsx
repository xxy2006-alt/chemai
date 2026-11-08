import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

export interface EChartProps {
  option: echarts.EChartsCoreOption
  height?: number
  className?: string
}

/** ECharts 封装：按需引入（charts/components/renderers）+ 自适应容器尺寸 */
export function EChart({ option, height = 280, className = '' }: EChartProps) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    chartRef.current = chart
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option as echarts.EChartsCoreOption, { notMerge: true })
  }, [option])

  return <div ref={ref} className={className} style={{ height, width: '100%' }} />
}

/* 方向 A 图表色板（与 tokens 一致） */
export const CHART_COLORS = {
  primary: '#002147',
  teal: '#0d7377',
  success: '#2c6e49',
  warning: '#b45309',
  error: '#b43c28',
  muted: '#94a3b8',
  bar: ['#002147', '#0d7377', '#2c6e49', '#b45309', '#b43c28', '#64748b'],
  doughnut: ['#002147', '#0d7377', '#2c6e49'],
  line: '#002147',
}

export const CHART_AXIS_TEXT = { color: '#94a3b8', fontSize: 11 }
