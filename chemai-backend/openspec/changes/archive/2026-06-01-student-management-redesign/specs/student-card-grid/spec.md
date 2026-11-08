## ADDED Requirements

### Requirement: Class overview stats bar
The student management page SHALL display a top-level stats bar with 4 KPI cards showing: total students, active students (exercised in last 30 days), students needing attention (barrier score > 60%), and average exercises completed per student.

#### Scenario: Stats bar renders with data
- **WHEN** student data is loaded from API or mock
- **THEN** 4 stat cards are displayed in a horizontal row with value + label format

#### Scenario: Stats bar adapts to empty data
- **WHEN** no student data is available
- **THEN** each stat card displays "0" or "--" as appropriate

### Requirement: Multi-dimensional filter toolbar
The page SHALL provide a toolbar with: name search input, class dropdown filter, barrier type dropdown filter (concept/reading/expression/all), and an "Add Student" button.

#### Scenario: Filter by class
- **WHEN** user selects a class from the dropdown
- **THEN** only students belonging to that class are displayed in the card grid

#### Scenario: Filter by barrier type
- **WHEN** user selects a barrier type from the dropdown
- **THEN** only students whose dominant barrier matches the selection are displayed

#### Scenario: Search by name
- **WHEN** user types characters in the search input
- **THEN** student cards are filtered in real-time by name substring match

### Requirement: Student card grid layout
The page SHALL render students as a responsive card grid (CSS Grid, `repeat(auto-fill, minmax(240px, 1fr))`) instead of a data table. Each card SHALL display: avatar initial letter, full name, class name, dominant barrier type with color-coded tag, exercises completed count, and last activity date.

#### Scenario: Card grid renders with data
- **WHEN** student list is loaded
- **THEN** cards are displayed in a grid with at least 3 cards per row on desktop

#### Scenario: Card grid single column on narrow screens
- **WHEN** viewport width is below 600px
- **THEN** cards render in a single column

#### Scenario: Empty state
- **WHEN** no students match current filters
- **THEN** an empty state message is displayed with appropriate copy

#### Scenario: Card click opens detail drawer
- **WHEN** user clicks a student card
- **THEN** the student detail drawer opens with that student's information

### Requirement: Pagination
The page SHALL paginate student cards with a configurable page size (default 12 per page) and display page navigation controls.

#### Scenario: Navigate between pages
- **WHEN** student count exceeds page size
- **THEN** pagination controls are displayed and functional

#### Scenario: Filter resets page
- **WHEN** user changes a filter
- **THEN** pagination resets to page 1

### Requirement: Mock data fallback
The page SHALL display mock/demo data when the API returns no results or fails, with a visible "MOCK · 演示数据" badge.

#### Scenario: Mock data activates on API failure
- **WHEN** API calls for students fail or return empty
- **THEN** mock student data is rendered and the mock badge is visible
