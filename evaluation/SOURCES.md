# Benchmark research and attribution

Research/retrieval date: 2026-09-18 (Korea Standard Time). Source artifacts were
retrieved through the connected GitHub app; upstream revisions below are pinned.
Only primary sources informed technical design. Case reuse is distinguished from
method inspiration; benchmark/framework names do not imply endorsement.

| Source | What was reused | What was not claimed |
|---|---|---|
| `idnotbe/skill-quality-builder` at `14d607873f0626e7a938d7855d391fb6916e5d4c` | All 67 existing cases across six suites, with repaired inputs, shared checks, dimensions, language variants and stage separation. Byte pins appear in the generator. | Existing empty observations are not results. Public examples are not private heldouts. |
| [Anthropic skill-creator](https://github.com/anthropics/skills/tree/34040c9c568585f6929bedeaad110ad08f079624/skills/skill-creator) | Method inspiration: positive/negative trigger queries, repetitions, baseline/candidate comparison, rubric grading and iterative review. | No Anthropic prompt is counted as a reused domain task. Its runner was not imported or executed. |
| [SkillsBench](https://github.com/benchflow-ai/skillsbench/tree/9a1f4dd5f7659f75707435da3ce854b6e48321d1) | Task/input/oracle/verifier separation and actual manufacturing codebook data. | This reduced derivative is not a complete SkillsBench task or comparable leaderboard score. |
| [SkillsBench manufacturing task](https://github.com/benchflow-ai/skillsbench/blob/9a1f4dd5f7659f75707435da3ce854b6e48321d1/tasks/manufacturing-codebook-normalization/task.md) | Product-specific codebook normalization, source spans and UNKNOWN handling. | Original confidence-distribution and full-log grading are deliberately outside this small child-task derivative. |
| [Manufacturing codebook](https://github.com/benchflow-ai/skillsbench/blob/9a1f4dd5f7659f75707435da3ce854b6e48321d1/tasks/manufacturing-codebook-normalization/environment/data/codebook_P1_POWER.csv) | Five verbatim data rows: EL-001, EL-002, EL-008, SD-015, SD-017. New compact input records exercise these rows. | The original log-file fetch returned empty content. No log row is falsely described as copied. The two U202 labels are indistinguishable; both codes are valid. |
| [Anthropic issue #1478](https://github.com/anthropics/skills/issues/1478) | A reported failure mechanism suggested the crash-versus-negative regression test. | This is a maintainer-repository user report, not an independently verified statement about all current versions. |
| [Anthropic issue #1427](https://github.com/anthropics/skills/issues/1427) | Reported worker-context contamination and early detection motivated isolated packets and late-selection checks. | This harness does not assert it repaired or reproduced that external runtime. |
| [GitHub Models retirement](https://docs.github.com/en/github-models) and [official announcement](https://github.blog/changelog/2026-07-30-github-models-is-now-retired/) | Explains why the former model-inference option cannot supply current evaluation trials. | A failed API call is not a negative trigger observation, and is not proof of the UI interruption's cause. |

The research found useful **skill-use benchmarks, skill-creation evaluation
workflows and evaluation tooling**, not a single ready-made, authoritative test
set that covers every behavior of this particular meta-skill. Therefore existing
repository cases were the primary source; external data/methods filled specific
gaps before new cases were authored. SkillsBench and skill-creator serve different
purposes; neither alone tests this builder's read-only audits or preservation rules.

## Third-party notice

`fixtures/codebook.csv` is a modified subset of the SkillsBench codebook referenced
above. Source task attribution: Di Wang @Foxconn, as recorded in task metadata.
Original project: benchflow-ai/skillsbench. License: Apache License 2.0; the full
license accompanies this package as `LICENSE-APACHE-2.0.txt`. Modifications:
selected five rows, omitted other products/codes, added separate synthetic task
records and a reduced output schema. No original copyright notice was removed
from the copied data; its source CSV contains only its header and data rows.

The license file is the standard Apache 2.0 license text obtained from the pinned
Anthropic skill-creator snapshot. No claim is made that it re-licenses the existing
repository or user-authored files. Existing synthetic fixture permission notices
remain intact. No private or customer data is included.
