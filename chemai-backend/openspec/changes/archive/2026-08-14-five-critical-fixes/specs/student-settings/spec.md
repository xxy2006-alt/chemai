## ADDED Requirements

### Requirement: Student can view and change password

The student settings panel SHALL provide a password change form with current password, new password, and confirm password fields.

#### Scenario: Successful password change
- **WHEN** student enters correct current password and matching new password
- **THEN** password is updated and a success message is shown

#### Scenario: Incorrect current password
- **WHEN** student enters wrong current password
- **THEN** an error message "当前密码错误" is shown

### Requirement: Student can view bind code

The student settings panel SHALL display the student's bind code (6-digit code used by parents to link accounts).

#### Scenario: Bind code displayed
- **WHEN** student opens settings panel
- **THEN** the 6-digit bind code is visible with a copy hint

### Requirement: Student can view personal info

The student settings panel SHALL display read-only personal information: name, student ID, class, and grade.

#### Scenario: Info displayed
- **WHEN** student opens settings panel
- **THEN** name, student ID, class, and grade are shown (non-editable)

### Requirement: About section

The student settings panel SHALL include an about section showing app version and description.

#### Scenario: About info visible
- **WHEN** student scrolls to the about section
- **THEN** app name "智辅化学", version, and a brief description are displayed
