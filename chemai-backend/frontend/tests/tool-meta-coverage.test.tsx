/* tool-meta-coverage.test.tsx — 48 工具 meta 全覆盖（S1 验收钉住）
 * 工具清单与后端 agent/tools/__init__.py TOOLS + browser_tools + request_approval 对齐。 */
import { describe, expect, it } from 'vitest'
import { TOOL_META } from '../src/components/chat/ToolCard'

const ALL_TOOLS = [
  // 核心 42
  'search_exam_bank', 'web_search', 'show_exam_workbench', 'show_diagnosis', 'show_students',
  'diagnose_barrier', 'chemistry_tutor', 'simulate_experiment', 'balance_equation',
  'query_ocr_progress', 'grade_answer_sheets', 'save_grading_results', 'query_batch_grades',
  'list_teacher_exams', 'ionic_equation_tutor', 'stoichiometry_tutor', 'redox_tutor',
  'equilibrium_tutor', 'periodic_law_tutor', 'organic_tutor', 'weekly_report',
  'assign_adaptive_practice', 'save_to_bank', 'list_banks', 'delete_bank', 'generate_questions',
  'memory_student_get', 'memory_teacher_get', 'generate_learning_plan', 'send_learning_plan',
  'generate_parent_report', 'send_report_to_parent', 'parse_chemistry_document',
  'import_question_bank', 'check_parser_services', 'read', 'write', 'edit', 'find', 'grep',
  'bash', 'plan_task',
  // 浏览器 5 + 审批 1
  'browse_navigate', 'browse_read', 'browse_click', 'browse_input', 'browse_screenshot',
  'request_approval',
]

describe('工具卡 meta 覆盖（S1）', () => {
  it('48 个工具全部有 meta（图标 + 中文动作说明）', () => {
    for (const tool of ALL_TOOLS) {
      const meta = TOOL_META[tool]
      expect(meta, `missing meta for ${tool}`).toBeDefined()
      expect(meta.label, `missing label for ${tool}`).toBeTruthy()
      expect(meta.icon, `missing icon for ${tool}`).toBeTruthy()
    }
  })

  it('所有 meta 的中文标签非空且不包含裸英文工具名', () => {
    for (const [tool, meta] of Object.entries(TOOL_META)) {
      expect(meta.label.trim().length).toBeGreaterThan(0)
      expect(meta.label).not.toBe(tool)
    }
  })
})
