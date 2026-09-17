# Source map

Read only when verifying a principle or refreshing host-dependent facts. Checked 2026-09-13. Sources are pointers, not runtime dependencies; the skill works without browsing. The full research synthesis is delivered outside the installed skill so it does not become startup context.

Standard constraints outrank incidental examples. Official recommendations, project-specific implementations, first-party experiments, and research findings have different evidential roles. No source guarantees this package improves performance. The exact published source text/code is not bundled.

- **S01 — Agent Skills**: [Agent Skills Specification](https://agentskills.io/specification). Continuously updated documentation.
- **S02 — Agent Skills**: [Best practices for skill creators](https://agentskills.io/skill-creation/best-practices). Continuously updated documentation.
- **S03 — Agent Skills**: [Optimizing skill descriptions](https://agentskills.io/skill-creation/optimizing-descriptions). Continuously updated documentation.
- **S04 — Agent Skills**: [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills). Continuously updated documentation.
- **S05 — Agent Skills**: [Using scripts in skills](https://agentskills.io/skill-creation/using-scripts). Continuously updated documentation.
- **S06 — Anthropic**: [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices). Continuously updated documentation.
- **S07 — Anthropic**: [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills). Published 2025-10-16; updated for the open standard on 2025-12-18.
- **S08 — Anthropic**: [The Complete Guide to Building Skills for Claude](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf). Publication date not confirmed in the source; 33-page PDF.
- **S09 — Anthropic**: [Skills for enterprise](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise). Continuously updated documentation.
- **S10 — OpenAI / ChatGPT Learn**: [Build skills](https://learn.chatgpt.com/docs/build-skills). Continuously updated documentation linked from earlier Codex documentation.
- **S11 — Eric Provencher / OpenAI**: [Rethinking skills and prompts for GPT-6 Astra](https://learn.chatgpt.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra). 2026-09-11.
- **S12 — OpenAI**: [skill-creator / SKILL.md](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md). Read from the main branch; not a pinned release.
- **S13 — Anthropic**: [skill-creator / SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md). Read from the main branch; not a pinned release.
- **S14 — Jesse Vincent / obra/superpowers**: [writing-skills / SKILL.md](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md). Read from the main branch; not a pinned release.
- **S15 — Paul Bakaus**: [Impeccable / SKILL.src.md](https://github.com/pbakaus/impeccable/blob/main/skill/SKILL.src.md). Read from the main branch; not a pinned release.
- **S16 — Minko Gechev**: [Best Practices for Creating Agent Skills](https://github.com/mgechev/skills-best-practices/blob/main/README.md). Read from the main branch; not a pinned release.
- **S17 — Vercel**: [AGENTS.md outperforms skills in our agent evals](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals). 2026-01-27.
- **S18 — Xiangyi Li et al.**: [SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks](https://arxiv.org/abs/2602.12670v4). v4, 2026-06-14.
- **S19 — Zhiyu Chen et al.**: [SkillJuror: Measuring How Agent Skill Organization Changes Runtime Behavior](https://arxiv.org/abs/2606.11543v1). v1, 2026-06-10.
- **S20 — Anthropic**: [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents). 2025-09-29.
- **S21 — Anthropic / Claude Code**: [Extend Claude with skills](https://code.claude.com/docs/en/skills). Continuously updated documentation.
- **S22 — Thariq Shihipar**: [Lessons from Building Claude Code: How We Use Skills](https://www.linkedin.com/pulse/lessons-from-building-claude-code-how-we-use-skills-thariq-shihipar-iclmc). Post reviewed; exact publication date not confirmed.

## How the evidence is used

S01 establishes format; S02–S06 inform authoring and evaluation; S07–S09 motivate packaging and trust checks; S10–S13 inform host differences and implementation patterns. S14–S16 supply concrete project experience, not mandatory universal policies. S17 warns that discovery must be tested. S18 (v4) and S19 (v1) support matched evaluation and task-dependent structural effects, not fixed performance promises. S20–S22 inform context and operational boundaries.

The ten-round ceiling, four result states, conservative packager, and preservation/report schemas are original engineering choices for this package. They are not claimed as official Agent Skills requirements.

## Model-aware improvement update — verified 2026-09-17

- **S23 — OpenAI:** [Model guidance / prompting best practices](https://developers.openai.com/api/docs/guides/latest-model). Live guidance read for Astra; profiles are scoped hypotheses, not unconditional policies.
- **S24 — Anthropic:** [Prompting Claude Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1). Host/API integration advice is separated from skill text.
- **S25 — Anthropic:** [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), 2026-01-09. Outcome grading, grader calibration, capability/regression distinction.
- **S26 — Research:** [GEPA](https://arxiv.org/abs/2507.19457); [ACE](https://arxiv.org/abs/2510.04618). Design motivation for feedback-driven candidates and incremental knowledge preservation, not a performance guarantee or bundled optimizer.

The model profiles, experiment protocol, rule categories and candidate lifecycle are this project's engineering choices. Evidence kinds and provenance are not proof that an adapter actually used a named model. The new runtime tests use synthetic adapters only; real model comparisons remain not_run until recorded.
