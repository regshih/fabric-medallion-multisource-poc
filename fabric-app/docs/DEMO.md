# Seven-minute customer walkthrough

## Before the meeting

Run `scripts/start-demo.ps1`, then open `http://127.0.0.1:5173/` in a normal browser profile. Confirm the Synthetic demo banner. Use the same origin throughout so saved investigation events persist. This fixture has a fixed September 1, 2026 load date; freshness should show Older than 24h, not a fabricated fresh timestamp. All customers, transactions and notes are synthetic.

If an approved live deployment has passed the separate acceptance checklist, use that URL instead and describe it as live queries over synthetic source data. Never call local fixtures live. Have the local demo available as an explicitly disclosed fallback for the presentation, not an automatic application fallback.

## 0:00–1:00 — Connect the business problem

Open Overview. Say: “The existing platform already provides useful risk intelligence. This application helps an investigator act on it, with evidence and a record of the work.” Point to the loaded-cohort label and explain that the KPIs apply to these customers, not the entire bank.

Show customer counts, high-risk customers, fraud signals and your open investigations. The chart is a distribution of retrieved source scores. There are no fabricated trend percentages or financial savings.

## 1:00–2:15 — Find a customer worth reviewing

Select Review high-risk customers. Explain the risk filter and sort order. Search for a visible customer ID, clear the search, and select a customer. The detail panel explains the score using transaction risk, source alerts, failed attempts, untrusted devices and geographic observations.

Say: “The score is the existing explainable synthetic heuristic, not a new fraud model and not an automatic decision.” Non-US session observations are not proof of fraud.

## 2:15–3:15 — Bring the evidence together

Open Transactions and Digital activity. Point out that transactions came from Databricks and behavior/alerts from Cosmos through the existing Fabric medallion processing. Amounts retain their source currencies. Evidence lists are bounded, so they do not claim to be a complete history or reconcile one-for-one with independently windowed aggregate metrics.

## 3:15–5:00 — Do the work a report cannot capture

Open Investigation. Enter assignment label “Fraud operations”, status Investigating, and note “Synthetic demo: review untrusted device and transaction velocity; follow up with the operations team.” Select Create investigation.

Add a note, then change the status to Escalated and save. Show the activity trail. Close the panel, open Investigations, and refresh the app. Reopen the case to show the saved work.

Say: “The investigation state belongs to the application. We are not writing case statuses into analytical facts or changing source-system alerts.” Explain that the POC's records are private to the investigator. Assignment is routing metadata, not actual cross-user sharing or an email notification.

## 5:00–6:15 — Explain the architecture

Open Data journey and select each stage. Databricks Delta remains in place. Unity Catalog mirroring supplies metadata and zero-copy shortcuts. Cosmos mirroring physically replicates its data. Fabric builds Silver and Gold; the app consumes the existing Warehouse through a read-only connector.

Show the separate app-owned SQL store in the architecture diagram. In the local demonstration, make the browser IndexedDB distinction explicit. In the deployed version, Fabric SSO plus creator policies protect the workflow records; delegated source identity governs reads.

## 6:15–7:00 — Show the limits honestly

Review freshness and reconciliation evidence. The fixed demo data is stale by design; HTTP refresh does not turn old source data into new data. A mismatched reconciliation run is flagged for review.

Close with: “Signal is deployed in Fabric, and its dashboard reads the existing Gold serving layer. Customer workflows use a separate app SQL database. Consumer security acceptance with a second identity remains a prerequisite before broader sharing.” Consult the current [live acceptance evidence](LIVE-PREFLIGHT.md) before claiming specific workflow, security or browser checks.
