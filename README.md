# GeoComply × Databricks — AI Dev Kit Workshop Pre-Read

## 1. Objective

In a single 2-hour working session we will:

- Use AI Dev Kit from your existing IDE (OpenCode / Claude Code / Cursor) to build a small pipeline and risk-scored table on Databricks.
- Train a simple model on those scores and track it with MLflow and Model Registry.
- Configure a Genie Space for natural-language exploration of the risk-scored data.
- Stand up an MCP server that exposes tools to:
  - Query that Genie Space.
  - Log feedback into MLflow (and optionally Lakebase).
- Build a minimal conversational app (Databricks App) that:
  - Acts as the chat UI front end.
  - Calls the MCP server.
  - Collects human-in-the-loop feedback and sends it to MLflow.

Lakebase is used as an optional backing store for conversation/feedback data and future extensions.

---

## 2. Audience and prerequisites

### Audience

Engineers and data scientists who:

- Use Databricks for pipelines / ML.
- Have OpenCode, Claude Code, Cursor, or similar AI coding tools.

### Access and permissions

- Databricks development workspace.
- Ability to attach to compute or use a SQL warehouse.
- Permissions to:
  - Create tables/views in an agreed sandbox catalog/schema.
  - Create a Genie Space (or equivalent, via an owner account).

### Tools

- Working installation of at least one IDE: OpenCode, Claude Code, or Cursor.
- Ability to install / configure AI Dev Kit for that IDE (we will provide install instructions in the calendar invite).

---

## 3. Data and risk-scoring scenario

We will use a synthetic fingerprint / geolocation dataset with fields such as:

- `device_id`, `account_id`
- `ip_address`, `country`, `latitude`, `longitude`
- `event_timestamp`
- Event-type and channel fields as needed

From this we will build a per-device (or per-fingerprint) risk table with the following example scores:

- **Velocity / Impossible Travel Score**
  - Detects physically implausible movements.
  - Derived from distances and time deltas between consecutive pings.
- **Jurisdiction / Geofence Mismatch Score**
  - Frequency of events outside an allowed region list.
  - Uses a configuration table (Delta or Lakebase).
- **Device Sharing Across Accounts Score**
  - Number of distinct accounts per device in a time window.
- **Behavioral Drift Score**
  - Deviation of current behavior from a historical baseline.
- **External Reputation / Watchlist Score**
  - Status from an external reputation service, accessed via UC HTTP connection.

The scores are simple enough to implement quickly but expressive enough to show the patterns we care about.

---

## 4. Activity 1 — Build the risk-scored table with AI Dev Kit (IDE)

**Goal:** Use agentic coding in your IDE to produce a curated risk table on Databricks.

**Steps (high level):**

- Use AI Dev Kit tools from your IDE to scaffold a notebook or pipeline that:
  - Reads the synthetic input data into a bronze Delta table.
- Prompt AI Dev Kit to:
  - Create a silver/gold table `fingerprint_risk` with one row per device/fingerprint.
  - Implement the five scores above as columns on that table.
- Validate that the resulting table looks reasonable (row counts, basic distributions).

**Output:**

- A Delta table (e.g. `<catalog>.<schema>.fingerprint_risk`) with all risk scores present.

---

## 5. Activity 2 — Train a model and wire in MLflow and Registry

**Goal:** Train a basic model on the risk-scored data and prepare MLflow to accept feedback later.

**Steps:**

- Add a simple synthetic label (for example, `high_risk` flag) based on a rule or randomization.
- From your IDE, use AI Dev Kit to:
  - Generate a training script or notebook that:
    - Reads `fingerprint_risk`.
    - Trains a simple classifier or risk-ranking model.
  - Add MLflow tracking:
    - Log parameters, metrics, and the model artifact.
- Register the model into Model Registry.
- Define a feedback payload that MLflow will accept later, for example:
  - `query_text`
  - `genie_answer`
  - `label` (e.g. helpful / unhelpful / incorrect / high-value)
  - `model_version`
  - `timestamp`
  - Optional: `device_id` / `account_id`

**Output:**

- An MLflow experiment with at least one run.
- A registered model version.
- An agreed feedback schema (fields and table/experiment names).

---

## 6. Activity 3 — Configure the Genie Space over the risk table

**Goal:** Make the risk-scored data explorable via a Genie Space.

**Steps:**

- Use AI Dev Kit's Genie-related skills to:
  - Create a Genie Space that:
    - Connects to the `fingerprint_risk` table or a simple view on top of it.
  - Add:
    - A short description of the space's purpose (fingerprint risk exploration).
    - A handful of sample questions (e.g., "List the devices with highest velocity score in country X over the last 24 hours").
- Verify that Genie can:
  - Generate runnable SQL against the risk table.
  - Return answers that match simple validation queries.

**Output:**

- A Genie Space ID and URL for the "fingerprint risk" space.

---

## 7. Activity 4 — Stand up the MCP server for Genie + feedback

**Goal:** Expose the Genie Space and feedback logging via MCP tools.

**Steps:**

- Implement or configure an MCP server (using AI Dev Kit patterns) that provides at least two tools:
  - `query_space` (name indicative only):
    - Inputs: `space_id`, `query_text`, optional context.
    - Behavior: sends the query to the Genie Space and returns the answer and, if available, the generated SQL.
  - `log_feedback`:
    - Inputs: at minimum `query_text`, `genie_answer`, `label`, `timestamp`, and optionally `model_version`, device/account identifiers.
    - Behavior:
      - Logs a record into MLflow as a trace/evaluation row, and/or
      - Inserts a record into a feedback table (Delta or Lakebase).
- (Optional) Use Lakebase as the target for a `feedback_events` table and, if desired, as a backing store for conversation state.

**Output:**

- An MCP endpoint URL and a tool list that includes `query_space` and `log_feedback`.
- A place for feedback records (MLflow experiment and/or feedback table).

---

## 8. Activity 5 — Build the conversational app (custom agent + chat UI)

**Goal:** Create a simple chat front end that uses the MCP server and logs HITL feedback.

**Steps:**

- Use AI Dev Kit app-oriented skills to scaffold a Databricks App that:
  - Renders a minimal chat interface:
    - Text input for user messages.
    - Chat history display with alternating user/assistant messages.
- Implement app logic so that:
  - On each user message:
    - The app calls the MCP server's `query_space` tool with:
      - The Genie `space_id`.
      - The user's `query_text`.
    - Displays the returned Genie answer (and optionally the SQL) in the chat history.
  - On feedback:
    - Provide a simple UI element (e.g., thumbs up/down, or a dropdown) for each answer.
    - When feedback is given, call the MCP server's `log_feedback` tool with:
      - The original `query_text`.
      - The `genie_answer`.
      - The chosen label.
      - Optional metadata (model version, device/account, timestamp).
- If Lakebase is used:
  - Configure the app (or MCP) to use a Lakebase table as the persistence layer for feedback events and, optionally, chat transcripts.

**Output:**

- A working Databricks App URL.
- A chat experience that:
  - Uses Genie via MCP for answers over fingerprint risk data.
  - Sends human feedback to MLflow (and optionally Lakebase) for later analysis and evaluation.

---

## 9. How to prepare

Before the workshop:

- Confirm workspace access and that you can create objects in the agreed sandbox catalog/schema.
- Ensure your IDE (OpenCode / Claude Code / Cursor) is installed and working.
- Install or test AI Dev Kit in your IDE (we'll send exact commands in the invite).
- If you expect to use Lakebase:
  - Confirm there is a Lakebase instance available to use as a resource for the Databricks App, or that we have a plan to create one.

During the workshop we will work from this starting point and aim to leave you with working assets in your own workspace.

---

*Co-authored with Glean*
