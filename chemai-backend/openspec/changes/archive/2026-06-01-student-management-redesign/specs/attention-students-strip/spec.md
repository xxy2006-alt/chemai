## ADDED Requirements

### Requirement: Attention students strip below charts
The analytics dashboard (teacher.html) SHALL display a horizontal strip of 3-5 "attention-needed" student cards below the chart section, replacing the previous full student table. Each mini card SHALL display: avatar initial, student name, dominant barrier type with color-coded tag. Clicking a card SHALL navigate to the student management page.

#### Scenario: Strip renders with attention students
- **WHEN** dashboard data is loaded and students have barrier diagnoses
- **THEN** up to 5 students with the highest barrier scores are displayed as mini cards

#### Scenario: Strip click navigates to student management
- **WHEN** user clicks a student card in the strip
- **THEN** browser navigates to `/pages/students.html`

#### Scenario: Empty state
- **WHEN** no students have barrier diagnosis data
- **THEN** the strip displays "暂无需要特别关注的学生"

### Requirement: Full student table removed
The analytics dashboard SHALL NOT contain the full student data table that was previously at the bottom of the page. Individual student listing belongs to the student management page.

#### Scenario: No student table renders
- **WHEN** the dashboard page loads
- **THEN** no full-width student data table is displayed in the main content area

### Requirement: Student detail modal removed
The analytics dashboard SHALL NOT contain the student detail modal that was previously triggered by clicking student rows. Student detail viewing belongs to the student management page.

#### Scenario: No detail popup triggers
- **WHEN** the dashboard page loads
- **THEN** no student detail modal markup or event handlers are present
