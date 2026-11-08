## ADDED Requirements

### Requirement: Target pages SHALL read chemai_navigate on load
Every target page (exam-v2, diagnosis, students, teacher) SHALL check `sessionStorage.chemai_navigate` on `DOMContentLoaded`. If present, the page SHALL execute the stored actions and populate the specified targets with data.

#### Scenario: Exam page auto-populates question list
- **WHEN** exam-v2.html loads and `chemai_navigate.data.questionList` contains question data
- **THEN** the question list SHALL be populated automatically

#### Scenario: Diagnosis page auto-renders results
- **WHEN** diagnosis.html loads and `chemai_navigate.data.diagnosisResult` contains diagnosis data
- **THEN** the diagnosis results SHALL be rendered in the result area

#### Scenario: Students page auto-opens drawer
- **WHEN** students.html loads and `chemai_navigate.actions` includes `{action: "openStudentDrawer", payload: {student_id: "..."}}`
- **THEN** the student detail drawer SHALL open automatically for the specified student

#### Scenario: Teacher page auto-selects class
- **WHEN** teacher.html loads and `chemai_navigate.params.class_id` is set
- **THEN** the class selector SHALL switch to the specified class and `loadDashboard()` SHALL be triggered

#### Scenario: chemai_navigate is cleared after consumption
- **WHEN** a target page successfully processes `chemai_navigate`
- **THEN** `sessionStorage.removeItem('chemai_navigate')` SHALL be called to prevent re-execution on refresh

#### Scenario: No navigate data — normal page load
- **WHEN** a target page loads without `chemai_navigate` in sessionStorage
- **THEN** the page SHALL load normally with its default behavior (no data pre-filled)
