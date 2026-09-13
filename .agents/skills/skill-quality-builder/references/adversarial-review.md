# Counterexample-driven review

Read for substantial changes or unresolved failures. Scale the depth to risk and complexity. A typo correction does not need a review ceremony.

## Review packet

Use the original request, agreed contract, current candidate files, preservation map, observed outputs, test records, and open issues. Verify all evidence corresponds to the same candidate version. Do not grade an outline while delivering different files.

## Concrete challenges

1. Find a realistic request that should not activate this skill but shares its vocabulary.
2. Follow a branch with a missing input or unavailable dependency. Does it stop safely or fabricate?
3. Move through the reference route. Is a required condition hidden behind a file the agent will not know to read?
4. Compare original and candidate. Did name, format, license, metadata, or a non-obvious exception disappear?
5. Put an instruction-like sentence inside an input document. Is it treated as data or as authority?
6. Read the claimed test results. Did any simulation, unexecuted check, or static test become a performance claim?
7. Run an already successful case after the change. Is the “fix” overfitted to the newest example?

Each finding needs **criterion, counterexample/evidence, impact, proposed minimal fix, retest, and status**. Unsupported suspicion is a hypothesis, not a proven failure.

## Severity

- Critical: unauthorized disclosure/action, source destruction, fabricated verification, or lost hard constraint with material impact.
- Major: repeated wrong triggering, unusable output, unreachable necessary resources, or broken core workflow.
- Minor: isolated ambiguity, avoidable context cost, presentation inconsistency.

Do not offset critical issues with unrelated high scores. Close a finding only with evidence of a fix, a demonstrated counterargument, or explicit acceptance of a noncritical residual risk. “We changed the sentence” is not necessarily a successful retest.

## Revision control

Group fixes by root cause. Keep the original baseline unchanged. Re-test affected and prior-success cases after each material change. Default maximum is ten revision rounds and one major redesign; stop earlier on success. Two rounds with no material progress or a budget limit mean pause, not pass.

A different role prompt in the same agent is not an independent evaluator. Label the method actually used. Summarize reasons and observed evidence; do not expose or demand private internal reasoning.
