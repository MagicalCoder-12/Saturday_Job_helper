# Hermes AI Job Application Agent Implementation Plan

> **For Hermes:** Do not start implementation until Ajith has reviewed and approved this PLAN.md. Use subagent-driven-development skill to implement this plan task-by-task after approval.

**Goal:** Build an AI-powered job discovery and application assistant named Hermes that discovers relevant jobs, scores fit against Ajith's profile, generates tailored application documents, sends Telegram approval requests, and applies only after explicit human approval.

**Architecture:** Hermes is a modular Python system with independent services for profile ingestion, job discovery, extraction, scoring, document generation, Telegram approval workflow, application automation, scheduling, and reporting. The system uses SQLite first, with repository interfaces designed so PostgreSQL can replace SQLite later without changing business logic. Browser automation is isolated behind Playwright adapters and all application submission actions are gated by explicit approval state checks.

**Tech Stack:** Python, Playwright, LangGraph, SQLite, future PostgreSQL, Groq API as primary LLM provider, LM Studio local fallback with `google/gemma-4-e4b`, Telegram Bot API, python-docx, Microsoft Word PDF conversion, structured logging, cron/APScheduler-style local scheduling, pytest.

---

## 1. Non-Negotiable Rules

1. Hermes must NEVER submit an application unless the job status is `Approved` and the approval was explicitly triggered by Ajith through Telegram or another verified approval interface.
2. Hermes must support manual application fallback for sites that block or complicate automation.
3. Hermes must log every important decision and action.
4. Hermes must preserve all generated resume and cover letter versions.
5. Hermes must treat credentials as external configuration, never hard-coded values.
6. Hermes must be usable on a personal laptop with startup-triggered scans and scheduled runs.
7. Hermes must be modular enough to add more job boards, LLM providers, notification channels, and databases later.
8. Before Phase 2 implementation begins, required credentials and configuration must be confirmed.
9. Hermes must enforce daily and per-run caps to prevent notification spam and accidental high-volume application bursts.

---

## 2. Required Credentials and Configuration Before Implementation

Implementation must not begin until these are confirmed:

### 2.1 Required for Phase 2 Core Implementation

- Python version target, recommended: Python 3.11+
- Project location on disk
- Existing resume source file path
- Portfolio URL
- GitHub username or repository list
- Career preferences:
  - Preferred roles
  - Preferred locations
  - Remote/hybrid/on-site preference
  - Minimum salary if any
  - Experience level target
  - Excluded companies or industries if any

### 2.2 Required for AI Features

LLM provider plan:

- Primary provider: Groq API.
- Fallback provider: LM Studio local server.
- Fallback model: `google/gemma-4-e4b`.
- If Groq fails because of network, rate limits, provider downtime, or invalid response format, Hermes should retry according to policy and then fallback to LM Studio.
- Credentials must still be stored as environment variables, never hard-coded.

Required LLM configuration:

- Groq API key status
- Groq model for matching/scoring
- Groq model for resume and cover letter generation
- LM Studio base URL, usually `http://localhost:1234/v1`
- LM Studio fallback model name: `google/gemma-4-e4b`
- Token/cost limits per run
- Whether generated documents can use cloud LLM APIs

### 2.3 Required for Telegram Integration

- Telegram bot token
- Ajith's Telegram chat ID
- Whether commands should be restricted to a single chat/user
- Whether generated PDFs should be sent directly through Telegram
- Daily and per-run caps, recommended defaults:
  - `max_applications_per_day: 10`
  - `max_alerts_per_run: 20`

### 2.4 Optional Email Configuration

Only required if email support is enabled:

- SMTP provider
- SMTP username
- SMTP app password or token
- Sender email address
- Recipient email address

### 2.5 Optional Application Automation Credentials

Only required for automated application submission:

- Job board accounts that Ajith wants Hermes to use
- Whether login sessions should be persisted in Playwright storage state
- Sites allowed for automation
- Sites forbidden from automation
- Whether CAPTCHA or MFA should always trigger manual fallback

---

## 3. High-Level System Architecture

### 3.1 Logical Components

1. Profile Intelligence Service
   - Parses Ajith's resume, project list, GitHub repositories, portfolio, skills, experience, and career preferences.
   - Produces a normalized candidate profile used by the scoring engine and document generator.

2. Job Discovery Service
   - Searches supported job sources.
   - Produces raw job postings with source metadata.
   - Deduplicates by company, title, canonical URL, and description fingerprint.

3. Job Extraction Service
   - Normalizes job data into a consistent schema.
   - Extracts title, company, description, required skills, experience, salary, location, remote status, and application URL.

4. Matching Engine
   - Scores compatibility using skill overlap, project relevance, experience relevance, education relevance, tech stack match, location preference, and remote preference.
   - Produces match score, confidence score, explanation, rejection reason if applicable, and recommended next action.

5. Document Generation Service
   - Creates ATS-friendly tailored resumes.
   - Creates cover letters only when required or requested.
   - Exports generated documents as PDF and stores metadata in the database.

6. Telegram Interface
   - Sends job alerts, summaries, generated document links/files, errors, and status updates.
   - Handles commands:
     - `/apply <job_id>`
     - `/reject <job_id>`
     - `/details <job_id>`
     - `/resume <job_id>`
     - `/coverletter <job_id>`
     - `/status`

7. Approval Gate
   - Central safety layer that blocks all application submissions unless the job is approved.
   - Validates approval state immediately before any submission attempt.

8. Application Automation Service
   - Uses Playwright adapters for supported application flows.
   - Falls back to manual instructions when automation is not safe or not supported.

9. Scheduler and Startup Trigger
   - Runs discovery on startup if last scan was more than 4 hours ago.
   - Runs preferred scans at 10:05 AM and 5:05 PM.
   - Sends daily summary around 8:30 PM.

10. Logging and Monitoring Service
    - Writes structured logs for searches, matching decisions, document generation, Telegram messages, approval actions, application attempts, and errors.

---

## 4. Recommended Folder Structure

```text
hermes-job-agent/
├── PLAN.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── config/
│   ├── settings.example.yaml
│   ├── job_sources.yaml
│   ├── scoring.yaml
│   └── prompts/
│       ├── profile_summary.md
│       ├── job_extraction.md
│       ├── job_scoring.md
│       ├── resume_tailoring.md
│       └── cover_letter.md
├── data/
│   ├── input/
│   │   ├── resume/
│   │   └── profile/
│   ├── generated/
│   │   ├── resumes/
│   │   ├── cover_letters/
│   │   └── reports/
│   ├── browser_state/
│   └── hermes.sqlite3
├── logs/
│   ├── app.log
│   ├── jobs.log
│   ├── telegram.log
│   ├── applications.log
│   └── errors.log
├── src/
│   └── hermes_job_agent/
│       ├── __init__.py
│       ├── main.py
│       ├── cli.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py
│       │   └── secrets.py
│       ├── database/
│       │   ├── __init__.py
│       │   ├── connection.py
│       │   ├── migrations.py
│       │   ├── schema.sql
│       │   └── repositories/
│       │       ├── jobs.py
│       │       ├── documents.py
│       │       ├── approvals.py
│       │       ├── job_rejections.py
│       │       ├── runs.py
│       │       └── logs.py
│       ├── profile/
│       │   ├── __init__.py
│       │   ├── resume_parser.py
│       │   ├── github_analyzer.py
│       │   ├── portfolio_analyzer.py
│       │   ├── preferences.py
│       │   └── profile_builder.py
│       ├── discovery/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── orchestrator.py
│       │   ├── deduplication.py
│       │   └── sources/
│       │       ├── linkedin.py
│       │       ├── indeed.py
│       │       ├── wellfound.py
│       │       ├── greenhouse.py
│       │       ├── lever.py
│       │       └── company_pages.py
│       ├── extraction/
│       │   ├── __init__.py
│       │   ├── job_parser.py
│       │   ├── salary_parser.py
│       │   ├── skill_extractor.py
│       │   └── normalizer.py
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── llm_client.py
│       │   ├── langgraph_workflows.py
│       │   ├── structured_outputs.py
│       │   └── prompts.py
│       ├── matching/
│       │   ├── __init__.py
│       │   ├── scorer.py
│       │   ├── explanation.py
│       │   ├── quality_filter.py
│       │   └── thresholds.py
│       ├── documents/
│       │   ├── __init__.py
│       │   ├── resume_tailor.py
│       │   ├── cover_letter_generator.py
│       │   ├── ats_formatter.py
│       │   ├── pdf_exporter.py
│       │   └── storage.py
│       ├── telegram/
│       │   ├── __init__.py
│       │   ├── bot.py
│       │   ├── commands.py
│       │   ├── message_templates.py
│       │   └── auth.py
│       ├── approvals/
│       │   ├── __init__.py
│       │   ├── approval_gate.py
│       │   └── state_machine.py
│       ├── applications/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── orchestrator.py
│       │   ├── manual_fallback.py
│       │   └── adapters/
│       │       ├── greenhouse.py
│       │       ├── lever.py
│       │       └── generic_form.py
│       ├── scheduler/
│       │   ├── __init__.py
│       │   ├── startup.py
│       │   ├── jobs.py
│       │   └── summary.py
│       ├── notifications/
│       │   ├── __init__.py
│       │   ├── telegram_notifier.py
│       │   └── email_notifier.py
│       ├── logging_utils/
│       │   ├── __init__.py
│       │   ├── logger.py
│       │   └── audit.py
│       └── utils/
│           ├── __init__.py
│           ├── time.py
│           ├── hashing.py
│           ├── urls.py
│           └── text.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── e2e/
└── docs/
    ├── architecture.md
    ├── telegram_commands.md
    ├── database.md
    ├── job_sources.md
    ├── automation_policy.md
    └── manual_application_playbook.md
```

---

## 5. Database Design

Initial database: SQLite.
Future upgrade path: PostgreSQL using the same repository interface.

### 5.1 Entity Relationship Overview

```text
candidate_profiles 1 ── * profile_snapshots
runs               1 ── * discovered_jobs
jobs               1 ── * job_scores
jobs               1 ── * documents
jobs               1 ── * approvals
jobs               1 ── * job_rejections
jobs               1 ── * application_attempts
jobs               1 ── * telegram_messages
runs               1 ── * logs
```

### 5.2 Tables

#### candidate_profiles

Stores stable candidate identity and baseline profile metadata.

Fields:

- id INTEGER PRIMARY KEY
- full_name TEXT NOT NULL
- email TEXT
- phone TEXT
- location TEXT
- portfolio_url TEXT
- github_url TEXT
- linkedin_url TEXT
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

#### profile_snapshots

Stores versioned profile summaries used for matching.

Fields:

- id INTEGER PRIMARY KEY
- candidate_profile_id INTEGER NOT NULL
- resume_source_path TEXT
- resume_text TEXT
- normalized_profile_json TEXT NOT NULL
- skills_json TEXT NOT NULL
- projects_json TEXT NOT NULL
- experience_json TEXT NOT NULL
- preferences_json TEXT NOT NULL
- created_at TEXT NOT NULL
- FOREIGN KEY(candidate_profile_id) REFERENCES candidate_profiles(id)

#### runs

Tracks discovery, summary, document, and application runs.

Fields:

- id INTEGER PRIMARY KEY
- run_type TEXT NOT NULL
- status TEXT NOT NULL
- started_at TEXT NOT NULL
- finished_at TEXT
- jobs_found_count INTEGER DEFAULT 0
- errors_count INTEGER DEFAULT 0
- metadata_json TEXT

Run metadata should include cap-related counters where relevant:

- alerts_sent_count
- applications_submitted_count
- applications_blocked_by_daily_cap_count
- jobs_suppressed_by_alert_cap_count

Allowed run_type values:

- startup_scan
- scheduled_scan
- manual_scan
- daily_summary
- application_attempt
- document_generation

Allowed status values:

- running
- completed
- failed
- partial

#### jobs

Stores normalized job postings.

Fields:

- id INTEGER PRIMARY KEY
- external_id TEXT
- source TEXT NOT NULL
- company TEXT NOT NULL
- position TEXT NOT NULL
- url TEXT NOT NULL UNIQUE
- canonical_url TEXT
- application_url TEXT
- location TEXT
- remote_type TEXT
- salary_text TEXT
- salary_min INTEGER
- salary_max INTEGER
- currency TEXT
- experience_required TEXT
- description TEXT NOT NULL
- skills_required_json TEXT
- employment_type TEXT
- discovered_at TEXT NOT NULL
- updated_at TEXT NOT NULL
- status TEXT NOT NULL
- description_hash TEXT NOT NULL
- raw_payload_json TEXT

Allowed status values:

- Discovered
- Awaiting Approval
- Approved
- Rejected
- Applied
- Manual Apply Required
- Failed

#### job_scores

Stores matching results and explanations.

Fields:

- id INTEGER PRIMARY KEY
- job_id INTEGER NOT NULL
- profile_snapshot_id INTEGER NOT NULL
- match_score INTEGER NOT NULL
- confidence_score INTEGER NOT NULL
- skill_overlap_score INTEGER NOT NULL
- experience_overlap_score INTEGER NOT NULL
- education_relevance_score INTEGER NOT NULL
- project_relevance_score INTEGER NOT NULL
- tech_stack_score INTEGER NOT NULL
- location_score INTEGER NOT NULL
- remote_score INTEGER NOT NULL
- explanation TEXT NOT NULL
- rejection_reason TEXT
- scoring_model TEXT
- created_at TEXT NOT NULL
- FOREIGN KEY(job_id) REFERENCES jobs(id)
- FOREIGN KEY(profile_snapshot_id) REFERENCES profile_snapshots(id)

#### documents

Stores generated resumes and cover letters.

Fields:

- id INTEGER PRIMARY KEY
- job_id INTEGER NOT NULL
- document_type TEXT NOT NULL
- version INTEGER NOT NULL
- source_format TEXT NOT NULL
- file_path TEXT NOT NULL
- pdf_path TEXT
- prompt_version TEXT
- generation_model TEXT
- generation_reason TEXT
- diff_text TEXT
- diff_json TEXT
- telegram_diff_sent_at TEXT
- created_at TEXT NOT NULL
- FOREIGN KEY(job_id) REFERENCES jobs(id)

Allowed document_type values:

- resume
- cover_letter
- report

#### approvals

Stores human approval and rejection decisions.

Fields:

- id INTEGER PRIMARY KEY
- job_id INTEGER NOT NULL
- action TEXT NOT NULL
- source TEXT NOT NULL
- actor_chat_id TEXT
- reason TEXT
- created_at TEXT NOT NULL
- FOREIGN KEY(job_id) REFERENCES jobs(id)

Allowed action values:

- approve
- reject
- request_details
- request_resume
- request_cover_letter

#### job_rejections

Stores structured rejection reasons so Hermes can learn Ajith's negative preferences over time and avoid repeatedly recommending poor-fit jobs.

Fields:

- id INTEGER PRIMARY KEY
- job_id INTEGER NOT NULL
- rejection_source TEXT NOT NULL
- rejection_category TEXT NOT NULL
- rejection_reason TEXT NOT NULL
- freeform_note TEXT
- actor_chat_id TEXT
- confidence_score INTEGER
- created_at TEXT NOT NULL
- FOREIGN KEY(job_id) REFERENCES jobs(id)

Allowed rejection_source values:

- user
- matching_engine
- automation_policy
- expired_or_invalid

Allowed rejection_category values:

- salary_too_low
- not_remote
- wrong_location
- wrong_tech_stack
- too_senior
- too_junior
- not_interested
- company_mismatch
- spam_or_training_upsell
- expired
- invalid_application_url
- duplicate
- other

Learning use:

- User rejections from Telegram should be stored here in structured form.
- Automatic low-score filtering should also store a rejection entry when the reason is clear.
- Future scoring should use aggregated rejection patterns as negative preference signals.
- Example: if Ajith repeatedly rejects non-remote roles, remote preference weight should increase or non-remote jobs should be filtered earlier.
- Example: if Ajith rejects a tech stack repeatedly, that stack should be de-prioritized in future matching explanations and alerts.

#### application_attempts

Tracks automated and manual application attempts.

Fields:

- id INTEGER PRIMARY KEY
- job_id INTEGER NOT NULL
- attempt_type TEXT NOT NULL
- status TEXT NOT NULL
- adapter_name TEXT
- started_at TEXT NOT NULL
- finished_at TEXT
- submitted_at TEXT
- error_message TEXT
- confirmation_text TEXT
- confirmation_url TEXT
- metadata_json TEXT
- FOREIGN KEY(job_id) REFERENCES jobs(id)

Allowed attempt_type values:

- automated
- manual_required

Allowed status values:

- pending
- running
- submitted
- manual_required
- failed
- blocked

#### daily_limits

Stores per-day alert and application cap usage.

Fields:

- id INTEGER PRIMARY KEY
- date TEXT NOT NULL UNIQUE
- max_applications_per_day INTEGER NOT NULL
- max_alerts_per_run INTEGER NOT NULL
- applications_submitted_count INTEGER DEFAULT 0
- alerts_sent_count INTEGER DEFAULT 0
- applications_blocked_count INTEGER DEFAULT 0
- alerts_suppressed_count INTEGER DEFAULT 0
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

Default cap values:

- `max_applications_per_day: 10`
- `max_alerts_per_run: 20`

Rules:

- Telegram alerts must stop or batch once `max_alerts_per_run` is reached.
- Automated submissions must stop once `max_applications_per_day` is reached.
- If Ajith approves more jobs after the daily application cap is reached, Hermes should mark them as approved but queue them for the next day or send manual instructions, depending on configuration.
- Daily summary must include cap usage and suppressed/queued counts.

#### telegram_messages

Tracks outbound and inbound Telegram interactions.

Fields:

- id INTEGER PRIMARY KEY
- job_id INTEGER
- telegram_message_id TEXT
- chat_id TEXT NOT NULL
- direction TEXT NOT NULL
- command TEXT
- message_text TEXT NOT NULL
- status TEXT NOT NULL
- created_at TEXT NOT NULL
- FOREIGN KEY(job_id) REFERENCES jobs(id)

Allowed direction values:

- inbound
- outbound

#### system_events

General audit log table.

Fields:

- id INTEGER PRIMARY KEY
- run_id INTEGER
- level TEXT NOT NULL
- event_type TEXT NOT NULL
- message TEXT NOT NULL
- metadata_json TEXT
- created_at TEXT NOT NULL
- FOREIGN KEY(run_id) REFERENCES runs(id)

---

## 6. Agent Workflow

### 6.1 Full Job Discovery Cycle

```text
START
  │
  ▼
Load configuration and validate required secrets
  │
  ▼
Create run record
  │
  ▼
Build or refresh candidate profile snapshot
  │
  ▼
Search enabled job sources
  │
  ▼
Extract and normalize job postings
  │
  ▼
Deduplicate against existing jobs
  │
  ▼
Score each new or updated job
  │
  ├── score below reject threshold ──► Store as Discovered or reject internally with reason
  │
  └── score above alert threshold ───► Set status Awaiting Approval
                                      │
                                      ▼
                              Send Telegram notification with score, reason, and commands
                                      │
                                      ▼
                              Wait for Ajith approval
                                      │
                                      ▼
                              Finish run and log summary
END
```

Important cost-control rule: discovery must not generate tailored resumes or cover letters. Documents are generated only after explicit approval through `/apply <job_id>` or an explicit document request such as `/resume <job_id>` or `/coverletter <job_id>`.

### 6.2 Telegram Approval Workflow

```text
Telegram command received
  │
  ▼
Authenticate chat/user
  │
  ├── unauthorized ─► Ignore or send unauthorized response
  │
  ▼
Parse command and job_id
  │
  ├── /details ───────► Send full job details and match explanation
  ├── /resume ────────► Generate or send tailored resume PDF plus resume diff
  ├── /coverletter ───► Send existing cover letter or generate on demand
  ├── /reject ────────► Record structured rejection reason, set status Rejected
  ├── /status ────────► Send aggregate status summary
  └── /apply ─────────► Record approval, set status Approved
                         │
                         ▼
                 Generate tailored resume and resume diff if missing
                         │
                         ▼
                 Generate cover letter only if required or requested
                         │
                         ▼
                 Send generated document summary and resume diff to Telegram
                         │
                         ▼
                 Application orchestrator checks approval gate
                         │
                         ├── automation supported ─► Attempt automated submission
                         │                             │
                         │                             ├── success ─► status Applied
                         │                             └── failure ─► status Manual Apply Required or Failed
                         │
                         └── automation unsupported ─► status Manual Apply Required
                                                       Send link + docs + instructions
```

### 6.3 Approval Gate

The approval gate must run immediately before any application submission.

Rules:

1. Job status must be `Approved`.
2. At least one approval record must exist for the job.
3. Approval must come from an authorized Telegram chat/user.
4. Job must not already be `Applied`.
5. Job must not be `Rejected`.
6. Required resume document must exist, generating it after approval if missing.
7. Resume diff must be stored and sent to Telegram before application submission when a tailored resume is generated.
8. Application URL must exist.
9. If automation is not explicitly supported for the source, return manual fallback.

### 6.4 Startup Trigger

```text
Hermes process starts
  │
  ▼
Read last completed discovery run time
  │
  ├── no previous run ───────────────► Run full discovery cycle
  │
  ├── last run older than 4 hours ───► Run full discovery cycle
  │
  └── last run within 4 hours ───────► Skip immediate scan and wait for schedule
```

### 6.5 Scheduled Runs

Preferred local laptop schedule:

- 10:05 AM: full discovery cycle
- 5:05 PM: full discovery cycle
- 8:30 PM: daily summary

Laptop usage windows:

- 10:00 AM to 1:00 PM
- 5:00 PM to 9:00 PM

If the laptop is asleep during a preferred time, startup trigger catches up if last run is older than 4 hours.

### 6.6 Daily and Per-Run Limits

Default limits:

```yaml
max_applications_per_day: 10
max_alerts_per_run: 20
```

Workflow:

```text
Before sending job alert
  ↓
Check alerts sent in current run
  ↓
If below max_alerts_per_run → send alert
  ↓
If cap reached → store job as Awaiting Approval but suppress immediate alert or include in batched summary

Before automated application submission
  ↓
Check applications submitted today
  ↓
If below max_applications_per_day → continue approval-gated application flow
  ↓
If cap reached → do not submit; mark as Approved but queued/manual depending on config
```

Reason: if Hermes finds 120 matching jobs, Ajith should not receive 120 Telegram notifications or accidentally submit dozens of approved jobs in one evening.

---

## 7. API and Interface Design

### 7.1 Internal Python Service Interfaces

#### JobSourceAdapter

Purpose: Standard interface for job boards and company pages.

Methods:

- `search(query, location, filters) -> list[RawJobPosting]`
- `fetch_details(raw_job) -> RawJobPosting`
- `source_name -> str`
- `supports_application_automation -> bool`

Adapters:

- LinkedIn adapter
- Indeed adapter
- Wellfound adapter
- Greenhouse adapter
- Lever adapter
- Company careers adapter
- Generic web job page adapter

#### LLMClient

Purpose: Abstract Groq and LM Studio calls behind one OpenAI-compatible interface.

Methods:

- `complete(prompt, schema=None) -> LLMResponse`
- `structured_complete(prompt, schema) -> dict`
- `get_provider_name() -> str`
- `get_model_name() -> str`

Provider order:

1. Try Groq API first.
2. If Groq fails after configured retries, fallback to LM Studio at the configured local OpenAI-compatible endpoint.
3. Use LM Studio model `google/gemma-4-e4b` for fallback generation/scoring.
4. Log the provider used for every scoring and document-generation event.

#### MatchingEngine

Purpose: Score jobs against profile snapshots.

Methods:

- `score(job, profile_snapshot) -> JobScore`
- `should_alert(score) -> bool`
- `should_reject(score) -> bool`

#### DocumentGenerator

Purpose: Generate tailored documents.

Methods:

- `generate_resume(job, profile_snapshot) -> DocumentRecord`
- `generate_cover_letter(job, profile_snapshot) -> DocumentRecord`
- `edit_resume_docx(job, profile_snapshot, source_docx) -> DocumentRecord`
- `export_pdf_with_word(document) -> Path`

Required resume document pipeline:

```text
Generate tailored content
  ↓
python-docx edits the Word resume template
  ↓
Microsoft Word converts DOCX to PDF
  ↓
Telegram sends PDF
```

The preferred source resume for formatting is a `.docx` Word file. If only the extracted Markdown profile is available, Hermes can use it for profile intelligence, but Ajith must provide the original `.docx` resume before faithful Word-based editing and PDF export can be implemented.

#### ApprovalGate

Purpose: Safety gate before application.

Methods:

- `can_apply(job_id) -> ApprovalDecision`
- `assert_can_apply(job_id) -> None`

#### ApplicationAdapter

Purpose: Automate submissions for supported sources.

Methods:

- `can_handle(job) -> bool`
- `apply(job, resume_path, cover_letter_path=None) -> ApplicationResult`

#### TelegramBot

Purpose: Notification and command interface.

Methods:

- `send_job_alert(job, score, documents)`
- `send_daily_summary(summary)`
- `send_error(error)`
- `handle_command(command_text, chat_id)`

### 7.2 Telegram Command API

#### /apply <job_id>

Behavior:

1. Verify authorized chat.
2. Verify job exists.
3. Set job status to `Approved`.
4. Record approval action.
5. Trigger application orchestrator.
6. Return one of:
   - automated application started
   - application submitted
   - manual application required
   - failed with reason

#### /reject <job_id>

Optional forms:

- `/reject <job_id>`
- `/reject <job_id> salary_too_low`
- `/reject <job_id> not_remote`
- `/reject <job_id> wrong_tech_stack`
- `/reject <job_id> not_interested`

Behavior:

1. Verify authorized chat.
2. Verify job exists.
3. Parse rejection category if provided.
4. If no category is provided, store `other` and optionally ask Ajith for a reason later.
5. Set job status to `Rejected`.
6. Record rejection action in `approvals` for audit history.
7. Record structured rejection pattern in `job_rejections` for learning.
8. Confirm rejection to Telegram.

#### /details <job_id>

Returns:

- Role
- Company
- Location
- Salary if available
- Match score
- Confidence score
- Explanation
- Required skills
- Application URL
- Current status

#### /resume <job_id>

Returns:

- Existing tailored resume if available
- If not available and job exists, generates resume and sends it

#### /coverletter <job_id>

Returns:

- Existing cover letter if available
- If not available, generates one on demand and sends it

#### /status

Returns:

- Total jobs discovered today
- Awaiting approval count
- Approved count
- Rejected count
- Applied count
- Manual apply required count
- Failed count
- Last scan time
- Next scheduled scan

---

## 8. Job Source Strategy

### 8.1 Phase 1 Supported Source Strategy

Start with the two most automation-friendly sources only:

1. Greenhouse boards
2. Lever boards

Company career pages with structured job links can be added after these two adapters are stable.

### 8.2 Later Source Strategy

Add sources gradually by complexity:

1. Phase 2 source expansion: Wellfound
2. Phase 3 source expansion: LinkedIn
3. Optional later expansion: Indeed and company-specific career pages

LinkedIn must not be part of the initial implementation because it is typically the most difficult platform for automation, login handling, rate limits, and bot detection. Treat LinkedIn as manual-fallback-first until a reliable adapter is proven.

### 8.3 Search Query Strategy

Queries should be generated from profile and preferences:

- Python Developer fresher remote India
- AI Engineer intern Python Hyderabad
- Machine Learning Engineer entry level India
- Data Scientist fresher Python TensorFlow
- Game Developer Unity Godot remote
- AI Data Science internship Hyderabad
- Backend Python Developer Flask FastAPI

### 8.4 Deduplication Strategy

Deduplicate using:

- Canonical URL
- Company + normalized title + location
- Description hash
- Application URL
- External source ID when available

---

## 9. Matching Engine Design

### 9.1 Score Components

Total match score: 0 to 100.

Recommended default weights:

- Skill overlap: 25%
- Technology stack match: 20%
- Project relevance: 20%
- Experience overlap: 15%
- Education relevance: 10%
- Location preference: 5%
- Remote preference: 5%

### 9.2 Confidence Score

Confidence score reflects data quality, not job suitability.

Factors:

- Full job description available
- Required skills explicitly listed
- Location clear
- Experience requirement clear
- Salary available
- Company and application URL verified

### 9.3 Thresholds

Initial suggested thresholds:

- 85 to 100: Excellent match, alert Ajith and wait for approval before generating documents
- 70 to 84: Good match, alert if enough daily capacity and wait for approval before generating documents
- 55 to 69: Store only unless specifically requested
- Below 55: Low priority or rejected internally

### 9.4 Rejection Rules

Reject or deprioritize jobs when:

- Experience requirement is far above target
- Mandatory skills have no overlap
- Location conflicts with preferences
- Role is unrelated to target career path
- Job appears expired
- Application URL is missing or invalid
- Posting looks like spam or training upsell

Every rejection with a clear reason should create a `job_rejections` record. This applies both to user-triggered rejections and automatic matching-engine rejections.

### 9.5 Learning From Rejections

Hermes should use rejection history as a feedback loop.

Examples:

- If many rejected jobs have category `salary_too_low`, salary filters should become stricter.
- If many rejected jobs have category `not_remote`, non-remote jobs should be penalized or filtered earlier.
- If many rejected jobs have category `wrong_tech_stack`, those technologies should lower the match score unless balanced by strong positives.
- If many rejected jobs have category `not_interested`, similar roles or companies should be de-prioritized.

Implementation rule:

- Rejection learning should start as transparent score adjustments, not hidden black-box behavior.
- Telegram `/details <job_id>` should mention when rejection history influenced the score.
- Rejection learning must never override explicit user approval.

---

## 10. Resume Customization Strategy

### 10.1 Resume Inputs

- Preferred base resume source: `.docx` Word resume template
- Current master resume source: `/home/ajith/ml_projects/Saturday_Job_helper/data/input/resume/Master_resume.docx`, provided by Ajith after combining game and ML resumes and adding recent internships
- Current stored profile source: `/home/ajith/ajith_resume_profile_updated.md`, an extracted Markdown profile used for profile intelligence and links
- Structured candidate profile
- Job description
- Matching explanation
- Project relevance map

### 10.2 Resume Tailoring Rules

1. Generate tailored resumes only after Ajith approves the job with `/apply <job_id>` or explicitly requests `/resume <job_id>`.
2. Keep ATS-friendly formatting.
3. Preserve truthful experience and project facts.
4. Reorder skills by job relevance.
5. Highlight matching projects.
6. Adjust project descriptions to emphasize relevant technologies and outcomes.
7. Do not invent employment history, credentials, metrics, or skills.
8. Export PDF for submission.
9. Store every generated version.
10. Generate and store a human-readable resume diff for every tailored resume.
11. Send the resume diff to Telegram before application submission.

### 10.3 Resume Diff

Hermes must show Ajith what changed in the tailored resume before applying.

The resume diff should include:

```text
Resume Changes for Job <job_id>

Added:
✓ Python
✓ FastAPI

Moved Higher:
✓ AI Projects
✓ Backend/API skills

Reworded:
✓ HackRx RAG project bullet aligned to retrieval and API requirements

Removed or De-emphasized:
✓ Unreal Engine
✓ Low-relevance game jam details
```

Diff categories:

- Added
- Moved Higher
- Reworded
- Removed or De-emphasized
- Unchanged Important Items

Rules:

1. The diff must be understandable in Telegram without opening the PDF.
2. The diff must not hide factual changes.
3. If no meaningful changes were made, say `No major resume changes; only formatting/export updated.`
4. Store the diff with the document record or in a linked resume diff table/file.
5. The application automation service must not submit until the tailored resume and diff have both been generated and sent, unless Ajith explicitly chooses manual-only application.

### 10.4 Resume Output Formats

Recommended:

- DOCX source/template for formatting fidelity
- DOCX tailored output generated with python-docx
- Markdown or JSON change summary for version control and generation traceability
- PDF final exported by Microsoft Word for submission

Stored resume chain:

```text
master_resume.docx
  ↓
tailored_resume.docx
  ↓
tailored_resume.pdf
```

Hermes must keep both the editable tailored DOCX and the exported PDF. If Word/PDF formatting breaks, the tailored DOCX remains available for manual editing and regeneration.

Required conversion flow:

```text
LLM generates tailored content
  ↓
python-docx applies edits to a copied DOCX resume template
  ↓
Microsoft Word converts DOCX to PDF
  ↓
Telegram sends PDF and resume diff
```

Implementation notes:

- On Windows, use Microsoft Word automation through COM if Hermes runs with access to the Windows host.
- On WSL, call a Windows-side helper script through `/mnt/c/...` or `powershell.exe` to run Word conversion.
- If Microsoft Word is unavailable, stop and report a blocker instead of silently using a lower-quality converter.
- The Markdown profile is not a replacement for the Word resume template; it is the structured knowledge source.

### 10.5 Resume File Naming

```text
data/generated/resumes/{job_id}_{company_slug}_{role_slug}_v{version}.pdf
```

Example:

```text
data/generated/resumes/123_xyz_python_developer_v1.pdf
```

---

## 11. Cover Letter Strategy

### 11.1 Generate Cover Letters Only When

- Job posting requires it
- Application form has a cover letter field
- Ajith requests `/coverletter <job_id>`

### 11.2 Cover Letter Rules

1. Keep concise and role-specific.
2. Use truthful project and experience references.
3. Avoid generic filler.
4. Mention company and role accurately.
5. Store generated versions.
6. Export PDF when needed.

---

## 12. Application Automation Strategy

### 12.1 Automation Levels

#### Level 0: Manual Only

Hermes sends:

- Application link
- Tailored resume
- Cover letter if available
- Instructions

#### Level 1: Assisted Automation

Hermes opens or prepares application form but requires Ajith to complete final submission.

#### Level 2: Automated Submission After Approval

Hermes fills and submits application only after approval and only for supported adapters.

### 12.2 Initial Automation Targets

Start with:

- Greenhouse
- Lever
- Simple company-hosted forms

Delay or manual fallback for:

- LinkedIn Easy Apply
- Indeed login-gated flows
- Sites with CAPTCHA
- Sites requiring MFA
- Sites requiring long custom questionnaires

### 12.3 Automation Safety Checks

Before submission:

1. Re-read job status from database.
2. Verify status is `Approved`.
3. Verify approval record exists.
4. Verify resume path exists.
5. Verify application URL domain matches expected source.
6. Verify no previous successful application exists.
7. If final page contains unexpected fields, stop and request manual action.

---

## 13. Scheduling and Runtime Strategy

### 13.1 Local Laptop Runtime

Hermes runs as a local Python process. Options:

1. CLI command run manually at startup.
2. OS startup task launching Hermes.
3. Lightweight background process during usage windows.

### 13.2 Startup Trigger

On every start:

- Read latest completed discovery run.
- If no scan or last scan older than 4 hours, run discovery.
- Otherwise wait for the next scheduled run.

### 13.3 Scheduled Jobs

- 10:05 AM: discovery scan
- 5:05 PM: discovery scan
- 8:30 PM: daily summary

### 13.4 Daily Summary Contents

Telegram summary:

- Jobs found
- Jobs approved
- Jobs rejected
- Jobs applied
- Pending approvals
- Manual apply required
- Failed attempts
- Errors encountered
- Top opportunities with scores

---

## 14. Logging and Observability

### 14.1 Log Categories

- Search logs
- Extraction logs
- Matching logs
- Document generation logs
- Telegram logs
- Approval logs
- Application attempt logs
- Error logs
- Scheduler logs

### 14.2 Structured Log Fields

Each log event should include:

- timestamp
- level
- event_type
- run_id
- job_id if applicable
- source if applicable
- message
- metadata_json

### 14.3 Error Reporting

Critical errors should be sent to Telegram:

- Missing credentials
- Job source failures
- LLM provider failures
- PDF generation failures
- Telegram delivery failures
- Application automation failures
- Database errors

---

## 15. Security and Privacy

### 15.1 Secrets Management

- Use `.env` for local secrets.
- Provide `.env.example` without secret values.
- Never commit credentials.
- Keep Playwright browser session state under `data/browser_state/` and exclude from git.

### 15.2 Telegram Security

- Restrict commands to Ajith's chat ID.
- Reject unknown users.
- Log unauthorized command attempts without exposing secrets.

### 15.3 Document Privacy

- Generated resumes and cover letters contain personal data.
- Store locally by default.
- Only send to Telegram/email when configured.

---

## 16. Risks and Mitigations

### Risk: Job boards block scraping or automation

Mitigation:

- Prefer official/public job pages where possible.
- Use source adapters with throttling.
- Add manual fallback.
- Avoid aggressive scraping.

### Risk: Automated applications submit incorrect information

Mitigation:

- Approval gate.
- Source-specific adapters.
- Form validation before submit.
- Manual fallback for unknown fields.

### Risk: LLM generates inaccurate resume content

Mitigation:

- Use structured candidate profile.
- Add truthfulness checks.
- Do not allow invented claims.
- Keep generated resume diffs traceable.

### Risk: Duplicate jobs spam Telegram

Mitigation:

- URL and description hash deduplication.
- Status-aware notifications.
- Daily alert limits.

### Risk: Laptop is asleep during scheduled runs

Mitigation:

- Startup trigger checks last run time.
- Catch up if no scan within 4 hours.

### Risk: Telegram bot receives commands from unauthorized users

Mitigation:

- Whitelist Ajith's chat ID.
- Ignore or reject all other chats.

### Risk: PDF formatting quality is poor

Mitigation:

- Use controlled ATS template.
- Add visual and text extraction checks.
- Keep Markdown/HTML source for regeneration.

### Risk: Cost or rate limits from LLM providers

Mitigation:

- Batch and cache profile summaries.
- Use deterministic extraction where possible.
- Apply pre-filters before LLM scoring.
- Add per-run job limits and cost limits.

---

## 17. Implementation Phases

## Phase 1: Planning and Architecture

Deliverables:

- PLAN.md
- Architecture design
- Folder structure
- Database schema
- Agent workflow diagrams

Acceptance criteria:

- PLAN.md exists and is reviewed by Ajith.
- No application code has been written.
- Required credentials and configuration list is clear.

Status: This file completes Phase 1 draft.

---

## Phase 2: Core Implementation

Objective: Build the foundation without Telegram approval or automated submissions.

Tasks:

1. Create Python project skeleton.
2. Add configuration loader.
3. Add `.env.example` and settings example.
4. Implement SQLite connection and schema migrations.
5. Implement repository layer for jobs, runs, scores, documents, approvals, job_rejections, and logs.
6. Implement structured logging.
7. Implement profile ingestion from resume/profile files.
8. Implement basic job source interface.
9. Implement Greenhouse and Lever discovery adapters first; do not implement LinkedIn in the initial source set.
10. Implement job extraction and normalization.
11. Implement deduplication.
12. Implement matching engine with deterministic scoring first.
13. Implement rejection pattern storage for automatic low-quality filtering.
14. Add LLM scoring as optional provider-backed enhancement.
15. Add unit tests for config, database, scoring, deduplication, rejection learning, and status transitions.

Phase 2 verification:

- Run tests successfully.
- Run a dry discovery cycle.
- Store discovered jobs in SQLite.
- Produce match scores and explanations.
- No automated application capability enabled yet.

---

## Phase 3: Telegram Approval Workflow

Objective: Make Telegram the main user interface.

Tasks:

1. Implement Telegram Bot API client.
2. Implement authorized chat validation.
3. Implement job alert message templates.
4. Implement `/details <job_id>`.
5. Implement `/reject <job_id>` with optional structured rejection category capture.
6. Implement `/apply <job_id>` as approval only, not submission yet.
7. Implement `/resume <job_id>` placeholder response until document generation is complete; final behavior generates only on explicit request or after approval.
8. Implement `/coverletter <job_id>` placeholder response until document generation is complete.
9. Implement `/status`.
10. Store inbound and outbound Telegram messages.
11. Add integration tests using mocked Telegram API.

Phase 3 verification:

- Telegram bot sends job alerts.
- Commands update database state correctly.
- `/reject` stores both an audit action and a structured `job_rejections` row.
- Unauthorized chat IDs cannot control jobs.
- `/apply` sets status to `Approved` but does not submit applications yet.

---

## Phase 4: Resume Tailoring System

Objective: Generate high-quality ATS-friendly application documents.

Tasks:

1. Parse base resume into structured sections from the provided Word `.docx` template and the stored Markdown profile.
2. Build ATS-friendly DOCX resume template rules.
3. Implement skill reordering.
4. Implement relevant project selection.
5. Implement project bullet tailoring with truthfulness constraints.
6. Implement resume diff generation.
7. Implement python-docx editing of a copied Word resume template.
8. Implement Microsoft Word DOCX-to-PDF export through Windows/Word automation.
9. Store generated DOCX, PDF, and resume diff records.
10. Implement cover letter generation on demand or when required.
11. Add Telegram document and diff delivery for `/resume` and post-approval `/apply`.
12. Add tests for document file creation, diff generation, and metadata storage.
13. Add environment checks that fail clearly if Microsoft Word or the source `.docx` resume is unavailable.

Phase 4 verification:

- High-scoring jobs do not create tailored resume PDFs during discovery.
- Approved jobs create tailored resume DOCX and PDF after `/apply <job_id>`.
- Explicit `/resume <job_id>` requests create or return tailored resume DOCX/PDF.
- Cover letter generates only when required or requested.
- Documents are stored under `data/generated/`.
- Resume diffs are stored and sent to Telegram.
- Telegram can send or reference generated documents.

---

## Phase 5: Automated Application System

Objective: Apply after approval where safe and supported.

Tasks:

1. Implement approval gate.
2. Implement application orchestrator.
3. Implement manual fallback generator.
4. Implement Greenhouse application adapter.
5. Implement Lever application adapter.
6. Implement generic form detector in cautious mode.
7. Add Playwright browser state management.
8. Add final pre-submit validation screen/logic.
9. Add application attempt records.
10. Add Telegram updates for success, manual fallback, and failure.
11. Add end-to-end tests with local mock application forms.

Phase 5 verification:

- Unapproved jobs cannot be submitted.
- Rejected jobs cannot be submitted.
- Already applied jobs cannot be resubmitted.
- Unsupported sites produce manual instructions.
- Supported mock forms submit successfully only after approval.

---

## Phase 6: Monitoring and Reporting

Objective: Make Hermes reliable for daily use.

Tasks:

1. Implement startup trigger.
2. Implement scheduled runs at 10:05 AM and 5:05 PM.
3. Implement daily summary at 8:30 PM.
4. Implement error reporting to Telegram.
5. Add run history and status reporting.
6. Add report generation under `data/generated/reports/`.
7. Add log rotation strategy.
8. Add backup/export command for SQLite database.
9. Add README usage instructions.
10. Add troubleshooting guide.

Phase 6 verification:

- Startup scan runs when last scan is older than 4 hours.
- Scheduled scans run during laptop usage windows.
- Daily Telegram summary is sent.
- Errors are logged and reported.

---

## 18. Testing Strategy

### 18.1 Unit Tests

Test:

- Configuration validation
- Secrets loading behavior without exposing values
- Database repositories
- Status transitions
- Deduplication
- Score calculations
- Prompt input construction
- Resume file naming
- Approval gate rules

### 18.2 Integration Tests

Test:

- Discovery adapter with mocked pages
- LLM client with mocked responses
- Telegram command handling with mocked API
- Document generation pipeline
- Scheduler startup trigger logic

### 18.3 End-to-End Tests

Test:

- Full dry-run discovery to Telegram alert
- Approval command to manual fallback
- Approval command to mock automated application
- Daily summary generation

### 18.4 Safety Tests

Required tests:

1. `/apply` approval exists but application adapter fails safely.
2. Direct application call without approval is blocked.
3. Rejected job cannot be approved accidentally without explicit new command.
4. Already applied job is not submitted again.
5. Unauthorized Telegram chat cannot approve jobs.

---

## 19. Configuration Files

### 19.1 settings.example.yaml

Should define:

- App name
- Timezone
- Database URL
- Job source enable/disable flags
- Schedule times
- Scoring thresholds
- LLM provider selection
- Groq API key environment variable name and selected Groq models
- LM Studio fallback base URL and model name `google/gemma-4-e4b`
- Resume source DOCX path
- Microsoft Word conversion helper path or command
- `max_applications_per_day`, default `10`
- `max_alerts_per_run`, default `20`
- Telegram enabled flag
- Email enabled flag
- Application automation enabled flag
- Manual fallback defaults

### 19.2 job_sources.yaml

Should define:

- Enabled sources
- Search queries
- Locations
- Remote filters
- Per-source limits
- Delay/throttle settings

### 19.3 scoring.yaml

Should define:

- Component weights
- Alert threshold
- Rejection threshold
- Confidence thresholds
- Hard reject rules

---

## 20. Data Retention Strategy

Recommended defaults:

- Keep all generated resumes and cover letters unless Ajith deletes them.
- Keep all job records for historical tracking.
- Keep logs for 30 to 90 days with rotation.
- Keep browser session state only if automation is enabled.
- Provide export command for database and generated documents.

---

## 21. Future Expansion

Planned future improvements:

1. PostgreSQL migration.
2. Web dashboard.
3. More job board adapters.
4. Better company research summaries.
5. Interview preparation module.
6. Follow-up email assistant.
7. Application analytics dashboard.
8. Resume A/B testing.
9. Job market trend reports.
10. Multi-profile support.

---

## 22. Review Checklist Before Coding

Ajith should review and confirm:

- [ ] Folder structure is acceptable.
- [ ] SQLite first, PostgreSQL later is acceptable.
- [ ] Telegram is the primary interface.
- [ ] Email remains optional.
- [ ] Greenhouse and Lever should be first automation targets.
- [ ] LinkedIn/Indeed automation can be delayed or manual-fallback-first.
- [ ] Resume generation can use the chosen LLM provider.
- [ ] Application submission requires explicit approval.
- [ ] Daily schedule matches laptop usage windows.
- [ ] Required credentials/configuration can be provided before implementation.

---

## 23. Implementation Gate

No code should be written until Ajith reviews this plan and explicitly approves moving to Phase 2.

When approved, implementation should begin with Phase 2 only, using small test-driven tasks and verifying each module before continuing.
