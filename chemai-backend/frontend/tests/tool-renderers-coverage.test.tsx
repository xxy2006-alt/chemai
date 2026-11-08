/* tool-renderers-coverage.test.tsx — 补齐渲染器冒烟（S1 标准）
 * 每个渲染器至少一条代表性数据断言可读内容（非裸 JSON）。 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  BankSaveResult, BankListResult, BankDeleteResult,
  MemoryStudentResult, MemoryTeacherResult,
  SendPlanResult, ParentReportResult, SendReportResult,
  OcrProgressResult, GradeSheetsResult, SaveGradesResult,
  BatchGradesResult, TeacherExamsResult,
  ParseDocResult, ImportBankResult, ParserServicesResult,
  BrowseNavigateResult, BrowseReadResult, BrowseClickResult,
  BrowseInputResult, BrowseScreenshotResult,
} from '../src/components/chat/tool-renderers'

describe('补齐渲染器冒烟（S1）', () => {
  it('save_to_bank → 保存确认文案', () => {
    render(<BankSaveResult data={{ saved: true, set_name: '期中卷', count: 5 }} />)
    expect(screen.getByText(/已保存 5 题到题库「期中卷」/)).toBeInTheDocument()
  })
  it('list_banks → 题库列表', () => {
    render(<BankListResult data={{ banks: [{ name: '期中卷', question_count: 5, created_at: '2026-08' }] }} />)
    expect(screen.getByText('期中卷')).toBeInTheDocument()
    expect(screen.getByText('5 题')).toBeInTheDocument()
  })
  it('delete_bank → 删除确认', () => {
    render(<BankDeleteResult data={{ deleted: true, name: '旧卷' }} />)
    expect(screen.getByText(/已删除：旧卷/)).toBeInTheDocument()
  })
  it('memory_student_get → 诊断记录数', () => {
    render(<MemoryStudentResult data={{ student_id: '202610101', diagnoses: [{ key: 'diagnosis-1' }] }} />)
    expect(screen.getByText('1')).toBeInTheDocument()
  })
  it('memory_teacher_get → 键值可读', () => {
    render(<MemoryTeacherResult data={{ 常教年级: '高一' }} />)
    expect(screen.getByText('常教年级:')).toBeInTheDocument()
    expect(screen.getByText('高一')).toBeInTheDocument()
  })
  it('send_learning_plan → 发送确认', () => {
    render(<SendPlanResult data={{ result: 'success', student_name: '张浩宇' }} />)
    expect(screen.getByText(/已发送学习计划给 张浩宇/)).toBeInTheDocument()
  })
  it('generate_parent_report → 报告预览', () => {
    render(<ParentReportResult data={{ student_name: '张浩宇', preview: '家长报告预览内容' }} />)
    expect(screen.getByText('家长报告预览内容')).toBeInTheDocument()
  })
  it('send_report_to_parent → 发送确认', () => {
    render(<SendReportResult data={{ result: 'success', parent_name: '张父', student_name: '张浩宇' }} />)
    expect(screen.getByText(/已发送报告给家长 张父/)).toBeInTheDocument()
  })
  it('query_ocr_progress → 进度摘要与批次进度', () => {
    render(
      <OcrProgressResult
        data={{ summary: '3/5 完成', all_done: false, batches: { b1: { total: 5, done: 3 } } }}
      />
    )
    expect(screen.getByText('3/5 完成')).toBeInTheDocument()
    expect(screen.getByText('3/5')).toBeInTheDocument()
  })
  it('grade_answer_sheets → 成绩表', () => {
    render(<GradeSheetsResult data={{ results: [{ student_name: '张浩宇', score: 88, total: 100 }] }} />)
    expect(screen.getByText('88 / 100')).toBeInTheDocument()
  })
  it('save_grading_results → 统计数字', () => {
    render(<SaveGradesResult data={{ saved_count: 42, total: 42, message: '全部保存' }} />)
    expect(screen.getAllByText('42')).toHaveLength(2)
    expect(screen.getByText('全部保存')).toBeInTheDocument()
  })
  it('query_batch_grades → 结果列表', () => {
    render(<BatchGradesResult data={{ message: '成绩如下', results: [{ student_name: '张浩宇', score: 90 }] }} />)
    expect(screen.getByText('90')).toBeInTheDocument()
  })
  it('list_teacher_exams → 班级分组考试', () => {
    render(<TeacherExamsResult data={{ total: 1, classes: [{ class_name: '2419班', exams: [{ name: '期中化学' }] }] }} />)
    expect(screen.getByText('2419班')).toBeInTheDocument()
    expect(screen.getByText('期中化学')).toBeInTheDocument()
  })
  it('parse_chemistry_document → provider 与题数', () => {
    render(<ParseDocResult data={{ success: true, provider: 'mineru', result: { questions: [{}, {}, {}] } }} />)
    expect(screen.getByText('mineru')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })
  it('import_question_bank → 待确认题数', () => {
    render(<ImportBankResult data={{ provider: 'mineru', source_name: '全国卷', question_count: 12 }} />)
    expect(screen.getByText('12')).toBeInTheDocument()
  })
  it('check_parser_services → 三行服务状态（对象形状）', () => {
    render(
      <ParserServicesResult
        data={{
          ocr: { available: true, provider: 'baidu' },
          mineru: { available: true, note: '' },
          vision: { available: false, note: '未配置' },
        }}
      />
    )
    expect(screen.getAllByText('✅ 正常')).toHaveLength(2)
    expect(screen.getByText('❌ 不可用')).toBeInTheDocument()
  })
  it('browse_navigate → 标题与文本', () => {
    render(<BrowseNavigateResult data={{ title: '百度', url: 'https://example.com', text: '页面内容' }} />)
    expect(screen.getByText('百度')).toBeInTheDocument()
  })
  it('browse_read → selector 与文本', () => {
    render(<BrowseReadResult data={{ selector: '#main', text: '正文' }} />)
    expect(screen.getByText(/selector: #main/)).toBeInTheDocument()
  })
  it('browse_click → 点击确认', () => {
    render(<BrowseClickResult data={{ clicked: true, title: '新页面' }} />)
    expect(screen.getByText('新页面')).toBeInTheDocument()
  })
  it('browse_input → 输入文本', () => {
    render(<BrowseInputResult data={{ text: '化学' }} />)
    expect(screen.getByText(/已输入：化学/)).toBeInTheDocument()
  })
  it('browse_screenshot → 图片渲染', () => {
    render(<BrowseScreenshotResult data={{ screenshot: 'data:image/png;base64,AAAA' }} />)
    expect(screen.getByAltText('页面截图')).toBeInTheDocument()
  })
})
