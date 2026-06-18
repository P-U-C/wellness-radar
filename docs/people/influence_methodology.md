# Influence Scoring Methodology

Status: M3 beta

Influence scoring uses public professional data only. It does not use patient data, private attributes, scraped LinkedIn data, private social data, or raw social firehose data.

## Formula

```text
Influence Score =
0.25 institutional_authority
+ 0.20 network_centrality
+ 0.15 research_or_clinical_leadership
+ 0.15 media_velocity
+ 0.10 capital_power
+ 0.10 event_convening
+ 0.05 public_reach
```

The weighted score is multiplied by:

- `locality_multiplier`
- `recency_decay`
- `source_confidence`

## Components

- `institutional_authority`: public role and public institution signals.
- `network_centrality`: graph degree centrality from public people/org/operator/event edges.
- `research_or_clinical_leadership`: public title/role indicators such as Dr., health officer, clinical, research, practitioner, or therapist.
- `media_velocity`: source-backed `signal.related_person_ids` mentions in the 180-day window.
- `capital_power`: public founder/investor/operator/government authority indicators.
- `event_convening`: source-backed event matches.
- `public_reach`: public profile and public institution visibility.

Every scored person row stores the full component breakdown in `person_influence_component`.

## Explanation

The API returns `influence_explanation` as the “why this person appears” text. It is assembled from public role, public affiliation, graph centrality, source-backed media mentions, and event matches.

## Governance

- Display only rows with `source_refs`.
- Do not add private personal contact details.
- Do not infer sensitive health attributes.
- Keep correction/request-update flow as a production-hardening task.
