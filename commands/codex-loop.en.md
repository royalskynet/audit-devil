---
description: Main session plans and rules, deep executes, codex audits and post-mortems, rulings feed the next round; gate mechanically decides convergence
argument-hint: "<计划或目标文件> [--repo <路径>] [--max-rounds N]"
---

Goal: $ARGUMENTS

## 1. Roles

- Main session: plans, rules, verifies only. **Never writes product code.**
- deep: executes via `deep-run <workorder.md> <worktree>` (bare name, in the background).
- Second model: audit-devil with `--preset codex` by default — audits, post-mortems, proposes optimisations.
- Without `--repo`, ask `git rev-parse --show-toplevel`; `--max-rounds` defaults to 6.

## 2. Every round

1. Write the work order `.audit-devil/<round>.md` (four sections: task / acceptance [one command per line, exit 0] / do-not-touch / forbidden).
2. `deep-lint <workorder>`; fix the work order rather than dispatching a failing one.
3. Open a worktree off main: `git worktree add <worktree> -b loop/<n> main`.
4. `deep-run <workorder.md> <worktree>` in the background; collect when it exits.
5. Main session reruns `wo-verify <workorder>` inside the worktree itself; on failure write a fix-up work order and go back to step 2.
6. Pass: `git merge --ff-only` into the main repo, rerun `wo-verify <workorder>` there.
7. Send for audit:
   ```bash
   audit-devil bundle --root <repo> --diff <this round's range> --preset codex \
     --note "<goal, last round's rulings, ask it to post-mortem prior must-fixes and propose optimisations>"
   audit-devil send <bundle>
   audit-devil check <bundle>     # exit 1: reject every fabricated finding
   ```
8. Rule on every finding in `<bundle>/verdict.md` (`decision:` = accept / reject / defer; reject and defer need `reason:`).
9. `audit-devil gate <bundle> --ledger <repo>/.audit-devil/loop.tsv`, then follow section 3.

## 3. By gate exit code

| exit | meaning | action |
| --- | --- | --- |
| 0 | converged, no accept | run final acceptance; commit / push as the user directs |
| 10 | accepts remain | turn accepted items into the next fix-up work order, back to step 2 |
| 3 | undecided or missing reason | fill in `verdict.md`, rerun gate |
| 4 | accept count flat or rising 3 rounds | **stop guessing**: change method (delegate to an Opus subagent or rewrite the plan) and report |

## 4. Hard rules

- Same item failing twice → delegate to an Opus subagent; do not retry the same path.
- The main session decides the fix; never copy the second model's fix.
- Never loosen an existing assertion in acceptance.
- Mutation check: remove this round's fix and its test must fail.
- At `--max-rounds` stop and report the remaining items and the last ledger round.

## 5. Wrap-up

- One line of conclusion (converged / cap reached / changed method).
- Per-round high / accept trend: `cat <repo>/.audit-devil/loop.tsv`.
- Options: where the defer items went, whether another round is worth it.
