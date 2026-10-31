---
description: Summon a second model as devil's advocate to run an audit + postmortem; the report comes back to the main session for mechanical verification, then adjudication and landed fixes
argument-hint: "[diff range | files…] [--incident <error transcript file>] [--model <preset>]"
---

Goal: $ARGUMENTS

**Audit + postmortem** task. You are the adjudicator; the second model is the devil's advocate — its findings are not facts until you verify them.
If no scope is given, audit `HEAD~1..HEAD` without asking first. CLI = `audit-devil` (on PATH; if missing, use the absolute path to `bin/audit-devil` in the install directory).

## 1. Bundle (done by the main session)

```bash
audit-devil bundle --root <repo 絕對路徑> \
  --diff <範圍> [--file <檔>]… [--incident <錯誤原文檔>] \
  --note "<它看不到的上下文：這次要解什麼、已排除什麼、哪裡最可疑>"
```

`--note` is the only lever in this step: the second model cannot see this session's conversation. Put the goal, the known trade-offs, and your own suspicions into it.
The output is the absolute path of the bundle directory — remember it. The default second model = OpenBot Builder; to use another OpenBot agent, set `OPENBOT_AGENT=<id>`,
or use `--preset cmd` together with `AUDIT_DEVIL_CMD='<CLI that reads stdin and writes stdout>'`.

## 2. Send

```bash
audit-devil send <bundle>
```

The OpenBot teammate's reply lands in a **later turn**; this turn only reports "dispatched" — no polling, no waiting.
`collect` retrieves the report (if it hasn't answered yet it exits 1, so do something else and collect later):

```bash
audit-devil collect <bundle>
```

## 3. Mechanical verification (cannot be skipped)

```bash
audit-devil check <bundle>
```

exit 1 = a finding's `evidence:` does not point to a real location, or the report has no `## Verdict` and no findings (format ignored). A Verdict with zero findings is a clean answer, exit 0 — still read the Verdict line.
`checked.md` attaches the actual code lines to each entry. Verification has two layers; do not conflate them:

- **Location**: `check` has already decided this mechanically. Reject every `UNVERIFIED` entry and name it explicitly in the report: "the second model fabricated N entries" — do not cover for it.
- **Claim**: `OK` only proves those lines exist, not that the claim is true. Read the code yourself and judge each one; when necessary, run a command that would fail to confirm.

## 4. Adjudicate

Fill in `<bundle>/verdict.md`; each `decision:` can only be:

- `accept` — you verified it as true; fix it in this round.
- `reject` — you verified it as false or the location does not exist; write one sentence on why.
- `defer` — true but out of this round's scope; state clearly where it is left (issue / fixindex / state).

Do not copy the second model's suggested fix: what you adopt is the **problem**; the fix is yours to decide (cure the cause, no opportunistic refactoring).

## 5. Land + accept

Fix every accepted item one by one, to the `/fix` standard: change the cause not the symptom, and attach a regression check that would fail to the same change.
The acceptance report pastes the raw output: the regression check and a rerun of `check` (exit 0).

## Wrap-up

- Report one line of conclusion + "accept N / reject N / defer N" + the bundle's absolute path + options. Leave the details in the bundle.
- If the second model fabricated something, or caught a real defect you missed this round, run `/fi` to record it if it's worth remembering.
