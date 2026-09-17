# GPT-6 Astra profile

Local profile ID: `gpt-6-astra`; reviewed 2026-09-17. Not an API identifier.

Source: [OpenAI model guidance, Prompting best practices](https://developers.openai.com/api/docs/guides/latest-model). Model-specific recommendations below paraphrase the official guide; the tests are project proposals, not observed results.

OpenAI describes greater sensitivity to skill/project instructions, more clarification in ambiguous tasks, potentially broad verification for small coding changes, and delegation that may need explicit tuning. State the result, authority and stopping conditions rather than imposing a generic reasoning script. Keep writing requirements appropriate to the requested artifact.

When those symptoms appear, first remove conflicting defaults. Let already-authorized reversible work proceed; ask only about material decisions that genuinely block correctness or exceed permissions. Stop verification once relevant checks pass unless new evidence justifies more. Delegate independent investigation only where available tools and expected benefit support it. Never demand hidden chain-of-thought.

Test authorized follow-through versus reserved decisions; a typo versus a permission-sensitive migration; explicit and implicit skill requests; conflicting optional instructions versus a genuine hard constraint. Compare a minimal contract and the unmodified skill before retaining extra control text. Record real host/effort settings; this profile does not set provider parameters or prove a quality gain.
