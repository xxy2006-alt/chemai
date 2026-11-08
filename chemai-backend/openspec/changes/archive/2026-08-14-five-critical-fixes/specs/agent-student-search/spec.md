## ADDED Requirements

### Requirement: Agent can find students by name via show_students

The `show_students` tool SHALL accept a `student_name` parameter. When provided, the tool SHALL perform LIKE-based fuzzy search on the students table and return matching student results, bypassing class-based filtering.

#### Scenario: Agent searches for student by Chinese name
- **WHEN** Agent calls `show_students(student_name="李雨萱")`
- **THEN** the tool returns all students whose name matches `%李雨萱%`, with student_id, name, barrier_type, and class info

#### Scenario: No match found
- **WHEN** Agent calls `show_students(student_name="不存在的名字")`
- **THEN** the tool returns a message indicating no students were found

#### Scenario: Backward compatible without student_name
- **WHEN** Agent calls `show_students(class_id="class_2025_1")` without student_name
- **THEN** the tool behaves exactly as before, listing students in the class
