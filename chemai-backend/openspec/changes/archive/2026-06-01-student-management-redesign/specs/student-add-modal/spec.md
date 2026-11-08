## ADDED Requirements

### Requirement: Add student button
The student management toolbar SHALL include an "Add Student" button that opens the add student modal.

#### Scenario: Button visible and clickable
- **WHEN** page renders
- **THEN** the add student button is displayed in the toolbar

### Requirement: Add student modal
The add student modal SHALL support two modes: manual entry (name + class dropdown) and invite code generation. The modal SHALL include form validation (name required, class required).

#### Scenario: Manual entry mode
- **WHEN** user opens the add student modal
- **THEN** name input and class dropdown are displayed as the default view

#### Scenario: Validation prevents empty submission
- **WHEN** user clicks submit with empty name or no class selected
- **THEN** an inline validation message is shown and submission is blocked

#### Scenario: Successful submission
- **WHEN** user fills in name and selects a class, then clicks submit
- **THEN** the API is called to create the student, the modal closes, and the student list refreshes

#### Scenario: Invite code mode
- **WHEN** user switches to invite code tab/mode
- **THEN** an invite code is generated and displayed for sharing

#### Scenario: Modal closes
- **WHEN** user clicks cancel, the close button, or the backdrop
- **THEN** the modal closes without making changes
