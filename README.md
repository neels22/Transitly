# Transitly - Al powered moving assistant architecture

![](https://i.imghippo.com/files/QDMY8488c.png)

## ⭐ Core Mission

Make the paperwork side of moving disappear. You enter your old/new address and move dates; Transitly plans your tasks and, with your approval, autofills the right forms (USPS, utilities, ISP) while keeping an auditable checklist and timeline.

## 🔧 The Problem We Solve
Moving requires dozens of small but critical admin steps spread across different portals. People forget tasks, mistype information, and lose hours clicking through brittle forms.

- **Fragmented workflows**: USPS, utilities, ISP, insurance—every site is different and easy to miss.
- **Manual, error‑prone forms**: Re‑typing addresses and dates across portals leads to mistakes and bounces.
- **No single source of truth**: Checklists live in notes or memory; progress and proofs are hard to track.
- **Time sinks and deadline risk**: Missed windows (e.g., tech appointments) create costly delays.

## 💡 Our Solution
An agentic system that plans, acts (with approvals), and tracks your move‑day admin.

- **Smart intake → plan**: Collect `from_address`, `to_address`, `move_out_date`, `move_in_date` (plus household prefs) and generate a dynamic checklist tailored to your move.
- **Approve to autofill**: Use a browser‑action agent to navigate real websites and prefill up to the review/submit page; a human click is required to confirm.
- **Live status + audit**: Stream progress to the UI via SSE, save checklists in DynamoDB, and keep structured action logs. Screenshots/receipts and reminders are planned next.
- **Privacy‑first**: No passwords are stored; sensitive fields are masked and PII is redacted in logs.

## 🔄 Multi-Agent Orchestration System
Transitly uses a LangGraph‑based orchestrator that routes between specialized workers and yields a consistent state: messages, `user_details`, a typed checklist, and action results.

- **Orchestrator Agent**: Supervises the workflow using a reasoning LLM and a registry of workers. Chooses `next_task` deterministically when possible and stops when all relevant items are complete or blocked.
- **Get User Details Agent**: Resolves a `user_id` and fetches profile + latest move from DynamoDB via a tool. Idempotent: skips if details already exist and updates any matching checklist item.
- **Checklist Agent**: Plans the move as `ChecklistItem` objects, assigning `agent_label` (e.g., `amazon_address_change`) so the supervisor can route execution. Produces 4–10 atomic, actionable tasks.
- **Nova Act Agent (Amazon Address Change)**: Uses `NovaAct` browser automation to update the default Amazon shipping address. Runs only with user approval, requires login in a real browser, and stops at the review page for a human click. Results are written back to state.

Backend: FastAPI with Cognito JWT auth, DynamoDB tables (`TransitlyUsers`, `TransitlyMoves`, `TransitlyChecklists`), and an SSE endpoint (`/run-agents-stream`). Frontend: React + Vite; the `AgentStatus` component listens for `text/event-stream` updates and renders progress and checklists.

## ✨ Key Benefits
- **Fewer clicks, fewer mistakes**: Autofill reduces re‑typing and address errors across portals.
- **Always know what’s next**: A living checklist with statuses, streamed live to the UI.
- **Approval in the loop**: Every action is gated by a “Confirm & Autofill” step; no silent submissions.
- **Cloud‑ready architecture**: Cognito for auth, DynamoDB for state, Bedrock/Gemini‑class LLMs, and Nova Act for safe browser actions.
- **Extensible workers**: Add agents for USPS COA, utilities, ISP transfers, and DMV reminders without changing the orchestration model.