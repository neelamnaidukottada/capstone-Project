# PROMPT_SEQUENCES

## Purpose
Reusable Copilot Agent Mode prompt patterns for specification-driven, AI-first implementation.

## Sequence 1: Requirement Lock
Prompt template:
"Read REQUIREMENTS.md and list the frozen in-scope features only. Refuse to add out-of-scope work. Produce acceptance checks for each in-scope item."

Expected output:
- In-scope checklist
- Acceptance checks
- Explicit out-of-scope exclusions

## Sequence 2: Contract-First Implementation
Prompt template:
"Using SPEC.md, implement or update only one contract slice at a time: schema -> service -> route -> test. Do not proceed if schema is ambiguous."

Expected output:
- Modified files by slice
- Contract test updates
- Notes on unresolved schema gaps

## Sequence 3: Dependency-Aware Build
Prompt template:
"Follow DEPENDENCIES.md strictly. Verify upstream prerequisites before any new code change. Stop and report if prerequisite is missing."

Expected output:
- Dependency validation result
- Safe next implementation target
- Blockers list (if any)

## Sequence 4: Gate-Driven Progress
Prompt template:
"Check CHECKPOINTS.md for current phase gate criteria. Validate green status before starting next phase."

Expected output:
- Gate status (green/yellow/red)
- Evidence references
- Approved next phase or stop condition

## Sequence 5: Demo Readiness Sweep
Prompt template:
"Validate DELIVERABLES.md checklist and README phase status. Report remaining demo blockers in priority order."

Expected output:
- Completed deliverables
- Missing deliverables
- Priority-ordered blocker list
