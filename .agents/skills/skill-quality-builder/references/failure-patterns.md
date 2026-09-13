# Failure patterns and targeted repairs

Read when instructions are generic, bloated, or repeatedly ignored. This is a diagnostic catalog, not a checklist to expand every skill.

| Symptom | Why it happens | Repair | Check |
|---|---|---|---|
| Skill activates on almost everything | Broad domain words replace user intent | Name the action and exclusions | Near-miss trigger cases |
| Description is followed as the whole workflow | Too much process in metadata | Keep capability and activation cues; put procedure in body | Observe actual body read |
| Every reference is read | No branch predicates | Link each file with when/why | Trace loaded files per case |
| Very short root misses constraints | Compression removes invariants | Restore the minimal required guardrail | Risky boundary case |
| Full rewrite changes expected behavior | No preservation baseline | Map hard constraints before editing | Original-versus-candidate regression |
| “Do not guess” still produces invented fields | No alternative output behavior | State “missing means unassigned/unknown” | Incomplete-input example |
| Repeated code differs between runs | Fragile logic regenerated | Bundle tested deterministic code | Script unit and edge tests |
| “All tests passed” without logs | Confidence substitutes for observations | Require explicit state and evidence | Empty/missing evidence tests |
| More references improve no task | Content added without evidence | Remove low-value material in a candidate | Same-case comparison |
| Improvement only on the edited example | Overfitting | Use new/private cases and old successes | Regression and held-out checks |
| Script hangs | Interactive input or unbounded retry | CLI flags; bounded failure | No-input/invalid-input execution |
| Tool dependency silently assumed | Environment conflated with instructions | Check availability, then fallback | Tool-unavailable case |

## Repair examples

Instead of “Provide useful decisions and actions,” write: “Separate confirmed decisions from proposals. For every assigned action, retain the source-supported owner and due date; write unassigned or unspecified when absent.”

Instead of “Always review thoroughly three times,” write: “After a material change, test the affected criterion and an existing success case. Stop when the agreed criteria are met; pause if the remaining failure cannot be resolved within the budget.”

Instead of “Read all documents before starting,” write: “Read the contract first. Read the refactoring reference only when changing an existing bundle. Read platform guidance only when installation or host-specific metadata is part of the request.”

These are original examples of the package's method, not copied vendor policies.
