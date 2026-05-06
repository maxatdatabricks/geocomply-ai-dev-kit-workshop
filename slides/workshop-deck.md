# GeoComply x Databricks — AI Dev Kit Workshop

> Slide deck outline. One H2 = one slide. Title, subtitle, and bullets. Copy-paste into your slide tool of choice.

---

## Slide 1 — Cover

**Title:** GeoComply x Databricks
**Subtitle:** AI Dev Kit Workshop

- ~2 hours
- Hands-on, in your own workspace
- Bring your IDE and your curiosity

---

## Slide 2 — Objective and outcomes

**Title:** What we're doing today
**Subtitle:** Build a fingerprint-risk pipeline and a chat app on Databricks, end to end, using AI Dev Kit

- Use AI Dev Kit from your IDE to scaffold and ship Databricks artifacts without leaving your editor
- Build a risk-scored Delta table from synthetic geolocation data
- Train and register a model with MLflow
- Stand up a Genie Space, an MCP server, and a Databricks App over the risk data
- Walk away with: AI Dev Kit installed, a working pipeline, an MLflow-tracked model, a Genie Space, an MCP endpoint, and a chat app — all in your own workspace

---

## Slide 3 — Format

**Title:** How the next 2 hours run
**Subtitle:** Short briefs, hands-on sprints, quick regroups

- ~10 minutes of intro, then five activity sprints
- Each activity: 3-minute brief, ~12-minute sprint, ~3-minute regroup
- Work in your own workspace using your own IDE
- Activities are independent — if you fall behind, skip ahead
- Ask questions in chat or unmute at any point

---

## Slide 4 — What is AI Dev Kit

**Title:** What is AI Dev Kit
**Subtitle:** A toolkit Databricks Solutions Architects use day-to-day, packaged so you can install it too

- Open-source project under [databricks-solutions/ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit)
- Turns any agentic-coding IDE (Claude Code, Cursor, Antigravity, Windsurf, OpenCode, Gemini CLI, Codex, Copilot) into a Databricks-aware assistant
- Built and maintained by Databricks Field Engineering, used internally every day
- Not part of the supported core Databricks product surface — community-supported, moves fast
- Re-run the install command periodically to pull the latest skills and tools

---

## Slide 5 — What you can build with it

**Title:** What AI Dev Kit can build
**Subtitle:** Most of the Databricks platform surface, from your IDE

- **Pipelines:** Spark Declarative Pipelines (streaming tables, CDC, SCD Type 2, Auto Loader), Databricks Jobs
- **SQL and analytics:** Unity Catalog (tables, volumes, governance), Genie Spaces, AI/BI Dashboards
- **AI and ML:** MLflow experiments and tracing, Model Serving, Knowledge Assistants (RAG), Vector Search
- **Apps:** Databricks Apps with foundation-model integration
- 20+ skills + 50+ MCP tools, growing — see the repo for the current catalog

---

## Slide 6 — How it works

**Title:** How AI Dev Kit works
**Subtitle:** Three layers, each usable on its own

- **Skills** — markdown instruction packs that teach the agent Databricks patterns (e.g., how to build a Genie Space the right way)
- **MCP server** — a local process exposing 50+ executable tools the agent calls to act on your workspace (run SQL, list catalogs, deploy apps, etc.)
- **IDE config** — per-project files (`.claude/`, `.cursor/`, `.opencode/`, `.github/`, etc.) that wire skills + MCP into your IDE
- Skills auto-load when the agent recognizes a relevant task; MCP tools are called when the agent needs to act
- Authentication is just a Databricks CLI profile — no extra credentials to manage

---

## Slide 7 — Install AI Dev Kit

**Title:** Install AI Dev Kit
**Subtitle:** One command, run from your project directory

- Prerequisites:
  - [uv](https://github.com/astral-sh/uv) (Python package manager)
  - [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/)
  - At least one supported IDE (Claude Code, Cursor, Antigravity, Windsurf, OpenCode, Gemini CLI, Codex, Copilot)
- **Mac / Linux:**
  - `bash <(curl -sL https://raw.githubusercontent.com/databricks-solutions/ai-dev-kit/main/install.sh)`
- **Windows (PowerShell):**
  - `irm https://raw.githubusercontent.com/databricks-solutions/ai-dev-kit/main/install.ps1 | iex`
- Default scope is **project-level** — run the install from the directory you'll be working in (your client must run from this same directory)
- Use `--global` (or `-Global` on Windows) for a user-wide install instead
- Respond to the interactive prompts; Cursor and Copilot need a manual settings update after install
- Full options and advanced flags: [README](https://github.com/databricks-solutions/ai-dev-kit#install-in-existing-project)

---

## Slide 8 — Authenticate with your workspace

**Title:** Authenticating with Databricks
**Subtitle:** One CLI profile, picked up by AI Dev Kit automatically

- Authenticate the Databricks CLI to your workspace and create a named profile:
  - `databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile geocomply`
- This writes a `[geocomply]` section into `~/.databrickscfg`
- The AI Dev Kit installer detects available profiles; pick `geocomply` (or pass `--profile geocomply` to install)
- The profile name ends up in your IDE's MCP config as `DATABRICKS_CONFIG_PROFILE=geocomply`
- Restart your IDE so the MCP server reloads with the new profile
- Verify: ask the agent "list the catalogs I can access" — you should see your workspace

---

## Slide 9 — How and why to use it

**Title:** How and why to use AI Dev Kit
**Subtitle:** Reach for it whenever you'd otherwise context-switch

- Use it when you'd normally jump to docs, the workspace UI, or a notebook to do something Databricks-shaped
- Prompt with the outcome, not the API: "create a streaming table that ingests events from this volume" beats "use Auto Loader with cloudFiles"
- Skills auto-load when the agent recognizes a relevant task — you can also reference one by name to be explicit
- Material speedup on greenfield work; review carefully on production code paths
- Treat it as a senior pair, not autopilot — verify what it ships before you merge

---

## Slide 10 — The scenario

**Title:** Today's scenario
**Subtitle:** Synthetic fingerprint and geolocation data, scored for risk, then made conversational

- Input: ~150,000 events across ~800 devices, ~600 accounts, 30 days, 11 countries
- One row per device-event with location, IP, timestamp, channel, event type
- Goal: collapse to one row per device with five risk scores, then make it queryable in natural language
- Sample data, geofence config, IP watchlist, and ground-truth labels are pre-generated in the repo
- Generator: `scripts/generate_sample_data.py` (config-driven, dry-run supported)

---

## Slide 11 — The five risk scores

**Title:** Risk dimensions
**Subtitle:** Five scores, each detectable in the planted anomalies

- **Velocity / Impossible Travel** — distance and time deltas between consecutive pings; flags speeds no aircraft can sustain
- **Jurisdiction / Geofence Mismatch** — events outside the account's allowed-country set (per `allowed_regions.csv`)
- **Device Sharing** — count of distinct accounts seen on a single device in a window
- **Behavioral Drift** — deviation between baseline (first 21 days) and current (last 9 days) on country and time-of-day
- **External Reputation** — events from IPs on the watchlist (`ip_watchlist.csv`)
- Ground truth (`data/ground_truth.csv`) labels exactly which devices/accounts are anomalous so you can validate scoring

---

## Slide 12 — Activity 1: Build the risk-scored table

**Title:** Activity 1 — Build the risk-scored table
**Subtitle:** From raw events to a curated Delta table with one row per device

- Goal: produce `<your_catalog>.<your_schema>.fingerprint_risk` with all five score columns
- Inputs: `data/fingerprint_events.parquet`, `data/allowed_regions.csv`, `data/ip_watchlist.csv`
- Pick your own catalog/schema in your workspace — the activity is workspace-target agnostic
- Suggested skills: `databricks-spark-declarative-pipelines`, `databricks-unity-catalog`, `databricks-dbsql`
- Prompt example: "Ingest the parquet to a bronze Delta table, then build a gold `fingerprint_risk` table with these five score columns: velocity, geofence, sharing, drift, reputation"
- Validate: top-N devices per score should overlap with `ground_truth.csv`
- Time: ~15 minutes

---

## Slide 13 — Activity 2: Train a model and wire in MLflow

**Title:** Activity 2 — Train and register a model
**Subtitle:** Risk scores as features, MLflow for tracking, Model Registry for versioning

- Goal: train a simple classifier on `fingerprint_risk`, log it to MLflow, register it
- Add a synthetic `high_risk` label (e.g., a threshold rule across the five scores)
- Suggested skills: `mlflow-onboarding`, `instrumenting-with-mlflow-tracing`, `databricks-model-serving`
- Define the feedback schema you'll log later: `query_text`, `genie_answer`, `label`, `model_version`, `timestamp`, optional identifiers
- Output: a registered model version + an experiment ready to receive feedback in Activity 4
- Time: ~15 minutes

---

## Slide 14 — Activity 3: Configure a Genie Space

**Title:** Activity 3 — Genie Space over the risk table
**Subtitle:** Natural-language SQL over `fingerprint_risk`

- Goal: a Genie Space pointed at `fingerprint_risk` (or a view on top of it) that returns runnable SQL
- Suggested skill: `databricks-genie`
- Add a short description of the space's purpose and ~5 sample questions
  - Example: "Top 20 devices by velocity score in the last 24 hours"
  - Example: "How many accounts had geofence violations in country X this week?"
- Validate: pick a known-answer question and cross-check Genie's SQL against `ground_truth.csv`
- Output: a Genie Space ID and URL, ready to be called by an MCP tool in Activity 4
- Time: ~10 minutes

---

## Slide 15 — Activity 4: MCP server with Genie + feedback tools

**Title:** Activity 4 — Stand up the MCP server
**Subtitle:** Two tools: query the Genie Space, log feedback to MLflow

- Goal: an MCP endpoint exposing two tools
  - `query_space(space_id, query_text)` — calls the Genie API, returns answer + generated SQL
  - `log_feedback(query_text, answer, label, model_version, timestamp, ...)` — writes to MLflow trace + optional Lakebase row
- Suggested skills: `databricks-genie`, `instrumenting-with-mlflow-tracing`, `databricks-app-python`
- Optional: back the feedback table with Lakebase for OLTP-style writes and downstream analytics
- Output: a deployed MCP endpoint URL + a tool list confirming both tools are registered
- Time: ~15 minutes

---

## Slide 16 — Activity 5: Conversational app

**Title:** Activity 5 — Build the chat app
**Subtitle:** A Databricks App that calls your MCP server and captures human feedback

- Goal: a minimal chat UI that uses Activity 4's MCP server for answers and feedback
- Suggested skills: `databricks-app-python` or `databricks-app-apx`
- On user message: call `query_space` → display the Genie answer (and optionally the SQL)
- On feedback: thumbs-up / thumbs-down (or label dropdown) → call `log_feedback` with the original query, the answer, and metadata
- Optional: persist conversation transcripts to Lakebase
- Output: a working Databricks App URL with HITL feedback flowing into MLflow
- Time: ~15 minutes

---

## Slide 17 — Where to go next

**Title:** Where to go from here
**Subtitle:** Install, iterate, bring your own use case

- All sample data and scripts in this workshop are in the repo: `scripts/generate_sample_data.py`, `data/`
- AI Dev Kit repo and full docs: [databricks-solutions/ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit)
- Re-run the install command periodically to pull new skills and MCP tools as they ship
- Bring your own use case — most Databricks work gets materially faster with this loop
- Feedback is welcome: open issues against the AI Dev Kit repo, or share with your Databricks SA
