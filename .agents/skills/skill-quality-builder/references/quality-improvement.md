# Improve the target's work, not just its instructions

Read for substantive creation/improvement or unexplained task failures. Keep tiny authorized edits tiny. Use [improvement notes](../assets/improvement.template.md) only when they help; they are external working records, not extra mandatory context in every target skill.

## 1. Find the missing expertise

Start from real inputs, corrections, good/bad outputs and project records. Ask what decision the expert changed and why, not merely which wording they preferred. Extract a small knowledge card: source/version, scope, application condition, decision rule, positive example, nearest counterexample, and evidence that would invalidate it. Distinguish user constraints from facts and preferences. Do not promote one user's style preference into a universal domain rule.

A useful card says: a proposed owner is not an accepted owner; leave owner blank without acceptance. A weak card says: extract accurately. A contrasting pair changes only acceptance, not names or prose length. Preserve useful exceptions when compressing; remove generic explanations the executor already knows. An unsupported card remains a hypothesis requiring external feedback, not manufactured expertise.

## 2. Diagnose before adding instructions

| Observed symptom | Competing explanation | Test / possible intervention |
|---|---|---|
| Skill not selected | Discovery text or competing skills | Natural positive/near-negative prompts; adjust metadata only |
| Selected but evidence not loaded | Poor placement or unclear read condition | Inspect actual reads; change placement rather than adding warnings |
| Wrong instruction followed | Incorrect rule | Domain counterexample; replace/delete the rule |
| Correct rule ignored | Conflict, ambiguous scope or excess context | Isolate competing guidance and replay |
| Tool loop fails | Wrong schema, error response or environment | Fix tool contract/environment, not more forceful prompting |
| Valid alternative fails grading | Overprescriptive judge | Repair grader and regrade both conditions |
| Cannot finish despite correct plan | Output budget or unnecessary approvals | Inspect runtime and authorization; adjust only the real cause |

For each diagnosis record exact input/trace evidence, a rival explanation, proposed minimal intervention and a retest that could disprove it. A model-written causal story is provisional. Check successful runs as well as failures. Do not treat a failed network request as proof the prompt needs rewriting.

## 3. Improve judgment and exploration selectively

For open-ended analysis, test whether the problem framing or causal mechanism is wrong. Ask what evidence would reverse the recommendation; whether eliminating or changing the sequence/ownership of a task beats speeding it up; and whether a supposed constraint is actual or assumed. Alternatives should work through different mechanisms, not different labels. Compare at least one serious rival when the choice is consequential; do not require three options or a fixed reasoning transcript in every task.

Synthetic process example: 45 minutes of work plus three days of approval waiting suggests investigating handoff/approval readiness, not only automating the 45 minutes. When approval is mandatory, removing it violates the contract. A paired case with no approval delay should not force the same redesign. Reward useful reframing when supported, and reward keeping the original framing when evidence supports it. Do not reward novelty alone or force contrarianism.

## 4. Test different changes, not endless rewrites

Compare no skill, immutable original, minimal contract/core facts, and a targeted candidate when useful. Keep raw inputs, available facts, tools and executor settings equal; otherwise report the information or environment confound. A no-skill baseline may receive the same task-specific facts as ordinary input, without the skill's strategy.

Candidate hypotheses: delete unnecessary scaffolding; add a missing judgment rule/contrast; or move a deterministic operation to a tested script/tool. Change one causal factor where practical. Keep the current best candidate until evidence warrants replacement. Ten rounds remain a ceiling, not a quota; stop after two rounds without material new evidence. Reopening the same self-review is not independent feedback.

## 5. Observe multiple dimensions and guard against overfitting

Track completion, correctness, judgment, usefulness, safety and exact format separately. Separate capability cases from regression cases. Compare matched assertions, not inflated aggregate scores from adding easy checks. Use fresh tasks not exposed during generation, distinct project/data contexts, repeated trials where appropriate and all reported failures. Public examples are development material, not a private holdout. Repeated checks from one run are not independent samples.

Evaluate actual final artifacts/state and attempted tool actions. Do not require one exact tool sequence when other legitimate routes satisfy the contract. For analysis, review sources, missing decision-changing conditions, meaningful alternatives and required human rework; blind A/B review is useful but judges need calibration. Mutate a good result by removing a key fact, inventing an owner or bypassing approval: the grader should reject it. Also supply a valid different approach that should pass. A rubric derived only from the candidate's own instructions is circular evidence.

The [quality transfer suite](../evals/quality-transfer-cases.json) covers extraction, analysis and bounded actions. Specialize it to one coherent target job; do not make every generated skill handle all domains. The [grader calibration cases](../evals/grader-calibration-cases.json) test whether an evaluator accepts valid alternatives and rejects concrete defects. Their outcomes remain unverified until actually observed.

## 6. Retain, revise, split, tool, retire or leave unchanged

A successful builder may recommend no change, delete a model workaround, split unrelated jobs, move fragile computation into code, or retire a skill whose removal does not hurt task results. Never delete a user requirement or license to improve a metric. Classify feedback as personal/project/domain before promoting it. Record accepted/rejected changes, evidence and rollback identity outside the installed bundle. Use small edits to preserve accumulated expertise rather than replacing the whole playbook each round.

## Research basis and limits

[Agent Skills authoring guidance](https://agentskills.io/skill-creation/best-practices) motivates real expertise and execution-based refinement. [Anthropic agent evaluations](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) distinguishes outcome grading, human calibration and capability/regression tests. [GEPA](https://arxiv.org/abs/2507.19457) motivates feedback-driven candidate search; [ACE](https://arxiv.org/abs/2510.04618) motivates preserving useful context during incremental updates. These are design inputs, not evidence this builder improves Astra/Fable performance. No external optimizer or model API is required.
