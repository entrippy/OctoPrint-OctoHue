# OctoHue Development Workflow

This document defines the cooperative development process between human and AI. Its purpose is to prevent false-positive feedback loops — the failure mode where AI writes bad tests, bad code that passes those tests, and a review that finds no problems, all within the same shared context.

## Honest accounting of AI independence

**Subagent context independence:** Claude can spawn subagents with clean contexts — no memory of the current conversation, no exposure to the reasoning behind the code. This provides meaningful independence from anchoring and conversation-level bias.

**Not model independence:** Subagents share the same underlying model. Systematic model-level blind spots (misunderstanding a protocol, a wrong assumption about an API) are shared. This is a real limitation.

**Human review is irreplaceable for:** domain correctness (does this CCT output actually look right on hardware?), security assumptions, architectural trade-offs, and anything requiring real-world validation.

---

## The five stages

### Stage 1 — Specification
*Who:* Human leads. AI grills. Both document.

1. Human states the goal in plain language
2. **Run the `grill-with-docs` skill** — AI interviews relentlessly about every aspect of the plan, one question at a time, waiting for an answer before continuing. For each question AI provides its recommended answer so the human is reacting to a concrete proposal, not answering in a vacuum. If a question can be answered by reading the codebase, AI does that instead of asking.
3. During the grilling session, AI actively:
   - **Challenges terminology** against any existing glossary in `CONTEXT.md` — if the human uses a term that conflicts with established language, call it out immediately
   - **Sharpens fuzzy language** — when vague or overloaded terms appear, propose a precise canonical term
   - **Stress-tests with concrete scenarios** — invent edge cases that force precision about boundaries
   - **Cross-references with existing code** — if the human states how something works, check whether the code agrees and surface any contradiction
4. As terms are resolved, update `CONTEXT.md` inline — do not batch these up
5. Offer an ADR only when all three are true: the decision is hard to reverse, it would surprise a future reader without context, and it was the result of a genuine trade-off with real alternatives
6. Both agree explicit acceptance criteria and known edge cases before any code is written

**Gate:** Human signs off on the spec. `CONTEXT.md` reflects any new or revised terms. No code until this is done.

**Note on `CONTEXT.md`:** If none exists yet, create it when the first term is resolved. Keep it free of implementation details — only terms meaningful to a domain expert belong here.

---

### Stage 2 — Test design (tests first)
*Who:* AI writes. Subagent challenges. Human gates.

1. AI writes tests from the spec only — no implementation knowledge
2. Tests are run against a stub implementation that always returns wrong/empty values — **every test must fail**. A test that passes against a stub is not testing anything
3. **Subagent adversarial review of tests** (fresh context — see prompt discipline below):
   - "What valid behaviours do these tests fail to cover?"
   - "What broken implementation could pass all of these tests?"
4. Human reads every test case and must be able to state in plain language what it asserts and why — approval without understanding is not approval

**Gate:** Human confirms test completeness before any implementation is written. Findings from the subagent review are resolved, not skipped.

**Prompt discipline for subagent:** Give it the spec and the test file only. Do not include the implementation, do not include AI reasoning about the tests. Instruct it to find gaps and to describe code that would pass the tests but be wrong.

---

### Stage 3 — Implementation
*Who:* AI writes.

1. Code is written to make the failing tests pass
2. No new tests are written during this stage — if new tests are needed, the spec was incomplete and Stage 1 must be revisited
3. All tests must pass before proceeding

---

### Stage 4 — Adversarial review
*Who:* Subagent reviews. Human gates.

Two passes, both using subagents with fresh contexts:

**Pass A — Code review:**
Given: the spec, the diff, the tests. Not given: any AI reasoning about the implementation.
Task: find correctness issues, edge cases, security problems, spec violations. Explicitly ask: "What broken implementation could pass all these tests?"

**Pass B — Mutation testing:**
Given: the test file only.
Task: write three to five small deliberate mutations (wrong comparisons, off-by-one, missing guard) and identify which tests would catch each. Report any mutation that no test catches — those are test gaps requiring a return to Stage 2.

**Gate:** Every finding is triaged. Critical or warn findings block the merge and trigger a return to the appropriate stage. The human must read and understand the findings — not just accept that the AI resolved them.

---

### Stage 5 — Integration and e2e
*Who:* Human runs. AI assists interpretation.

1. Unit tests passing is necessary but not sufficient
2. For provider code: test against real hardware or a real API before merging to `devel`
3. For UI changes: manually verify in a browser
4. Failures here feed back to Stage 2

**Gate:** Real-world verification completed and logged before merge.

---

## What honest cooperation looks like

The human's role is not to rubber-stamp AI output. At each gate:
- Read the tests before approving them — if you cannot explain what a test asserts, it has not been reviewed
- Read the review findings — if the AI resolved a finding, check whether the resolution actually addresses it
- Challenge assumptions — if the AI states something as fact, ask how it knows

The AI's role is to be explicit about uncertainty:
- State assumptions as assumptions, not facts
- Flag when something has not been verified against real hardware or a live API
- Distinguish between "I found no bugs" and "this is correct"
- When spawning a subagent, state exactly what it was and was not given

---

## When to skip stages

Never skip Stage 2 (tests first) or Stage 4 (adversarial review).

Stage 1 can be abbreviated for genuinely trivial changes (typo fixes, comment corrections) where the spec is self-evident and the risk of misunderstanding is negligible. State explicitly when doing so.

Stage 5 can be deferred for backend-only changes with no hardware dependency, but must be completed before promoting to `rc`.
