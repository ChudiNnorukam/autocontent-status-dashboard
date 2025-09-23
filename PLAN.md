# Autoposter Revamp Plan

## Core Objectives

1. **Durable queue storage** – replace JSON files with a persistent data store (SQLite on disk to start, with an interface that can swap to Supabase/Postgres later).
2. **Robust scheduling** – enforce allowed posting windows (06:00, 10:00, 15:00, 20:00, 23:30 ET) and stop double-posting by tracking sent hashes and attempt counts.
3. **Resilient automation** – make GitHub Actions (or any scheduler) idempotent by reading/writing the shared store rather than a throwaway checkout.
4. **Voice + content fidelity** – move from synthetic samples to real tweet ingestion and richer prompts once API access is restored.
5. **Observability** – add logging, alerts, and metrics so failures are visible immediately.

## Work Breakdown

- [ ] **Storage layer**
  - [ ] Create a queue repository backed by SQLite (`data/queue.db`).
  - [ ] Define schema (`posts` table with status, scheduled_at, attempt_count, last_hash, etc.).
  - [ ] Migration script to import existing JSON queue/history into the database.
  - [ ] Update scheduler/poster code to use the repository API.
- [ ] **Scheduling logic**
  - [ ] Encode allowed posting windows in config.
  - [ ] Add utilities to generate slots and avoid duplicate text back-to-back.
  - [ ] Provide CLI command to reflow schedule if windows change.
- [ ] **Posting safeguards**
  - [ ] Track hash of each sent tweet to prevent duplicates in the same day/week.
  - [ ] Implement exponential backoff for transient API errors and move hard failures to a review queue.
  - [ ] Record tweet IDs and timestamps inside the DB.
- [ ] **Automation**
  - [ ] Update GitHub Actions workflow (or alternative host) to read/write the DB.
  - [ ] Commit DB changes or store in remote storage if using Actions.
  - [ ] Add notifications (Slack/Discord/email) on failure or when the queue drops below a threshold.
- [ ] **Voice + generation**
  - [ ] Replace `train_from_samples.py` with real tweet ingestion (once keys work).
  - [ ] Improve LLM prompt with multi-shot examples pulled from the DB.
  - [ ] Store hashtags separately and rotate intelligently.
- [ ] **Dashboard & API**
  - [ ] Serve queue/analytics data from an API backed by the DB.
  - [ ] Update the GitHub Pages frontend to fetch from the API (or rebuild with a static export step).
- [ ] **Testing & CI**
  - [ ] Add unit tests for scheduling windows and repository operations.
  - [ ] Add integration test (dry-run) for the posting loop.

## Immediate Next Steps

1. Introduce the SQLite-backed storage layer with a clean repository API.
2. Provide a migration script to seed the database from existing JSON files.
3. Wire the scheduler to read/write via the repository while retaining the JSON export for the dashboard until the API lands.
