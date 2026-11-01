ADVISOR-CONSULT: <the one decision, in a single sentence>

<!-- Adapted 2026-11-01 from Alma's claude-config (github.com/aaronmarkowitz/claude-config, templates/orchestration/advisor-consult-brief.md). -->
<!--
Dispatch template for an advisor-consult proxy. Copy this into the dispatch prompt.

WHY THIS EXISTS. The advisor re-reads the entire transcript, uncached, on every call
(`cache_read_input_tokens` = 0, measured). So its latency and its failure probability
both scale with the size of the seat it is called from. Measured on one session:
138k advisor input tokens -> 114 s, success; 165k -> 262 s, success; a third call on the
same 47 MB transcript -> 362 s, `execution_time_exceeded`. Narrowing the QUESTION does
not shrink its INPUT. Only changing the SEAT does.

A dispatched worker's transcript is this brief plus a little work, so a consult from
there costs a page instead of a session. Verified 2026-09-17: a dispatched worker has
the advisor in its own tool surface and gets substantive guidance back.

WHEN TO USE IT. Second in the ladder, never first:
  1. Consult in-seat. Highest fidelity — the advisor sees everything you have done.
  2. If that returns an `advisor_tool_result_error`, dispatch this brief.
  3. If that fails too, tell Molly the consult failed and you are deciding without it.
Never decide alone and say nothing; `~/.claude/hooks/advisor-guard.py` blocks that handback.

THE LIMIT, AND YOU MUST REPORT IT. The proxy's advisor sees only this brief. It is a
consult on your framing, not on the situation. When you report what it said, say
"advisor saw brief only". If you cannot honestly fill in "What I am not telling you"
below, the question is not ready to be proxied.

The first line must keep the literal `ADVISOR-CONSULT:` sentinel: `.claude/agents/worker.md`
authorises the consult on it, and `~/.claude/hooks/advisor-guard.py` recognises the escalation by
it. Without the sentinel the dispatch is an ordinary worker that must not consult.
-->

## The decision
<One sentence. What will be different depending on the answer.>

## Why it is costly or hard to reverse
<What is spent, broken, or foreclosed if this goes the wrong way.>

## The facts it turns on
<3–8 bullets. Only what bears on the decision. Include the numbers and the file paths,
not the narrative. Each fact stated as a fact, with where it came from.>

## The options, with their costs
<Two or three. What each buys, what each costs, and which you currently favour and why —
say your leaning plainly; an advisor that cannot see your reasoning cannot correct it.>

## What I am NOT telling you
<MANDATORY. The context this brief omits: how long the session has run, what else is in
flight, which constraints you have already tested and discarded, what the surrounding
code or apparatus does. Name the omissions that could change the answer. This field is
what makes the proxy's answer weighable instead of merely cheap.>

## What a good answer looks like
<A verdict on the options, plus the one consideration you are most likely to have
missed. Say if you want it to attack a specific assumption.>

---

**Instructions to the dispatched worker** (keep these in the dispatch):

> You are an advisor-consult proxy. You are authorised to consult the advisor exactly
> once, overriding the standing "the advisor is for the orchestrators" line in your role
> prompt. Consulting is the purpose of this dispatch.
>
> Read only the files named above. Then consult the advisor, putting the decision and the
> facts to it in your own words, including the "What I am NOT telling you" section — the
> advisor must know what it cannot see.
>
> Report in this shape, and write no files:
> ```
> ADVISOR CONSULTED: yes | no (+ error_code if it failed)
> ADVISOR GUIDANCE (advisor saw brief only):
>   <faithful report. With a Fable advisor the guidance comes back encrypted, so you
>    cannot quote it — relay it in your own words and flag that as a paraphrase.>
> DISAGREEMENTS: <anything it said that the facts above contradict — do not smooth these over>
> YOUR VERDICT: <clearly labelled as yours, not the advisor's>
> ```
>
> If the advisor cannot be reached or returns an error, say so plainly in the first line
> and do NOT substitute your own opinion for its guidance. Report your own review clearly
> labelled as yours. A silent substitution is the exact failure this whole mechanism
> exists to prevent.
