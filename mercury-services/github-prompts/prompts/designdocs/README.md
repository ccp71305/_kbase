# Design Doc Prompt Library — Index

Prompts for generating and publishing Confluence design documents for mercury-services.

## Which prompt to use

| Task | Prompt |
|------|--------|
| Analyze a defect / find root cause / produce implementation plan | `../analysis/issue-analysis-generator.md` |
| Generate + publish an **architecture / defect-fix** design doc | `confluence-design-doc-generator.md` ← start here |
| Generate + publish an **API design** doc | `confluence-api-design-generator.md` |
| Generate + publish a **feature spec** | `confluence-feature-spec-generator.md` |
| Generate + publish a **runbook** | `confluence-runbook-generator.md` |
| First-time MCP / Confluence setup | `SETUP-confluence-mcp.md` |

## Typical workflow

```
1. Run issue-analysis-generator.md  →  produces <module>/docs/<date>-<ticket>.md
2. Implement the fix (branch → failing test → fix → all tests pass)
3. Run confluence-design-doc-generator.md  →  publishes design doc to Confluence
```

For API design, feature specs, and runbooks: skip step 1 and feed your own source document
into the relevant generator's `INPUT_ANALYSIS_FILE` parameter.

## Shared base files (do not edit inline — update here)

| File | Used by |
|------|---------|
| `_base-confluence-publisher.md` | All generator prompts (Steps 4–5: XHTML conversion, create/update, verify) |
| `../_base-session-protocol.md` | All prompts (session create/resume, context logging, completion) |
| `convert_design_doc.py` (repo root) | XHTML converter referenced by `_base-confluence-publisher.md` |

## Templates

Section schemas live in `templates/`. Generators reference them via `DESIGN_DOC_TEMPLATE`.

| Template | Doc type |
|----------|----------|
| `templates/architecture-template.md` | Architecture / defect-fix design docs |
| `templates/api-design-template.md` | API design docs |
| `templates/feature-spec-template.md` | Feature specs |
| `templates/runbook-template.md` | Runbooks |

## Completed instances

Past design doc runs (produced artifacts, published to Confluence) are in `completed/`.
Past analysis/fix runs are in `../analysis/completed/`.

## Prerequisites

- MCP server configured and SSO session valid → see `SETUP-confluence-mcp.md`
- `convert_design_doc.py` present at repo root (used for XHTML conversion)
