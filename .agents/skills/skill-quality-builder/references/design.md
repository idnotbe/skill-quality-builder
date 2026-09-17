# Design a useful skill

Read when creating a skill or changing its architecture. The root SKILL.md retains permissions, user synchronization, and final acceptance gates.

## Scope and evidence

Define a coherent repeatable job, not an entire profession. Gather the real inputs, successful output, difficult judgment, recurring corrections, required tools, and non-goals. Distinguish verified domain facts from proposed workflow. A generic knowledge dump is not a substitute for a worked case.

Use a short contract: “Given X, produce Y, preserving Z; ask or stop at Q.” Expose hard constraints separately from preferences. For example, an action-extraction skill may infer topic groupings but must not infer who accepted an assignment.

## Discovery

A description should identify the capability, request class, and important exclusion. Front-load distinctive words. Avoid broad claims such as “use for any business request.” Do not embed the workflow in the description. Test real paraphrases and near-misses in the user's language.

Separate trigger failures from execution failures. A short description is a hypothesis to test, not an optimization score.

## Placement decision

| Information | Location | Reason |
|---|---|---|
| Common acceptance and permission boundary | Root | Needed on every applicable execution |
| Selection between create/edit/audit | Root | Needed before branch files are loaded |
| Branch-specific procedure or domain rule | Directly linked reference | Read only for that branch |
| Non-obvious universal gotcha | Short root rule | The agent might not recognize a hidden trigger |
| Output shape | Small inline example or asset | Avoid ambiguous prose-only formatting |
| Deterministic conversion or validation | Script | Avoid reinventing fragile logic |
| Test inputs and expectations | Evaluation directory | Not part of execution instructions |
| Logs, snapshots, real private data | External workspace | Not shipped with the skill |

For each reference write: **when to read it, what it decides, and what output it enables**. Do not recursively require all reference files. Keep required references reachable from the root. Long references need a useful overview or contents, not an arbitrary mandatory line threshold.

## Instruction design

Specify actions with inputs, outputs, and failure handling. Replace “be accurate” with a domain-specific verification. Replace “do not hallucinate” with a concrete missing-information representation. Give one default path with explicit branch conditions; avoid a menu of equally recommended tools.

Match control to risk. Fix a dangerous migration sequence; leave a research framing decision flexible within evidence and user constraints. A hard upper bound prevents infinite iteration but should never become a quota to fill.

Examples should distinguish neighboring behaviors and obey the complete output contract. If output must contain only a table or another exact shape, do not append explanatory prose to the example. Label synthetic examples. Avoid examples with invalid names, product-only fields portrayed as standard, or fabricated environment capabilities.

When a skill consumes documents, messages, code, or other supplied content, decide explicitly whether that content is data. If it is, state that embedded commands carry no authority and cannot change permissions, tools, or output requirements. Put this trust boundary in the root when it applies to every run.

## Choose architecture

- **Small instruction-only skill:** one workflow, few exceptional rules, no repeated fragile computation.
- **Root plus conditional references:** several paths share the same purpose and contract, but need different details.
- **Multiple skills:** distinct user intents, owners, permissions, or release cycles; do not split just to meet a word count.
- **Script-backed skill:** deterministic parsing, validation, or packaging is repeated and worth testing once.

Compare alternatives only when the choice matters. Discuss preserved constraints, discovery ambiguity, dependency risk, context cost, and testing burden. Prefer the least complex design that passes the target cases. Public benchmarks are motivation to test, not guarantees for this task.

## Final writing pass

Remove generic introductions, duplicated rules, stale scaffolding, and unsupported guarantees. Keep rationale only where it changes decisions. Preserve stable terminology and explicit path bases. Verify the final emitted files, not an earlier outline.

## Model-aware expertise and judgment

For substantive design, use [quality improvement](quality-improvement.md) to extract evidence-backed judgment rules and contrasting cases. Use [model adaptation](model-adaptation.md) only for the actual builder/executor. Preserve degrees of freedom: meaningful alternatives and falsifiable recommendations for open analysis, exact sequences only for genuinely fragile operations. Do not add a mandatory reasoning transcript or copy every provider recommendation.
