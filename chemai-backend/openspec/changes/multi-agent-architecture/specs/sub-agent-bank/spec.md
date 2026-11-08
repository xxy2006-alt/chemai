## ADDED Requirements

### Requirement: Bank manager lists and deletes exam banks
The bank_manager sub-agent SHALL have access to list_banks and delete_bank tools.

#### Scenario: List all exam banks
- **WHEN** bank_manager is queried with "列出所有题库"
- **THEN** it invokes list_banks and returns bank list

#### Scenario: Delete exam bank with approval
- **WHEN** bank_manager is queried with "删除题库 qset_001"
- **THEN** it invokes request_approval first, then delete_bank after approval

### Requirement: Bank manager requires approval for delete
The bank_manager SHALL have request_approval tool and require approval before delete_bank.

#### Scenario: Delete blocked without approval
- **WHEN** bank_manager attempts delete_bank without prior approval
- **THEN** the call is blocked with requires_approval_blocked=True

#### Scenario: Delete succeeds after approval
- **WHEN** request_approval is called, then delete_bank
- **THEN** delete_bank executes and returns deleted result
