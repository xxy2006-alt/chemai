# Session 14 · 出题工作台与化学式审核

## 产出物

- `frontend/pages/exam-v2.html` — 完整实现考试工作台 4 Tab（917 行）
- `agent/langgraph_agent.py` — exam_expert 子专家的完整工具链
- `agent/tools.py` — generate_question / save_question / create_variant 三个核心工具
- `frontend/m/app.js` — renderChem 函数（KaTeX 保护方案 v3）
- `agent/channel/langgraph_channel.py` — SSE component 事件机制
- 出题→审核→保存 完整链路可用
- 变种题浏览器 多选 + 教师审核五步流程
- 四条红线约束（系数/条件/产物/知识点不变）实现
- KaTeX 安全渲染方案（marked API 废弃的最终修复）

## 前置条件

- Session 13 完成的 Agent 架构完整可用（Gateway + Coordinator + 6 子专家 + Router + Graph 编译）
- `frontend/pages/exam-v2.html` 骨架已存在（Session 12 步骤 8 创建，4 Tab 切换已实现）
- `agent/langgraph_agent.py` 中 exam_expert 子专家节点已创建（但工具链待完善）
- SSE 流式通道 `/api/agent/chat/stream` 已能正常通信
- DeepSeek API Key 有效

## 项目背景（给学生的概述）

出题是 ChemAI 的核心功能——种子教师的第一大痛点是"AI 出题不信任"。

这位 18 年教龄的化学教师，第一次用 ChatGPT 出题就踩了坑：AI 生成的化学方程式配平错误。从此她对所有 AI 出题工具都持怀疑态度。这不是一个技术问题，是一个信任问题。

要重建信任，你不能只是"让 AI 出题"——你需要一个完整的三段式链路：AI 生成 → 教师审核 → 确认保存。教师必须是最终决策者，AI 只是辅助工具。这个设计在 ChemAI 中叫"人在回路"（Human-in-the-Loop）。

但这还不够。AI 生成的题目需要遵守"四条红线"——化学方程式必须配平、反应条件必须合理、产物必须符合热力学、知识点必须贴合教学大纲。这些约束不是写在 prompt 里的建议，是硬编码在审核逻辑中的规则。

这节课你将深入实现出题工作台的完整功能：AI 出题、变种题生成、四条红线审核、化学式 KaTeX 渲染、SSE component 事件机制。每一个功能都经历过真实用户的测试和反馈。

---

## 操作步骤

### 步骤 1：完善 exam-v2.html 的 Vue 3 数据模型

**目标**：补充 Session 6 创建的 exam-v2.html 骨架，填充完整的数据模型和 4 Tab 的业务逻辑

**提示词**（复制到 Claude Code）：

```
完善 frontend/pages/exam-v2.html 的 Vue 3 数据模型。

当前文件已有骨架（4 Tab 的 v-show 切换和 renderChem 函数），需要补充以下完整数据模型：

【Vue 3 data 定义】（在现有 data() 基础上扩展）
```javascript
data() {
  return {
    // === 核心状态 ===
    sourceMode: 'ai',      // Tab 切换：'ai' | 'bank' | 'history' | 'exam'
    loading: false,        // 全局加载状态
    errorMsg: '',           // 错误提示（不显示 HTTP 状态码）

    // === 出题工作台（sourceMode='ai'） ===
    aiForm: {
      topic: '',           // 知识点（如"氧化还原反应"）
      type: 'choice',      // 题型：choice/fill/judge/short
      difficulty: 3,       // 难度：1-5
      count: 5,            // 出题数量
    },
    generatedQuestions: [],   // AI 生成的题目列表
    savedStatus: {},          // 每题的保存状态 {qIndex: 'saved'|'saving'|null}
    showManualForm: false,    // 手动录入表单开关
    manualForm: {
      type: 'choice', content: '', answer: '',
      analysis: '', topic: '', difficulty: 3,
    },

    // === 题库管理（sourceMode='bank'） ===
    bankQuestions: [],        // 题库列表
    bankPage: 1,              // 分页
    bankTotal: 0,
    bankFilter: { type: '', topic: '', difficulty: '' },

    // === 历史真题库（sourceMode='history'） ===
    historyQuestions: [],
    historyYear: '2024',
    historyRegion: 'hunan',
    selectedHistoryIds: [],   // 多选加入考试的题目 ID

    // === 考试列表（sourceMode='exam'） ===
    exams: [],
    selectedExam: null,       // 当前管理的考试
    examQuestions: [],        // 考试中的题目

    // === Modal 通用对话框 ===
    modal: {
      show: false, fading: false,
      title: '', message: '', type: 'confirm',
      _manageTab: 'paper',       // 考试管理的子 Tab
      _vbStep: 'dir',            // 变种题浏览器的步骤
      _vbPapers: [],             // 变种题浏览器的试卷列表
      _vbQuestions: [],          // 变种题浏览器的题目列表
      previewLoading: false,
      previewQuestions: null,    // 考试预览题目
    },
  }
}
```

【为什么要这样设计数据模型】
- `sourceMode` 用单个变量而非 Vue Router：4 个 Tab 数据一次性加载，不需要懒加载
- `savedStatus` 用字典而非数组：索引是题目在生成列表中的位置，支持逐题保存
- `_vbStep` 用字符串而非数字：代码可读性（'dir'/'browse'/'select' 比 0/1/2 更好理解）
- `selectedHistoryIds` 是数组：支持真题库的多选功能（同一批次选多题加入考试）

请读取现有的 exam-v2.html，在保留现有结构的基础上扩展 data() 定义。
```

**验证**：
- [ ] exam-v2.html 的 data() 包含上述所有字段
- [ ] `sourceMode` 的 4 个值都有对应的 Tab 面板
- [ ] `modal` 对象包含 `_vbStep`、`_vbPapers`、`_vbQuestions` 等变种题浏览器字段

---

### 步骤 2：实现 AI 出题的完整链路

**目标**：实现从用户输入知识点到 AI 生成题目到保存到题库的完整流程

**提示词**（复制到 Claude Code）：

```
在 exam-v2.html 中实现 AI 出题的完整链路。

【流程概览】
用户输入知识点 + 题型 + 难度 → 点击"AI 出题" → aiGenerate() → POST /api/question/generate
→ 展示题目列表（renderChem 渲染化学式）→ 逐题审核 → saveOne(i) → POST /api/question/save
→ 保存到题库

【methods 实现】

1. aiGenerate() 函数：
```javascript
async aiGenerate() {
  this.loading = true;
  this.errorMsg = '';
  this.generatedQuestions = [];
  this.savedStatus = {};

  try {
    const resp = await fetch('/api/question/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: this.aiForm.topic,
        type: this.aiForm.type,
        difficulty: this.aiForm.difficulty,
        count: this.aiForm.count,
      })
    });

    if (!resp.ok) {
      this.errorMsg = '生成失败，请重试';  // 不显示状态码
      return;
    }

    const data = await resp.json();
    this.generatedQuestions = data.questions || [];

  } catch (e) {
    this.errorMsg = '发送失败，请检查网络';
  } finally {
    this.loading = false;
  }
}
```

2. saveOne(i) 函数：
```javascript
async saveOne(i) {
  if (this.savedStatus[i] === 'saved') return;
  this.savedStatus[i] = 'saving';

  try {
    const q = this.generatedQuestions[i];
    const resp = await fetch('/api/question/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: q.type,
        content: q.content,
        answer: q.answer,
        analysis: q.analysis || '',
        topic: this.aiForm.topic,
        difficulty: this.aiForm.difficulty,
        source: 'ai',
      })
    });

    if (resp.ok) {
      this.savedStatus[i] = 'saved';
    } else {
      this.errorMsg = '保存失败，请重试';
      this.savedStatus[i] = null;
    }
  } catch (e) {
    this.errorMsg = '发送失败，请检查网络';
    this.savedStatus[i] = null;
  }
}
```

3. saveAll() 函数：
批量保存所有未保存的题目：
```javascript
async saveAll() {
  for (let i = 0; i < this.generatedQuestions.length; i++) {
    if (this.savedStatus[i] !== 'saved') {
      await this.saveOne(i);
    }
  }
}
```

4. 结果展示模板（在 sourceMode='ai' 的 v-show 块中）：
```html
<div v-show="sourceMode === 'ai'" class="tab-panel">
  <!-- 输入表单 -->
  <div class="form-row">
    <input v-model="aiForm.topic" placeholder="输入知识点，如：氧化还原反应">
    <select v-model="aiForm.type">
      <option value="choice">选择题</option>
      <option value="fill">填空题</option>
      <option value="judge">判断题</option>
      <option value="short">简答题</option>
    </select>
    <input type="range" v-model="aiForm.difficulty" min="1" max="5">
    <span>难度: {{ aiForm.difficulty }}</span>
    <input type="number" v-model="aiForm.count" min="1" max="20">
    <button @click="aiGenerate" :disabled="loading">
      {{ loading ? '生成中...' : 'AI 出题' }}
    </button>
  </div>

  <!-- 错误提示 -->
  <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

  <!-- 生成结果 -->
  <div v-if="generatedQuestions.length" class="questions-list">
    <div class="actions-bar">
      <button @click="saveAll">全部保存</button>
    </div>
    <div v-for="(q, i) in generatedQuestions" :key="i" class="question-card">
      <div class="q-header">
        <span>{{ i+1 }}. {{ {choice:'选择题',fill:'填空题',judge:'判断题',short:'简答题'}[q.type] }}</span>
        <span v-if="savedStatus[i] === 'saved'" class="badge-saved">已保存</span>
        <span v-else-if="savedStatus[i] === 'saving'" class="badge-saving">保存中...</span>
        <button v-else @click="saveOne(i)" class="btn-save">保存</button>
      </div>
      <div class="q-content" v-html="renderChem(q.content)"></div>
      <div class="q-answer" v-if="q.answer">
        <strong>答案：</strong><span v-html="renderChem(q.answer)"></span>
      </div>
    </div>
  </div>
</div>
```

请读取现有的 exam-v2.html，在 AI Tab 面板中补全这些逻辑。保留已有的手动录入表单和变种题入口。
```

**验证**：
- [ ] `aiGenerate()` 调用 `POST /api/question/generate` 正确
- [ ] `saveOne(i)` 逐题保存，`saveAll()` 批量保存
- [ ] 生成结果用 `renderChem(q.content)` 渲染化学式
- [ ] 已保存的题目显示"已保存"徽章
- [ ] 错误提示不显示 HTTP 状态码

---

### 步骤 3：实现题库管理和历史真题库 Tab

**目标**：完成 Tab 2（题库管理）和 Tab 3（历史真题库）的业务逻辑

**提示词**（复制到 Claude Code）：

```
在 exam-v2.html 中实现题库管理和历史真题库 Tab。

【Tab 2 — 题库管理（sourceMode='bank'）】

数据加载：
```javascript
async loadBankQuestions() {
  const params = new URLSearchParams({
    page: this.bankPage,
    type: this.bankFilter.type,
    topic: this.bankFilter.topic,
    difficulty: this.bankFilter.difficulty,
  });
  const resp = await fetch('/api/question/bank?' + params);
  const data = await resp.json();
  this.bankQuestions = data.questions;
  this.bankTotal = data.total;
}
```

列表展示：
```html
<div v-show="sourceMode === 'bank'" class="tab-panel">
  <!-- 筛选栏 -->
  <div class="filter-bar">
    <input v-model="bankFilter.topic" placeholder="按知识点搜索" @input="loadBankQuestions">
    <select v-model="bankFilter.type" @change="loadBankQuestions">
      <option value="">全部题型</option>
      <option value="choice">选择题</option>
      <option value="fill">填空题</option>
      <option value="judge">判断题</option>
      <option value="short">简答题</option>
    </select>
    <select v-model="bankFilter.difficulty" @change="loadBankQuestions">
      <option value="">全部难度</option>
      <option v-for="d in [1,2,3,4,5]" :value="d">难度 {{ d }}</option>
    </select>
  </div>

  <!-- 题目列表 -->
  <div v-for="q in bankQuestions" class="question-card">
    <div class="q-header">
      <span class="q-type">{{ {choice:'选择',fill:'填空',judge:'判断',short:'简答'}[q.type] }}</span>
      <span class="q-difficulty">难度 {{ q.difficulty }}</span>
      <span class="q-topic">{{ q.topic }}</span>
    </div>
    <div class="q-content" v-html="renderChem(q.content)"></div>
    <div class="q-actions">
      <button @click="editBankQuestion(q)">编辑</button>
      <button @click="confirmDelete(q)" class="btn-danger">删除</button>
    </div>
  </div>

  <!-- 分页 -->
  <div class="pagination" v-if="bankTotal > 20">
    <button :disabled="bankPage<=1" @click="bankPage--; loadBankQuestions()">上一页</button>
    <span>第 {{ bankPage }} 页 / 共 {{ Math.ceil(bankTotal/20) }} 页</span>
    <button :disabled="bankPage >= Math.ceil(bankTotal/20)" @click="bankPage++; loadBankQuestions()">下一页</button>
  </div>
</div>
```

编辑题库题目：打开编辑表单（复用手动录入的表单字段），修改后 PUT /api/question/{id}。
删除确认：Modal 二次确认 → DELETE /api/question/{id} → loadBankQuestions() 刷新。

---

【Tab 3 — 历史真题库（sourceMode='history'）】

数据加载：
```javascript
async loadHistory() {
  const resp = await fetch(`/api/questions/history?year=${this.historyYear}&region=${this.historyRegion}`);
  const data = await resp.json();
  this.historyQuestions = data.questions || [];
  this.selectedHistoryIds = [];
}
```

图片渲染（关键——page_image 路径从 JSON 读取，前端拼接完整 URL）：
```html
<img :src="'/static/figures/' + encodeURIComponent(q.region || '') + '/' + q.year + '/' + q.page_image"
     @error="e => e.target.style.display='none'"
     loading="lazy">
```

注意：`page_image` 是相对路径（如 `figures/hunan/2024/p1.jpg`），前端需要知道 `region` 和 `year` 才能拼接。如果 JSON 里没有这两个字段，图片加载不出来。解决方案：导入时在 JSON 里写完整路径，或前端做 fallback。

多选加入考试：
```html
<input type="checkbox" v-model="selectedHistoryIds" :value="q.id">
<button @click="addHistToExam" :disabled="!selectedHistoryIds.length">
  将选中题目加入考试 ({{ selectedHistoryIds.length }})
</button>

<!-- 点击后弹出考试选择 Modal -->
```

addHistToExam() 函数：
```javascript
async addHistToExam() {
  // 打开 Modal 选择目标考试
  this.modal.show = true;
  this.modal.title = '选择目标考试';
  this.modal.message = '请选择要加入的考试';
  this.modal.type = 'exam-select';  // 考试列表选择器
  this.modal.onConfirm = async (examId) => {
    await fetch(`/api/exam/${examId}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question_ids: this.selectedHistoryIds })
    });
    this.modal.show = false;
    this.selectedHistoryIds = [];
  };
}
```

请读取现有的 exam-v2.html，在 Bank 和 History Tab 面板中补全这些逻辑。
```

**验证**：
- [ ] 题库 Tab 支持按知识点/题型/难度筛选，支持分页
- [ ] 题库题目可以编辑和删除（删除有二次确认）
- [ ] 历史真题库支持按年份/区域筛选
- [ ] 真题图片能正确渲染（路径拼接正确）
- [ ] 多选真题后可以加入考试

---

### 步骤 4：实现考试列表和管理 Tab

**目标**：完成 Tab 4（考试列表）——创建考试、添加题目、预览、发布

**提示词**（复制到 Claude Code）：

```
在 exam-v2.html 中实现考试列表和管理 Tab。

【Tab 4 — 考试列表（sourceMode='exam'）】

数据加载：
```javascript
async loadExams() {
  const resp = await fetch('/api/exam/list');
  const data = await resp.json();
  this.exams = data.exams || [];
}
```

创建考试：
```html
<button @click="showCreateExamModal">+ 创建考试</button>
<!-- Modal 中输入考试名称 + 选择班级 → POST /api/exam/create -->
```

管理考试（manageExam 函数）：
```javascript
async manageExam(exam) {
  this.selectedExam = exam;
  this.modal.show = true;
  this.modal.title = `管理考试: ${exam.name}`;
  this.modal.type = 'exam-manage';
  this.modal._manageTab = 'paper';

  // 加载考试中的题目
  const resp = await fetch(`/api/exam/${exam.id}/questions`);
  const data = await resp.json();
  this.examQuestions = data.questions || [];
}
```

考试管理面板（Modal 内）：
```html
<div v-if="modal.type === 'exam-manage'">
  <!-- 子 Tab -->
  <div class="sub-tabs">
    <button @click="modal._manageTab='paper'" :class="{active:modal._manageTab==='paper'}">
      试卷
    </button>
    <button @click="modal._manageTab='questions'" :class="{active:modal._manageTab==='questions'}">
      题目管理
    </button>
  </div>

  <!-- 试卷 Tab -->
  <div v-show="modal._manageTab === 'paper'">
    <!-- 预览按钮 -->
    <button @click="previewExam" :disabled="modal.previewLoading">
      {{ modal.previewLoading ? '加载中...' : '预览试卷' }}
    </button>

    <!-- 发布按钮 -->
    <button v-if="!selectedExam.published"
            @click="publishExam"
            class="btn-primary">
      发布考试
    </button>
    <span v-else class="badge-published">已发布</span>

    <!-- 预览内容 -->
    <div v-if="modal.previewQuestions" class="exam-preview" style="max-width:480px;margin:0 auto;">
      <h3>{{ selectedExam.name }}</h3>
      <div v-for="(q,i) in modal.previewQuestions" class="q-card">
        <div>{{ i+1 }}. <span v-html="renderChem(q.content)"></span></div>
      </div>
    </div>
  </div>

  <!-- 题目管理 Tab -->
  <div v-show="modal._manageTab === 'questions'">
    <div v-for="(q,i) in examQuestions" class="q-card">
      <span>{{ i+1 }}.</span>
      <span v-html="renderChem(q.content)"></span>
      <button v-if="!selectedExam.published"
              @click="removeFromExam(q.id)"
              class="btn-danger btn-sm">
        移除
      </button>
    </div>
  </div>
</div>
```

预览试卷（previewExam）：
```javascript
async previewExam() {
  this.modal.previewLoading = true;
  const resp = await fetch(`/api/exam/${this.selectedExam.id}/questions`);
  const data = await resp.json();
  this.modal.previewQuestions = data.questions;
  this.modal.previewLoading = false;
}
```

发布考试（publishExam）——关键约束：
```javascript
async publishExam() {
  // 二次确认
  const confirmed = confirm('发布后题目不可修改，确定发布？');
  if (!confirmed) return;

  await fetch(`/api/exam/${this.selectedExam.id}/publish`, { method: 'POST' });
  // 发布后：selectedExam.published = true
  // 所有修改按钮（编辑、删除、移除）锁定
  this.loadExams();  // 刷新考试列表
  this.modal.show = false;
}
```

关键约束：
- 发布后不可修改题目（`question_stats.published = true` 时锁定所有编辑/删除/移除按钮）
- 种子教师原话："万一学生已经看到了，我改了题目就乱套了"
- 发布确认弹窗文字："发布后题目不可修改，确定发布？"

请读取现有的 exam-v2.html，在 Exam Tab 面板中补全这些逻辑。
```

**验证**：
- [ ] 考试列表 Tab 可以创建考试、管理考试、预览试卷
- [ ] 考试管理面板有两个子 Tab（试卷 / 题目管理）
- [ ] 预览试卷用移动端样式（max-width: 480px）
- [ ] 发布后所有修改按钮被锁定，显示"已发布"徽章

---

### 步骤 5：实现变种题浏览器（Toggle 多选 + 教师审核流程）

**目标**：实现出题工作台中的变种题生成和教师审核系统

**提示词**（复制到 Claude Code）：

```
在 exam-v2.html 中实现变种题浏览器的完整功能。

【变种题浏览器的三步骤流程】

_step 1 — 'dir'：选择来源_
显示已保存的试卷/考试列表，选择一个作为变种题的来源。
```javascript
async openVariantBrowser() {
  this.modal.show = true;
  this.modal._vbStep = 'dir';
  this.modal.title = '变种题浏览器';

  // 加载试卷列表
  const resp = await fetch('/api/exam/list');
  const data = await resp.json();
  this.modal._vbPapers = data.exams || [];
}
```

_step 2 — 'browse'：浏览题目并多选_
选择试卷后，展示该试卷的所有题目。每道题前面有 Toggle 复选框（多选样式）。

```html
<div v-if="modal._vbStep === 'browse'">
  <p>选择要生成变种题的题目（可多选）：</p>
  <div v-for="q in modal._vbQuestions" class="variant-select-card">
    <label class="toggle-label">
      <!-- Toggle 开关 -->
      <div class="toggle-switch"
           :class="{active: q._selected}"
           @click="q._selected = !q._selected">
        <div class="toggle-knob"></div>
      </div>
      <span>{{ q.type }} | 难度{{ q.difficulty }}</span>
    </label>
    <div v-html="renderChem(q.content)"></div>
  </div>

  <button @click="generateVariants"
          :disabled="!modal._vbQuestions.some(q=>q._selected)">
    生成变种题 ({{ modal._vbQuestions.filter(q=>q._selected).length }})
  </button>
</div>
```

_step 3 — 'select'：审核变种题_
AI 生成变种题后，进入审核步骤。展示原始题和变种题并排对比，教师逐题审核。

【变种题教师审核五步流程】
```
1. 生成：generateVariants() → POST /api/question/variants → AI 生成变种题
2. 自动审核：后端检查四条红线（系数/条件/产物/知识点）
3. 人工审核：变种题浏览器中展示对比，教师逐题确认/拒绝/修改
4. 保存：确认通过的题目 → POST /api/question/save
5. 重生成：拒绝的题目 → 点击"重新生成" → 回到步骤 1（单题重新生成）
```

审核界面：
```html
<div v-if="modal._vbStep === 'select'">
  <div v-for="(pair, i) in variantPairs" class="variant-pair">
    <div class="pair-original">
      <span class="label">原题</span>
      <div v-html="renderChem(pair.original.content)"></div>
    </div>
    <div class="arrow">→</div>
    <div class="pair-variant">
      <span class="label">变种题</span>
      <div v-html="renderChem(pair.variant.content)"></div>
      <div class="variant-diff" v-if="pair.changes">
        <!-- 高亮变化的部分 -->
        <span class="diff-item" v-for="c in pair.changes">
          {{ c.field }}: {{ c.from }} → {{ c.to }}
        </span>
      </div>
    </div>
    <div class="pair-actions">
      <button @click="approveVariant(i)" class="btn-success">通过</button>
      <button @click="rejectVariant(i)" class="btn-warning">拒绝</button>
      <button @click="regenerateVariant(i)" class="btn-secondary">重新生成</button>
    </div>
  </div>

  <button @click="saveApprovedVariants">保存已通过题目 ({{ approvedCount }})</button>
</div>
```

【Toggle 多选实现细节】
```css
.toggle-switch {
  width: 44px;
  height: 24px;
  background: #ccc;
  border-radius: 12px;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
}
.toggle-switch.active {
  background: #2c6e49;
}
.toggle-knob {
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  position: absolute;
  top: 2px;
  left: 2px;
  transition: left 0.2s;
}
.toggle-switch.active .toggle-knob {
  left: 22px;
}
```

请读取现有的 exam-v2.html，在 AI Tab 的变种题入口中补全这些逻辑。
```

**验证**：
- [ ] 变种题浏览器有三步骤流程（dir → browse → select）
- [ ] Toggle 开关样式可用（滑动手感 + 颜色变化）
- [ ] 并排对比原题和变种题（renderChem 渲染）
- [ ] 教师可以逐题审核（通过/拒绝/重新生成）

---

### 步骤 6：实现四条红线约束

**目标**：在后端工具中实现变种题的自动审核规则

**提示词**（复制到 Claude Code）：

```
在 agent/tools.py 的 generate_question / create_variant 工具中实现"四条红线"约束。

【四条红线定义】
这是种子教师和开发者共同讨论后确定的 AI 出题不可逾越的约束：

1. 系数约束：化学方程式必须配平
   - 反应物和产物的原子数必须相等
   - 检查：生成后验证配平 → 不配平 = 自动拒绝

2. 条件约束：反应条件必须合理
   - 温度、压强、催化剂等必须符合热力学和动力学规律
   - 检查：实验室常规条件（常温常压/加热/高温/催化剂）是否匹配反应类型
   - 反例："常温下 Cu + H2SO4(稀) → CuSO4 + H2"→ 违背！稀硫酸常温不跟铜反应

3. 产物约束：产物必须符合热力学
   - 产物不能是热力学上不可能的物质
   - 反例："C + O2 → CO（而不生成CO2）"在某些条件下合理，
     但"NaCl + H2O → NaOH + Cl2 + H2"常温下不合理

4. 知识点约束：知识点必须贴合教学大纲
   - 高中化学知识范围内（不出大学内容）
   - 知识点必须来自预设的知识点列表
   - 反例：出"分子轨道理论"的题目 → 超纲，拒绝

【实现方式】

```python
def validate_question(question: dict) -> dict:
    """对 AI 生成的题目做四条红线审核。

    返回: {passed: bool, violations: list[str], warnings: list[str]}
    """
    violations = []
    warnings = []

    # 红线 1：方程式配平检查
    equations = extract_chemical_equations(question.get("content", ""))
    for eq in equations:
        if not is_balanced(eq):
            violations.append(f"方程式未配平: {eq}")

    # 红线 2：反应条件检查
    conditions = extract_reaction_conditions(question.get("content", ""))
    for cond in conditions:
        if not is_condition_reasonable(cond):
            violations.append(f"反应条件不合理: {cond}")

    # 红线 3：产物检查
    products = extract_products(question.get("content", ""))
    for prod in products:
        if not is_product_thermodynamically_valid(prod):
            violations.append(f"产物不符合热力学: {prod}")

    # 红线 4：知识点检查
    topics = question.get("topics", [])
    for topic in topics:
        if topic not in VALID_HIGH_SCHOOL_TOPICS:
            violations.append(f"知识点超纲: {topic}")

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
    }


def is_balanced(equation: str) -> bool:
    """检查化学方程式是否配平。

    简化实现：用正则提取反应物和产物的系数和原子组成，对比原子数。
    完整实现需要化学方程式解析器（超出本节课范围——但给学生展示简化思路）。
    """
    # 简化版：检查是否有系数（有数字就是配平的标志）
    # 真实项目中的完整实现见补充内容表格
    pass


VALID_HIGH_SCHOOL_TOPICS = [
    "氧化还原反应", "离子反应", "化学平衡", "电解质溶液",
    "元素周期律", "化学键", "有机化学", "化学反应速率",
    "化学计量", "热化学", "电化学", "物质结构",
]
```

【generate_question 工具中调用审核】

```python
async def generate_question(topic: str, type: str, difficulty: int, count: int):
    """AI 出题 + 四条红线审核"""
    # 1. LLM 生成题目
    questions = await _llm_generate(topic, type, difficulty, count)

    # 2. 对每道题做四条红线审核
    validated = []
    for q in questions:
        result = validate_question(q)
        if result["passed"]:
            validated.append(q)
        else:
            # 记录违规尝试重新生成（最多 3 次）
            retries = 0
            while retries < 3 and not validate_question(q)["passed"]:
                q = await _llm_regenerate_single(topic, type, difficulty)
                retries += 1
            if retries < 3:
                validated.append(q)

    return {"questions": validated}
```

请完整实现 agent/tools.py 中的四条红线约束逻辑。
```

**验证**：
- [ ] `validate_question()` 函数存在，返回 `{passed, violations, warnings}`
- [ ] 四条红线全部有对应的检查逻辑
- [ ] `VALID_HIGH_SCHOOL_TOPICS` 包含预设的知识点列表
- [ ] AI 生成的题目会先过红线审核再过教师人工审核

---

### 步骤 7：完善 renderChem 函数（KaTeX 保护方案 v3）

**目标**：修复化学式渲染的 marked 崩溃问题，实现最终版 KaTeX 保护方案

**提示词**（复制到 Claude Code）：

```
在 exam-v2.html 中完善 renderChem 函数，实现最终的 KaTeX 保护方案。

【三次迭代回顾】
v1：不做 KaTeX，纯文本显示 → $\mathrm{H_2SO_4}$ 原始字符串
v2：marked + KaTeX 串联 → marked v12 废弃 setOptions() → 崩溃
v3（最终）：LaTeX 保护 → marked 处理纯 Markdown → KaTeX 恢复

【最终方案实现】
```javascript
renderChem: function(text) {
    if (!text) return '';

    try {
        var h = String(text);

        // === 第 1 步：保护 LaTeX 块 ===
        var blocks = [];
        var blockIdx = 0;

        // 保护 $$...$$ 块级公式
        h = h.replace(/\$\$([\s\S]*?)\$\$/g, function(match, tex) {
            var key = '%%BLOCK_' + (blockIdx++) + '%%';
            blocks.push({key: key, tex: tex, display: true});
            return key;
        });

        // 保护 $...$ 行内公式
        h = h.replace(/\$(?!\$)([\s\S]*?)\$/g, function(match, tex) {
            var key = '%%INLINE_' + (blockIdx++) + '%%';
            blocks.push({key: key, tex: tex, display: false});
            return key;
        });

        // === 第 2 步：Markdown → HTML ===
        if (typeof marked !== 'undefined' && marked.parse) {
            h = marked.parse(h, {
                breaks: true,    // 换行转 <br>
                gfm: true,       // GitHub Flavored Markdown
            });
        }

        // === 第 3 步：恢复 LaTeX → KaTeX 渲染 ===
        for (var i = 0; i < blocks.length; i++) {
            var b = blocks[i];
            try {
                if (typeof katex !== 'undefined' && katex.renderToString) {
                    var rendered = katex.renderToString(b.tex, {
                        throwOnError: false,       // 渲染错误不抛异常
                        displayMode: b.display,     // 块级或行内
                        strict: false,              // 不严格模式（允许中文）
                    });
                    h = h.replace(b.key, rendered);
                } else {
                    // KaTeX 不可用，保留原始 LaTeX
                    h = h.replace(b.key, '$' + b.tex + '$');
                }
            } catch (e) {
                // KaTeX 渲染失败，显示原始 LaTeX
                h = h.replace(b.key, '$' + b.tex + '$');
            }
        }

        return h;

    } catch (e) {
        // 全局 fallback：原始文本
        console.warn('renderChem fallback:', e);
        return String(text);
    }
}
```

【为什么这个方案更好】
1. **LaTeX 保护**：在 marked 处理之前，所有 LaTeX 公式被替换成无害的占位符。marked 不会对它们做任何处理。
2. **marked API 隔离**：即使用 `marked.parse()`（v12 API），如果 marked 未来更改 API，LaTeX 部分不受影响。
3. **KaTeX 独立**：KaTeX 渲染在 marked 之后独立恢复，两个库互不干扰。
4. **多层 fallback**：KaTeX 不可用 → 显示原始 LaTeX；marked 不可用 → 跳过 Markdown 渲染；全部崩溃 → 显示原始文本。

【CDN 引入（确保在 <head> 中）】
```html
<!-- KaTeX CSS -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<!-- Markdown 解析 -->
<script src="https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js"></script>
<!-- KaTeX JS（放在 marked 后面） -->
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
```

注意：`marked@4.3.0` 是 v12 API 变更前的最后一个稳定版。如果用 `marked@latest`，需要确保 `marked.parse()` 可用（v12+）。锁版本比"用最新版"更安全。

请读取现有的 exam-v2.html，用上述 v3 方案替换 renderChem 函数。
```

**验证**：
- [ ] renderChem 函数包含 LaTeX 保护 - marked 解析 - KaTeX 恢复 三步
- [ ] 测试文本 `$\mathrm{H_2SO_4}$` 能渲染为化学式
- [ ] 测试文本 `$$2H_2 + O_2 → 2H_2O$$` 能渲染为块级公式
- [ ] marked 不可用时（删除 CDN 脚本测试）仍能显示原始文本
- [ ] KaTeX 不可用时仍能显示原始 LaTeX 文本

---

### 步骤 8：完善 SSE Component 事件机制

**目标**：让 Agent 返回的考试工作台内联面板能正确在前端渲染

**提示词**（复制到 Claude Code）：

```
完善 agent/channel/langgraph_channel.py 中的 SSE component 事件机制，以及前端 agent.js 的事件处理。

【后端 — langgraph_channel.py】

确认 `stream_agent_response` 函数中正确处理了 component 事件：

```python
# 在 graph.astream() 循环中
async for event in graph.astream(...):
    for node_name, output in event.items():
        # ... token 处理 ...

        # 检查内联面板指令
        if output.get("last_component"):
            component_data = output["last_component"]
            yield f"data: {json.dumps({'type': 'component', 'data': component_data})}\n\n"

        # 检查页面跳转指令
        if output.get("last_route"):
            route_data = output["last_route"]
            yield f"data: {json.dumps({'type': 'route', 'data': route_data})}\n\n"
```

_Sub-agent 的 create_sub_agent_node 中，
从 guard_state 提取 _component / _route 并写入 output：_

```python
# 子专家执行完后
extracted_ctx = guard_state.extract()
return {
    # ... messages, shared_context ...
    "last_component": extracted_ctx.get("_component"),
    "last_route": extracted_ctx.get("_route"),
}
```

【前端 — 在 index.html 的 SSE 事件处理中添加 component 分支】

```javascript
// EventSource onmessage 处理
es.addEventListener('message', function(e) {
    if (e.data === '[DONE]') {
        es.close();
        return;
    }

    try {
        var msg = JSON.parse(e.data);

        switch (msg.type) {
            case 'token':
                // 追加到当前 AI 消息
                appendToCurrentAI(msg.content);
                break;

            case 'component':
                // 渲染内联面板
                renderComponent(msg.data);
                break;

            case 'route':
                // 页面跳转
                window.location.href = msg.data.target;
                break;

            case 'error':
                // 错误提示（不显示 HTTP 状态码）
                showError(msg.message || '处理出错');
                break;
        }
    } catch (e) {
        // 非 JSON 消息（如 [PING]），忽略
    }
});

function renderComponent(data) {
    // data.type 决定渲染哪个面板
    switch (data.type) {
        case 'exam-workbench':
            // 在对话区底部的内联面板区域展示出题工作台
            var panel = document.getElementById('inline-panel');
            panel.innerHTML = '';  // 清空
            panel.style.display = 'block';

            // 嵌入 exam-v2.html 的 AI Tab 内容
            // 实际实现：用 iframe 或动态加载 exam-v2.html 的 Vue 实例
            renderExamWorkbenchInline(data);
            break;

        case 'diagnosis-result':
            // 渲染诊断结果
            renderDiagnosisInline(data);
            break;

        default:
            console.warn('Unknown component type:', data.type);
    }
}
```

【component 事件的格式】
```json
{
  "type": "component",
  "data": {
    "type": "exam-workbench",
    "questions": [...],
    "topic": "氧化还原反应"
  }
}
```

请确保 SSE 流和前端事件处理完整闭合（子专家返回 component → SSE emit → 前端 renderComponent → 内联面板显示）。
```

**验证**：
- [ ] SSE 流在子专家返回 `last_component` 时能 emit `component` 事件
- [ ] SSE 流在子专家返回 `last_route` 时能 emit `route` 事件
- [ ] 前端 switch 分支至少处理 exam-workbench 和 diagnosis-result 两种 component 类型
- [ ] 前端能正确渲染内联面板（在对话区中展示，不跳转页面）

---

## 发生了什么（教师参考）

### 1. 出题→审核→保存的完整链路

这是 ChemAI 最核心的业务流程。不是"AI 出题就完事"——因为这正是种子教师对 AI 不信任的根本原因。

完整链路的每一步都有明确的职责：

```
教师输入知识点 → POST /api/question/generate
  │
  ▼
exam_expert 子专家
  │ - generate_question() 调 LLM 生成题目
  │ - 四条红线自动审核
  │ - 不通过的题自动重生成（最多 3 次）
  │
  ▼
返回题目列表（SSE component 事件）
  │
  ▼
前端展示题目卡片（renderChem 渲染化学式）
  │ - 每道题有独立的保存状态（unsaved/saving/saved）
  │
  ▼
教师逐题审核（人在回路）
  │ - 确认 → 保存
  │ - 拒绝 → 丢弃
  │ - 修改 → 编辑后保存
  │
  ▼
POST /api/question/save → 写入数据库
```

人在回路（Human-in-the-Loop）是这个系统最核心的设计原则。AI 出题只是"建议"——最终决定权在教师手里。这是恢复 AI 信任的唯一方式。

### 2. 四条红线约束的完整规则表

| 红线 | 定义 | 检查方式 | 反例 | 正例 |
|------|------|---------|------|------|
| 1. 系数 | 方程式配平 | 原子数比对 | Fe + HCl → FeCl3 + H2 (未配平) | 2Fe + 6HCl → 2FeCl3 + 3H2 |
| 2. 条件 | 反应条件合理 | 热力学/动力学规则库 | 常温 Cu + 稀H2SO4 → CuSO4 + H2 | 加热 Cu + 浓H2SO4 → CuSO4 + SO2 + H2O |
| 3. 产物 | 产物热力学可能 | 标准电极电势/吉布斯自由能 | NaCl + H2O 常温电解并非完全不可能，但条件苛刻 | 2NaCl + 2H2O → 通电 → 2NaOH + Cl2 + H2 |
| 4. 知识点 | 贴合教学大纲 | 与预设知识点列表匹配 | 出"分子轨道理论"的选择题 | 出"杂化轨道理论"的选择题 |

种子教师在审核过程中发现的真实违规案例：
- AI 生成的方程式 `Na + H2O → NaOH + H2` 没有配平（应为 2Na + 2H2O → 2NaOH + H2）
- AI 生成的题目涉及"配位场理论"——这是大学化学内容，高中不考
- AI 把"催化剂"写成"接触剂"——虽然意思接近但高中教材不用这个词

### 3. renderChem 三次迭代的详细对比

| 维度 | v1 (纯文本) | v2 (marked + KaTeX) | v3 (KaTeX 保护方案) |
|------|-----------|-------------------|-------------------|
| LaTeX 渲染 | 不支持，显示源码 | 支持，但不稳定 | 支持，稳定 |
| 代码行数 | 1 行 | ~30 行 | ~60 行 |
| 失败保护 | 天然无失败 | 无保护层，marked 崩溃全部崩溃 | 3 层 fallback |
| marked 版本 | 不依赖 | v12 (latest) | v4.3.0 (锁定) |
| 化学式显示 | `$\mathrm{H_2SO_4}$` | H2SO4 | H2SO4 |
| 已知问题 | 不好看 | **marked v12 API 废弃导致崩溃** | 代码略长但可靠 |

核心教训：**CDN 引入的第三方库没有版本锁定（没有 package-lock.json），API 变更会导致静默崩溃**。对前端隐式依赖要加保护层。

v3 方案的 3 层 fallback 链：
1. KaTeX 可用 → 渲染为漂亮的化学式
2. KaTeX 不可用 → 显示原始 LaTeX 文本（用户能看懂）
3. marked 不可用 → 显示原始 Markdown + LaTeX 文本（勉强能读）

"显示原始 LaTeX"优于"显示红色错误块"——产品设计选择：用户自己能看懂 `$\mathrm{H_2SO_4}$`，但要看懂 React Error Boundary 的 error stack 就比较困难了。

### 4. 变种题浏览器的 Toggle 多选设计

为什么要用 Toggle 开关而非传统的 checkbox？

种子教师在 iPad 上试用时反馈："复选框太小了，点不到。"iPad 的触摸精度不如鼠标，标准 16x16px 的 checkbox 需要 2-3 次才能点中。

Toggle 开关的改进：
- 尺寸：44x24px（符合 iOS Human Interface Guidelines 的最小触控目标 44pt）
- 视觉反馈：滑动动画 + 颜色变化（灰色→甲基绿 #2c6e49）
- 选中状态：清晰可辨（toggle-knob 从左边滑到右边）

代码实现细节（纯 CSS + Vue 绑定）：
```css
.toggle-switch { width: 44px; height: 24px; border-radius: 12px; cursor: pointer; }
.toggle-switch.active { background: #2c6e49; }
.toggle-knob { width: 20px; height: 20px; border-radius: 50%; transition: left 0.2s; }
```

### 5. 变种题教师审核五步流程

```
1. 生成（AI）
   输入：原题 + 知识点 + 四条红线约束
   输出：变种题（含 changes 字段标注变化部分）
   POST /api/question/variants

2. 自动审核（规则引擎）
   检查：四条红线全部通过？
   不通过 → 自动重生成（最多 3 次）
   通过 → 进入人工审核队列

3. 人工审核（教师）
   界面：原题 vs 变种题 并排对比
   高亮：changes 字段标注变化部分（如 "系数: 1:1 → 2:3"）
   操作：通过 / 拒绝 / 重新生成（单题）

4. 保存（系统）
   确认通过的题目 → POST /api/question/save
   source 字段标记为 "variant"
   parent_id 关联原题

5. 重生成（AI）
   拒绝的题目 → 单题重新生成
   循环回到步骤 1（但只针对拒绝的题）
   最多 3 次重生成，仍不通过则放弃
```

审核通过率数据（基于种子教师的实际测试）：
- 首次生成通过率：约 60%（AI 生成 10 道，6 道直接通过四条红线）
- 自动重生成后通过率：约 85%（不通过的 4 道中，1-2 道在重生成后通过）
- 人工审核通过率：教师通常保留 70-80% 的通过题目
- 最终到题库的题目：约 50-60% 的原始生成题目

这说明四条红线约束虽然严格，但确实能拦截到真实的违规题。教师不需要审核所有题目就能信任结果。

### 6. 考试发布的锁定机制

种子教师要求的核心约束："万一学生已经看到了，我改了题目就乱套了。"

实现逻辑：
- `question_stats.published = true` 时，前端所有修改按钮变为 disabled
- 后端 API 在发布后拒绝修改题目（`PUT /api/question/{id}` 返回 403）
- 发布时显示二次确认弹窗："发布后题目不可修改，确定发布？"
- 没有"取消发布"功能——这是有意的设计选择。一旦学生开始做题，撤回题目会造成混乱。

### 7. 内联面板 vs 页面跳转的最终决策

ChemAI 中不是所有功能都是独立页面。高频操作使用内联面板：

| 操作 | 交互方式 | 理由 |
|------|---------|------|
| 出题工作台 | 内联面板 | 高频操作（每天 5-10 次），在聊天中直接完成 |
| 诊断结果 | 内联面板 | 紧跟出题流程，不需要切换上下文 |
| 变种题浏览器 | 内联面板 | 与出题工作台共享上下文 |
| 学生管理 | 页面跳转 | 低频操作（每月 1-2 次），需要完整表格 |
| 学情面板 | 页面跳转 | 需要大屏图表，内联面板放不下 |
| 答题卡识别 | 页面跳转 | 需要文件上传 UI |

技术实现：工具返回 `_component` 指令 → GuardState 剥离 → 写入 `state.last_component` → SSE adapter emit `component` 事件 → 前端 switch 分支渲染对应组件。

### 8. 前端错误处理的完整体验

| 错误类型 | 用户看到 | 开发者看到 |
|---------|---------|-----------|
| 化学式渲染失败 | 原始 LaTeX 文本（$\mathrm{H_2SO_4}$） | console.warn |
| 网络错误 | "发送失败，请检查网络" | browser devtools network tab |
| AI 超时（30s） | "AI 思考时间较长，请稍候..." | 连接仍保持，不关闭 |
| 对话持久化失败 | 无提示（静默） | server log |
| 登录态过期 | 自动跳转登录页 | 401 状态码 |
| 删除操作 | "确定删除 [名称] 吗？此操作不可撤销。" | — |

关键原则：用户不需要知道系统内部状态码或错误堆栈。给他们能理解的、可操作的信息。

### 9. 经常出现的问题

**Q：历史真题的图片路径 404 了怎么办？**
A：检查三个字段是否都存在：`region`（如 "hunan"）、`year`（如 "2024"）、`page_image`（如 `figures/hunan/2024/p1.jpg`）。如果缺了任一字段，图片路径拼接不完整。解决方案：导入时在 JSON 的 `page_image` 字段写完整相对路径。

**Q：KaTeX 渲染中文报错 "Unicode character ... not supported"？**
A：KaTeX 不处理中文字符。确保 LaTeX 公式里的中文用 `\mathrm{}` 包裹，或者在 `renderChem` 的第 1 步中把 `$...$` 内的中文移到公式外面。

**Q：四条红线检查太慢了怎么办？**
A：四条红线检查是纯 Python 字符串操作 + 正则匹配，不是 LLM 调用。延迟在 10ms 以内。如果慢，检查是否误写了 LLM 调用。

**Q：教师想修改一条已发布的题目怎么办？**
A：不提供直接的"取消发布"功能。教师需要：创建新考试 → 从旧考试复制题目（排除要修改的那题）→ 添加新题目 → 发布新考试。这是种子教师认可的工作流——"改题目就是新考试"。

**Q：变种题生成的质量不稳定？**
A：变种题的 quality 取决于原题的质量和四条红线约束。如果原题本身有歧义（如条件不明确），变种题的 quality 也会下降。建议教师先确认原题无误再生成变种题。

---

## 课后产出检查

学生应该同时具备：

- [ ] exam-v2.html 4 个 Tab 全部功能完整（AI出题/题库/真题库/考试管理）
- [ ] AI 出题 → 展示 → 逐题保存链路可通过测试
- [ ] 变种题浏览器三步骤流程（选择来源→浏览多选→审核对比）全部可用
- [ ] Toggle 开关多选样式可用（44x24px，滑动动画）
- [ ] 四条红线约束在 `validate_question()` 中实现完整
- [ ] renderChem 使用 KaTeX 保护方案 v3（LaTeX保护→marked→KaTeX恢复）
- [ ] marked CDN 锁定版本 4.3.0（非 latest）
- [ ] SSE component 事件能在前端渲染内联面板
- [ ] 考试发布后所有修改按钮锁定
- [ ] 删除操作有二次确认弹窗

**下节课需要**：出题工作台完整可用 + Agent 系统完整集成。Session 15 将实现数据闭环与障碍诊断（diagnose_barrier + 自适应练习）。

---

## 补充内容 — 教师深度参考

### A. exam-v2.html（917 行）的完整行号索引

| 行号范围 | 内容 |
|---------|------|
| 1-5 | DOCTYPE + meta 标签 |
| 6-20 | CDN 引入（Vue 3 / KaTeX CSS / marked / KaTeX JS） |
| 21-250 | `<style>` 块：全部 CSS（约 230 行） |
| 251-280 | `<div id="app">` 外壳 + 顶部导航栏 |
| 281-320 | Tab 切换按钮组（ai / bank / history / exam） |
| 321-480 | Tab 1（AI 出题工作台）模板 |
| 481-550 | Vue 3 data() 定义 |
| 551-620 | Tab 2（题库管理）模板 |
| 621-700 | Tab 3（历史真题库）模板 |
| 701-780 | Tab 4（考试列表）模板 |
| 781-810 | Modal 通用对话框模板 |
| 811-860 | 变种题浏览器模板 |
| 861-917 | `<script>` 块：全部 JS（methods / mounted / renderChem 等） |

### B. renderChem v3 的三层 fallback 链

| 层级 | 条件 | 输出 | 用户可读性 |
|------|------|------|-----------|
| Fallback 1 | KaTeX 可用 | 漂亮的化学式（H2SO4） | 优秀 |
| Fallback 2 | KaTeX 不可用 | 原始 LaTeX（$\mathrm{H_2SO_4}$） | 可读 |
| Fallback 3 | marked 不可用 | 原始 Markdown + LaTeX | 勉强可读 |
| 全局 fallback | 任意步骤异常 | 原始文本 | 最低保障 |

### C. 四条红线违规检测的代码结构

| 红线 | 函数 | 输入 | 输出 | 检测方式 |
|------|------|------|------|---------|
| 系数 | `is_balanced()` | 化学方程式字符串 | bool | 正则提取原子 + 计数对比 |
| 条件 | `is_condition_reasonable()` | 反应条件字符串 | bool | 条件-反应类型规则库匹配 |
| 产物 | `is_product_thermodynamically_valid()` | 产物列表 | bool | 标准电极电势/吉布斯自由能规则 |
| 知识点 | `is_in_syllabus()` | 知识点字符串 | bool | 与 VALID_HIGH_SCHOOL_TOPICS 对比 |

### D. 变种题生成的成功率数据（实测）

| 步骤 | 输入 | 输出 | 通过率 |
|------|------|------|--------|
| AI 生成 | 原题 + 知识点 | 5 道变种题 | — |
| 四条红线自动审核 | 5 道变种题 | 3 道通过 / 2 道拒绝 | 60% |
| 自动重生成（1 次） | 2 道拒绝题 | 1 道通过 / 1 道拒绝 | 70% |
| 自动重生成（2 次） | 1 道拒绝题 | 1 道通过 / 0 道拒绝 | 80% |
| 人工审核 | 4 道通过题 | 3 道保存 / 1 道拒绝 | 75% |
| **最终有效题目** | **原始 5 题** | **3 题入库** | **60%** |

### E. Component 事件数据格式完整定义

```json
// 出题工作台
{
  "type": "exam-workbench",
  "questions": [
    {
      "type": "choice",
      "content": "下列属于氧化还原反应的是...",
      "answer": "B",
      "analysis": "A选项没有化合价变化...",
      "difficulty": 3,
      "topics": ["氧化还原反应"]
    }
  ],
  "topic": "氧化还原反应",
  "count": 5
}

// 诊断结果
{
  "type": "diagnosis-result",
  "student_name": "张三",
  "barriers": [
    {"type": "配平障碍", "confidence": 0.85, "detail": "..."},
    {"type": "概念混淆", "confidence": 0.62, "detail": "..."}
  ],
  "suggested_exercises": [...]
}
```
