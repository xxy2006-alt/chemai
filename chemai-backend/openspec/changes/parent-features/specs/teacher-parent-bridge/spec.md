## ADDED Requirements

### Requirement: Agent generates parent report preview

The `generate_parent_report` Agent tool SHALL accept `student_name` or `student_id`, aggregate diagnosis and practice data, and return a formatted report preview in the chat. The teacher SHALL be able to request modifications before sending.

#### Scenario: Teacher generates report for named student
- **WHEN** teacher says "把李世睿的学习报告发给家长" in Agent Chat
- **THEN** Agent calls `generate_parent_report(student_name="李世睿")` and a report preview is displayed in chat with edit/confirm/cancel options

#### Scenario: Teacher modifies report via chat
- **WHEN** report preview is shown and teacher says "把盐类水解部分改温和一点"
- **THEN** Agent updates the report content and re-displays the preview

### Requirement: Agent sends confirmed report to parent

The `send_report_to_parent` Agent tool SHALL look up the student's bound parent, create a ParentNotification with the confirmed report, and return a confirmation message.

#### Scenario: Report sent successfully
- **WHEN** teacher confirms and says "发吧" after preview
- **THEN** Agent calls `send_report_to_parent(student_id, report_data)`, a notification is created, and "已发送给李世睿家长(李建国)" is displayed

#### Scenario: No parent bound
- **WHEN** student has no bound parent
- **THEN** Agent returns an error: "该学生未绑定家长，无法发送"

### Requirement: Parent receives report notification

When a report is sent, the parent SHALL see a notification in their messages tab. Clicking a `weekly_report` type notification SHALL open the report panel.

#### Scenario: Parent sees new report notification
- **WHEN** teacher sends a report
- **THEN** parent's notification list shows an unread `weekly_report` notification

#### Scenario: Parent opens report from notification
- **WHEN** parent clicks a `weekly_report` notification
- **THEN** the full report panel opens with the report content
