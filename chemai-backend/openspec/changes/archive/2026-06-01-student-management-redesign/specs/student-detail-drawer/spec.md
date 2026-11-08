## ADDED Requirements

### Requirement: Right-side slide-out drawer
The page SHALL provide a 480px wide right-side drawer panel that slides in when a student card is clicked. The drawer SHALL use a semi-transparent backdrop overlay. On viewports below 600px, the drawer SHALL expand to 100vw.

#### Scenario: Drawer opens on card click
- **WHEN** user clicks a student card
- **THEN** the drawer slides in from the right with a backdrop overlay

#### Scenario: Drawer closes on backdrop click
- **WHEN** user clicks the backdrop area outside the drawer
- **THEN** the drawer slides out and the overlay disappears

#### Scenario: Drawer closes on close button
- **WHEN** user clicks the close (×) button inside the drawer
- **THEN** the drawer slides out

### Requirement: Student profile header
The drawer SHALL display a profile header with: avatar initial letter (large), student full name, class name, and action buttons (send message, export report, transfer class).

#### Scenario: Profile header renders
- **WHEN** drawer opens for a student
- **THEN** student name, class, and action buttons are displayed

### Requirement: Learning stats KPI cards
The drawer SHALL display 4 KPI stat cards: total exercises completed, average correctness rate, recent trend (up/down/flat arrow), and last activity date.

#### Scenario: Stats render with student data
- **WHEN** student data contains exercise history
- **THEN** 4 KPI cards are displayed with correct values

#### Scenario: Stats handle missing data
- **WHEN** student has no exercise history
- **THEN** KPI cards display "--" for missing values

### Requirement: Barrier diagnosis section
The drawer SHALL display a horizontal bar chart showing the student's three barrier type scores (concept understanding, reading comprehension, expression) as percentage bars with color coding (purple/orange/teal).

#### Scenario: Barrier bars render
- **WHEN** student has barrier diagnosis data
- **THEN** three horizontal percentage bars are displayed with labels and values

#### Scenario: No barrier data available
- **WHEN** student has no diagnosis data
- **THEN** a "暂无诊断数据" message is displayed

### Requirement: Score trend mini chart
The drawer SHALL display a mini line chart (160px height) showing the student's score trend over recent exams, using Chart.js with simplified styling (no axis labels, minimal grid).

#### Scenario: Trend chart renders
- **WHEN** student has score history data
- **THEN** a mini line chart is displayed with the trend line

#### Scenario: No trend data available
- **WHEN** student has fewer than 2 exam records
- **THEN** a "暂无趋势数据" message replaces the chart

### Requirement: Weak knowledge point tags
The drawer SHALL display the student's weak knowledge points as pill-shaped tags below the barrier section.

#### Scenario: Tags render
- **WHEN** student has weak knowledge points
- **THEN** each point is displayed as a tag with proper styling

#### Scenario: No weak points
- **WHEN** student has no weak knowledge points
- **THEN** a "暂无数据" placeholder is shown

### Requirement: Recent activity timeline
The drawer SHALL display a timeline of the student's 5 most recent activities (exercise submissions, exams, etc.) with date and activity description.

#### Scenario: Timeline renders
- **WHEN** student has recent activity records
- **THEN** up to 5 activity items are shown with dates

#### Scenario: No activity
- **WHEN** student has no recent activity
- **THEN** a "暂无最近活动" message is displayed
