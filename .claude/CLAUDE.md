## Git (hard rules)

- Never add "Co-authored-by: Claude" or any AI attribution to commit messages.
- Never use Claude as the commit author.
- Always use the Git author configured in this repository.
- Do not modify the Git author, committer, or email configuration.

## Plan before building

- Non-trivial work (3+ steps, or any architectural decision) starts in plan
  mode. Write the plan to `tasks/todo.md` as checkable items and confirm it
  before implementing.
- If the approach goes sideways mid-task, stop and re-plan. Do not keep pushing
  a failing approach.
- Mark items complete as you go. Add a short review section to `tasks/todo.md`
  when the unit of work is finished.

## Lessons

- After any correction from me, append to `tasks/lessons.md`: what went wrong,
  and the rule that prevents it recurring. Write the rule for yourself, not a
  description of the incident.
- Read `tasks/lessons.md` at the start of a session before touching code.

## Definition of done

- Never report a task complete without proving it. Run the tests, the
  typecheck, and the lint; verify against the running app where behaviour
  changed.
- State plainly what you verified and what you did not. "Tests pass" and "I did
  not open a browser" are both useful; implying a check you did not run is not.
- Before presenting non-trivial work, ask whether a staff engineer would approve
  it — and whether there is a more elegant approach. If a fix feels hacky,
  redo it properly rather than shipping it. Skip this for obvious one-liners.

## Bugs

- Given a bug report, a failing test, or an error log: investigate and fix it.
  Find the root cause. No temporary patches, no asking to be walked through it.

## Changes

- Simplest change that solves the problem. Touch only what the task requires.
- Prefer a small, correct change over a broad refactor that risks new bugs.

## Subagents

- Use them for broad read-only research — sweeping many files or directories
  where only the conclusion matters — to keep the main context clean.
- Do not spawn one for work that can be done inline. Each starts cold and
  re-derives context, so it is the expensive path.
