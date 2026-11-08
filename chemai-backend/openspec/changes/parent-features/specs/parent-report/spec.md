## ADDED Requirements

### Requirement: Parent sees complete five-section learning report

The parent report tab SHALL display a comprehensive report with five sections: learning overview (practice count, accuracy, streak), progress trends (this week vs last week), knowledge point mastery (with proficiency levels), learning characteristics (barrier analysis in plain language), and family suggestions.

#### Scenario: Report loads with all sections
- **WHEN** parent opens the report tab for a bound child
- **THEN** all five sections are visible with data populated from the student's records

#### Scenario: Bound/unbound button reflects state
- **WHEN** parent has a bound child
- **THEN** the header shows the child's name initial and clicking shows unbind/rebind options
- **WHEN** parent has no bound child
- **THEN** the header shows a "bind" button

### Requirement: AI summary per report section

Each report section SHALL have an "AI总结" button. When clicked, the frontend SHALL call `POST /api/parent/child/{sid}/report/ai-summary` with the section name and data, and display the returned summary below the button.

#### Scenario: AI summary generated for knowledge points
- **WHEN** parent clicks "AI总结" under the knowledge points section
- **THEN** a 2-3 sentence summary in plain Chinese appears below the button within 5 seconds

#### Scenario: AI summary re-generated on second click
- **WHEN** parent clicks "AI总结" again after a summary is already shown
- **THEN** a new summary is generated and replaces the previous one

### Requirement: AI summary API endpoint

The endpoint `POST /api/parent/child/{student_id}/report/ai-summary` SHALL accept `{section, data}` and return a DeepSeek-generated 2-3 sentence summary in plain Chinese suitable for 40-55 year old parents.

#### Scenario: Valid summary request
- **WHEN** POST with valid section and data
- **THEN** returns `{success: true, summary: "..."}` within 10 seconds
