## ADDED Requirements

### Requirement: Parent login returns JWT token

The `POST /api/parent/login` endpoint SHALL generate and return a JWT access token using the same `create_access_token()` function used by teacher and student logins.

#### Scenario: Successful parent login
- **WHEN** parent posts valid credentials to `/api/parent/login`
- **THEN** response includes `token` (JWT access token), `refresh_token`, `parent_id`, `name`, `role`

#### Scenario: Token works for subsequent API calls
- **WHEN** parent makes API calls with `Authorization: Bearer <token>`
- **THEN** auth middleware accepts the token and allows the request

### Requirement: Parent API routes are publicly accessible for login

The prefix `/api/parent/` SHALL be added to `PUBLIC_PREFIXES` in `app/main.py` so that unauthenticated login requests are not blocked by the auth middleware.

#### Scenario: Login request reaches the endpoint
- **WHEN** client sends POST to `/api/parent/login` without Authorization header
- **THEN** the request reaches the login handler (not blocked with 401)
