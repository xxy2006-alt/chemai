## ADDED Requirements

### Requirement: Playwright browser tools return structured JSON
Each browser tool SHALL return JSON with operation-specific fields, not raw HTML.

#### Scenario: browse_navigate returns structured result
- **WHEN** browse_navigate(url="https://example.com") succeeds
- **THEN** return JSON with title, url, and text fields (text truncated to 8000 chars)

#### Scenario: browse_click returns before/after state
- **WHEN** browse_click(selector=".next-page") succeeds
- **THEN** return JSON with selector, before_url, after_url, and title

### Requirement: Browser pool is concurrency-safe
The browser pool SHALL use asyncio.Lock to serialize page access.

#### Scenario: Concurrent access serialized
- **WHEN** two requests invoke browser tools simultaneously
- **THEN** the second request waits for the first to release the lock

### Requirement: Browser pool auto-cleans up
The browser pool SHALL close browser instance after 60s idle.

#### Scenario: Cleanup after idle
- **WHEN** no browser tools have been called for 60 seconds
- **THEN** next call creates a fresh browser instance

### Requirement: All browser operations have timeout
Every browser operation SHALL enforce a 30-second timeout.

#### Scenario: Navigation timeout
- **WHEN** browse_navigate takes more than 30 seconds
- **THEN** return JSON with error and timeout=True
