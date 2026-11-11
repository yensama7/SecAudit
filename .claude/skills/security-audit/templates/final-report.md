# Security Audit Report — {{repo_name}}

- **Repository:** {{root}}
- **Revision:** {{commit}}
- **Languages / frameworks:** {{languages}} / {{frameworks}}
- **Date:** {{date}}
- **Coverage:** {{examined_files}}/{{in_scope_files}} in-scope files examined — {{coverage_status}}

> {{incomplete_warning}}

## Executive summary

{{summary}}

| Severity | Count |
|----------|-------|
| Critical | {{n_critical}} |
| High     | {{n_high}} |
| Medium   | {{n_medium}} |
| Low      | {{n_low}} |

## Scope & coverage

{{coverage_table}}

Excluded files: {{excluded_list}}

## Findings

{{#each findings}}
### {{id}} — {{title}}

**Severity:** {{severity}}  |  **Confidence:** {{confidence}}

- **Location(s):** {{locations}}
- **Root cause:** {{root_cause}}
- **Reachability / preconditions:** {{reachability}}
- **Impact:** {{impact}}
- **Trigger:** {{trigger}}

**Evidence (this repo):**
```
{{evidence}}
```

**Historical comparison:** {{historical_summary}}
- Verdict: {{verdict}}
- References: {{references}}

**Remediation:** {{remediation}}

---
{{/each}}

## Limitations & unresolved questions

{{unresolved}}

## Methodology note

Findings marked *direct analysis* were discovered by examining this repository.
*Historical match* references come from past competitive-audit reports and were
used only to guide investigation — a match never establishes a vulnerability by
itself, and severity reflects this code's impact, not the historical finding's.
