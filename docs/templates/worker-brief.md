# Worker brief: <id> — <one-line title>

<!-- Checklist for a worker or scout dispatch. Copy the headings you need. -->

## Objective
<What to produce, in two to four sentences.>

## Read first
- `CLAUDE.md` — operating principles and hardware traps
- <path> — <why>
- Fixed interface (when agents share a file format or module): <tracked path in the repo>.
  If a name you need is missing, fail with "stale interface: <name>" rather than guess.

## Write allowlist
- <paths>
- Anything that reads those files (`grep -rl <filename>`): run it before reporting.

## Constraints
- Budget: <time box> and <N> turns. Write the report before ~80% of the turns are spent.
- No hardware actuation, no `ssh cymac1`, no push, no deletions (list candidates instead).
- Every number carries its source and the conditions it was computed for (I, h, divisor,
  date). Reusing it under other conditions means recomputing it or saying it was not.
- Report the exit code and summary line of every tool you are told to run.
- Runs longer than ~10 min: run in ≤10-min pieces, or hand back the exact command and
  expected outputs.

## Deliverable
Write to: <absolute path>. Create the skeleton first and update it after each step.
Final message: path, status (done / partial / blocked), checks run and skipped, assumptions.

<!-- Orchestrator side, not for the prompt:
- Before sending 2+ writers out, commit the shared tree (or give each its own branch).
- Wait for the notification; don't poll.
- Check the result yourself before using it. -->
