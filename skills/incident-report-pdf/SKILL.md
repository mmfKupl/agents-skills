---
name: incident-report-pdf
description: Generate standard 5-page PDF incident reports from Linear security/privacy/incident tickets using a bundled HTML template and headless Chrome export. Use when asked to create a report like the existing incident PDFs from a ticket ID such as UIB-2455 and return a finished PDF document.
---

# Incident Report PDF

## Writing quality

Before drafting report prose, read [`../unslop/SKILL.md`](../unslop/SKILL.md)
and apply its relevant editing guidance. Preserve source quotations, required
field values, and the fixed report format when they conflict with that guidance.

## Overview

Use this skill to turn a Linear incident-style ticket into the standard PDF report used in prior `UIB-*` security/privacy incident documents.
Query the ticket with Linear MCP, normalize the ticket into the report payload, render the bundled template, and export the final PDF.

## Input/Output Contract

- Input: a Linear ticket ID such as `UIB-2455`.
- Output: a finished PDF document in the standard 5-page incident-report format.
- Optional extra input: destination path for the PDF. If the user does not provide one, choose a clear default filename derived from the ticket ID.

## Workflow

1. Read the ticket and resolution context.
   - Call `mcp__linear__get_issue` with the ticket ID.
   - Call `mcp__linear__list_comments` for the same ticket.
   - Call `mcp__linear__get_user` when you need reporter or assignee details.
2. Build the final narrative, not just the initial report.
   - Use the ticket description as the initial incident intake.
   - Treat later comments as authoritative when they clarify, downgrade, or invalidate the incident.
   - Use exact dates from the ticket. Do not use relative dates.
3. Normalize the ticket into a JSON payload.
   - Read [`references/field-mapping.md`](./references/field-mapping.md).
   - Fill every required field.
   - Use plain strings for normal cells.
   - Use arrays of strings for `action_taken` and `mitigation_details`; the renderer turns them into bullet lists.
   - Prefer `None.`, `No.`, or `Not applicable.` over empty fields.
4. Render the report.
   - Run:
   - `python3 scripts/render_incident_report.py --input payload.json --output-html /tmp/UIB-2455-report.html --output-pdf /tmp/UIB-2455-report.pdf`
   - The script uses [`assets/incident-report-template.html`](./assets/incident-report-template.html).
5. Deliver the result.
   - Move or copy the PDF to the user-requested location.
   - If the user did not specify a location, choose a clear filename such as `UIB-2455-report.pdf` in the current working directory or the same report folder used in the thread.

## Required Inputs

Prepare a JSON file with the normalized report data before running the renderer.
The renderer expects all required keys from [`references/field-mapping.md`](./references/field-mapping.md).

## Output Rules

- Keep the report structure fixed to the standard 5-page layout.
- Keep the title format as `YYYY.MM.DD - <ticket title>`.
- Keep the incident date field format as `DD-Mon-YYYY`.
- Keep the tone factual and concise.
- Reflect the final resolved state if ticket comments change the original interpretation.

## Resources

### `scripts/render_incident_report.py`

Render the normalized JSON payload into HTML and optionally export it to PDF through headless Chrome.

If Chrome is not auto-detected, set `CHROME_BIN` before running the script.

### `assets/incident-report-template.html`

Provide the canonical HTML template used for the PDF layout, styling, and page structure.

### `references/field-mapping.md`

Define the required payload fields and the mapping rules from a Linear ticket into the report template.
