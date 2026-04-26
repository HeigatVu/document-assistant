---
name: wikidoc-search
description: Activate with /wikidoc-search. Search the document library index directly — no external tools or API calls needed.
---

# /wikidoc-search

Use this skill to find documents in the library by type, scope, topic, or keywords. Searches are performed by reading `processed/index.json` directly — no Python subprocess is spawned.

## Trigger

```
/wikidoc-search <query>
```

Examples:
- `/wikidoc-search ethics consent forms`
- `/wikidoc-search VinIF guidelines`
- `/wikidoc-search Type:ETH Scope:BV175`

## Workflow

1. **Read Index**: Read `processed/index.json` directly using `read_file`. Do NOT call `query.py`.
2. **Filter & Rank**: Match entries against the query using Scope, Type, Subject, keywords, and summary fields.
3. **Present Matches**: Show the top results — filename, Scope, Type, and a brief summary for each.
4. **Deep Dive** (if requested): Read `processed/markdown/<filename_stem>.md` for full document content.

## Index Fields Available for Filtering

| Field | Description | Example |
|-------|-------------|---------|
| `Scope` | Project or organization scope | `BV175`, `VinIF`, `IU` |
| `Type` | Document type code | `ETH`, `GDL`, `PRO` |
| `Subject` | Descriptive filename subject | `ICF_Template` |
| `keywords` | Extracted keyword list | `["IRB", "consent"]` |
| `summary` | One-paragraph document summary | — |
| `language` | Document language | `Vietnamese`, `English` |

## Example

User: `/wikidoc-search ethics consent forms BV175`

Agent:
1. Reads `processed/index.json`.
2. Filters for entries where `Scope = BV175` and `Type = ETH` or keywords contain "consent".
3. Returns:
   - `20260410_BV175_ETH_ICF_Template.docx` — Informed Consent Form template for BV175 ethics submissions.
   - `20260312_BV175_ETH_ApprovalLetter.pdf` — IRB approval letter for BV175 study.
