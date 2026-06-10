# Field Mapping

Use this file when turning a Linear incident ticket into the JSON payload for `scripts/render_incident_report.py`.

## Required Keys

The payload must include these keys:

```text
doc_title
report_title
reporter_last_name
reporter_first_name
reporter_position
reporter_company
reporter_phone
reporter_email
organization_name
organization_type
street_address
other_organizations
incident_date
incident_time
affected_location
brief_summary
project_program
classification_level
system_compromise
data_compromise
originator_authority
foreign_government
accredited_system
estimated_injury
estimated_impact
incident_duration
systems_affected_count
systems_affected_percentage
action_taken
supporting_documents
multiple_occurrences
incident_status
reported_to_authorities
mitigation_details
mitigation_results
additional_assistance
malicious_code
known_vulnerability
disruption_of_service
access_violation
accident_or_error
user_error_details
additional_details
apparent_origin_details
network_zone
system_type
operating_system
protocols_services
application_version
authorities_info
root_cause_analysis
```

## Value Types

- Use strings for normal fields.
- Use arrays of strings for `action_taken` and `mitigation_details`.
- Use newline-separated strings when a single cell needs multiple labeled lines, for example `apparent_origin_details`.

## Mapping Rules

### Title fields

- `report_title`: Format as `YYYY.MM.DD - <ticket title>` using the incident date from the ticket body, not the ticket creation date.
- `doc_title`: Usually match `report_title`.

### Reporter block

- Use `Person discovered incident` from the ticket body as the primary source.
- If that field is missing, fall back to the issue creator.
- Split the person into first and last name when possible.
- Use `mcp__linear__get_user` to resolve email and display name.
- If phone or position is unknown, use `Not provided`.
- Default company to `UI Bakery Inc.` unless the ticket clearly says otherwise.

### Incident details

- Use the ticket description as the initial incident report.
- Use comments to determine whether the final interpretation changed.
- If a comment says the report was invalid, resolved as false positive, or otherwise corrected, reflect that in:
  - `brief_summary`
  - `estimated_injury`
  - `estimated_impact`
  - `incident_status`
  - `mitigation_results`
  - `root_cause_analysis`
- Use exact timezone wording when available. If the ticket says `Warsaw time`, preserve that meaning in the rendered field.

### Text quality

- Prefer concise, audit-friendly prose.
- Avoid speculation beyond what the ticket and comments support.
- When the ticket does not specify a field, use `None.`, `No.`, or `Not applicable.` instead of leaving blanks.

### Common defaults

- `organization_name`: `UI Bakery Inc.`
- `organization_type`: `SaaS software company`
- `street_address`: `Not provided`
- `foreign_government`: `None.`
- `malicious_code`: `None.`
- `known_vulnerability`: `None.`

## Example Notes

- For a normal incident, keep the original incident description and add mitigation/resolution detail from comments.
- For a false alarm, keep the initial report in the summary but clearly state the final invalidation and zero impact.
