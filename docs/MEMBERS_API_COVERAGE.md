# Members API Coverage Audit

Source inventory: https://members-api.parliament.uk/index.html and its OpenAPI document at https://members-api.parliament.uk/swagger/v1/swagger.json.

This document exists because Commons Score must not pretend it has full Parliament Members API coverage when it only uses a subset.

## Current repo coverage

| Official API area | Endpoint / pattern | Current status | Current use | Metric relevance |
|---|---|---|---|---|
| Members | `/api/Members/Search` | Used | Current Commons MP list | Identity, ranking universe |
| Members | `/api/Members/{id}/RegisteredInterests` | Used in full-mode collector / counted when probed | Registered interests signal | Proof, Public Value, diagnostics |
| Members | `/api/Members/{id}/Edms` | Counted when probed | EDM activity count | Activity |
| Members | `/api/Members/{id}/Focus` | Counted when probed | Focus items count | Activity, Local Focus |
| Members | `/api/Members/{id}/Voting` | Counted when probed | Voting count | Activity |
| Members | `/api/Members/{id}/Experience` | Used in full-mode collector | Roles / committee / ministerial experience hints | Role context, Proof |
| Members | `/api/Members/{id}/ContributionSummary` | Used in full-mode collector | Debate, question, bill-related summary hints | Activity, Public Value |
| Members | `/api/Members/{id}/Contact` | Used in full-mode collector | MP website/contact discovery | Boost link, Proof |

## Members API endpoints seen in the official spec but not yet fully wired

| Official API area | Endpoint / pattern | Current status | Priority | Use for Commons Score |
|---|---|---|---|---|
| Members | `/api/Members/{id}` | Missing as a deliberate collector | High | Full member profile, portrait fields, stable member metadata |
| Members | `/api/Members/SearchHistorical` | Missing | Low for v1 | Historical membership; useful later for time series or former MPs |
| Location | `/api/Location/Constituency/Search` | Missing | High | Resolve constituency IDs instead of relying only on membership text |
| Location | `/api/Location/Constituency/{id}` | Missing | High | Constituency metadata for Local Focus |
| Location | `/api/Location/Constituency/{id}/Synopsis` | Missing | Medium | Constituency description/context; useful for Local Focus explanations |
| Location | `/api/Location/Constituency/{id}/Representations` | Missing | High | Representation history / current representation context |
| Location | `/api/Location/Constituency/{id}/Geometry` | Missing | Low for v1 | Map/boundary data; not needed for simple scoreboard launch |
| Location | `/api/Location/Constituency/{id}/ElectionResults` | Missing | Medium | Electoral context; can be shown but should not score MP performance directly |
| Location | `/api/Location/Constituency/{id}/ElectionResult/{electionId}` | Missing | Low | Specific historical election result lookup |
| Location | `/api/Location/Constituency/{id}/ElectionResult/Latest` | Missing | Medium | Latest result context; not a performance score input |
| Location | `/api/Location/Browse/{locationType}/{locationName}` | Missing | Low | Browse helper; not core to five metrics |
| LordsInterests | `/api/LordsInterests/Register` | Out of scope | None for Commons-only | Lords product only |
| LordsInterests | `/api/LordsInterests/Staff` | Out of scope | None for Commons-only | Lords product only |

## Correction to product state

Commons Score currently has a partial Members API integration.

It has enough to produce a Commons MP ranking surface, but it does not yet use the full official Members API surface. The biggest miss is the Location / Constituency group, because that is directly relevant to Local Focus and constituency context.

## Implementation order

1. Add constituency ID resolution from `/api/Location/Constituency/Search`.
2. Add constituency detail lookup from `/api/Location/Constituency/{id}`.
3. Add latest election result lookup as context only, not as a score input.
4. Add constituency representations as context and source audit.
5. Add member detail lookup from `/api/Members/{id}` to improve portrait/contact/profile completeness.
6. Keep Lords endpoints out of scope unless the product expands beyond Commons MPs.

## Guardrail

Do not wire endpoints blindly just because they exist. Each endpoint must map to one of:

- Activity
- Local Focus
- Delivery
- Public Value
- Proof
- Sources & Methods context
- Boost/contact routing
