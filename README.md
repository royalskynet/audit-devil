[繁體中文](README.zh-TW.md)

Let a second model play devil's advocate on your change (audit + post-mortem), require every finding to cite `path:line`, and mechanically verify each citation before you believe it.

## Why

Reviewing your own change means reviewing with your own blind spots. A second model has different blind spots, so it can catch what you missed — but it can also invent a citation that points at nothing. `check` turns a second opinion into a checkable second opinion: if a cited line does not exist, the run exits 1 instead of quietly handing you fiction.

## Install

```bash
git clone https://github.com/royalskynet/audit-devil
cd audit-devil
ln -s "$PWD/bin/audit-devil" ~/.local/bin/
```

Claude Code slash command (English):

```bash
ln -s "$PWD/commands/audit.en.md" ~/.claude/commands/audit.md
```

For the Chinese command, link `commands/audit.md` instead.

Requirements: Python 3.9+ and git. Nothing else.

## Pick your second model

Set `AUDIT_DEVIL_PRESET=cmd` and `AUDIT_DEVIL_CMD`. The command reads the prompt from stdin and writes the report to stdout. Adjust these to your installed CLI version; the author has only tested OpenBot and the `cmd` pipeline itself.

```bash
# Recommended: simonw/llm (Apache-2.0; plugins cover OpenRouter/Ollama/Gemini/Anthropic)
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='llm -m gpt-4o-mini'

# Any OpenRouter model through the llm plugin
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='llm -m openrouter/<model>'

# Other CLIs that take a prompt on stdin and print to stdout
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='codex exec -'
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='gemini -p ""'
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='ollama run qwen2.5-coder'
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='claude -p --model claude-sonnet-5-5'
```

The `builder` preset (the default) talks to the Builder agent of OpenBot, a local agent app. It needs the send-to-openbot skill (`OPENBOT_SKILL_DIR`); set `OPENBOT_AGENT=<id>` to use a different agent. Its reply arrives in a later turn, so you must `collect`.

## Quick start

```bash
audit-devil bundle --root . --diff HEAD~1..HEAD --note "what this change is for"
audit-devil send <bundle>
audit-devil collect <bundle>   # OpenBot only; skip for cmd
audit-devil check <bundle>
# read checked.md, then fill in verdict.md
```

A bundle directory holds `task.md` (the prompt), `material/` (the diff and full changed files), `meta.json`, `report.md` (the second model's answer), `checked.md` (every citation verified with the actual lines), and `verdict.md` (your rulings).

## Report format

The prompt is the `SPEC` constant in `bin/audit-devil`, reproduced verbatim:

```
You are the devil's advocate on this change. Your job is to find what is wrong
with it and to explain why nobody caught it. You are not here to approve it.

Two halves, both required:

AUDIT — defects in the material itself: wrong logic, unhandled failure, unsafe
input, race, silent fallback, dead or speculative code, a simpler correct form.
POST-MORTEM — for each defect answer: where else does this pattern appear in the
material, which layer should have stopped it (test, type, guard, hook, review),
and under what conditions it gets written again.

Rules:
- Every finding must cite real locations from the material as `path:line` or
  `path:line-line`. Paths are relative to the material root. A finding you
  cannot locate in the material does not go in the report.
- No praise, no summary of what the code does, no restating the task.
- If you believe the change is sound, say so in `## Verdict` and report only the
  findings you can actually evidence. An empty findings list is a valid answer.
- Rank findings highest severity first.
- Do a full pass before answering; do not stop at the first valid finding.
- Do not report style, formatting, lint or type-check issues, and no generic
  advice such as "add more tests". Only what genuinely matters.

Output format, exactly this, nothing before or after:

## Verdict
<one or two sentences: ship / fix first / cannot tell, and why>

### F1 <short title>
severity: high|medium|low
kind: audit|postmortem
action: auto-fix|ask-user|no-op
evidence: <path:line>[, <path:line-line> ...]
claim: <what is wrong, one or two sentences>
why-not-caught: <which layer was missing>
fix: <smallest change that fixes the cause, not the symptom>

action: auto-fix = correctness, error handling, security, performance — fixable
without discussing intent. ask-user = product behaviour or the author's deliberate
intent; when in doubt, ask-user. no-op = informational.

### F2 ...
```

## How check works

For each `evidence:` entry, `check` resolves the citation against the material root and reports one of:

- `OK` — the file and lines exist; the actual source lines are quoted.
- `MISSING` — the path does not exist in the material.
- `OUTOFRANGE` — the path exists but the cited lines fall outside the file.
- `OUTSIDE` — the path escapes the material root.
- `BADFORM` — the citation is not `path:line` or `path:line-line`.

A path may be material-relative (`files/x`) or repo-relative (`x`); both resolve. Exit 0 means every citation was verified. Exit 1 means at least one citation is `UNVERIFIED`, or no finding blocks could be parsed from the report at all. Exit 2 means the usage is wrong.

`OK` only proves those lines exist. It does not prove the claim is true. The verdict is still yours to make by reading the code.

## Verdict

Fill `verdict.md`. Each `decision:` is one of:

- `accept` — you verified it is true and will fix it this round.
- `reject` — you verified it is false or the location does not exist; say why in one sentence.
- `defer` — real but out of scope; record where it is being kept (issue / fixindex / state).

## Environment variables

| Variable | Meaning | Default |
| --- | --- | --- |
| `AUDIT_DEVIL_PRESET` | Second-model preset: `builder` or `cmd` | `builder` |
| `AUDIT_DEVIL_CMD` | CLI for the `cmd` preset (stdin to stdout) | unset |
| `AUDIT_DEVIL_OUT` | Bundle parent directory | `./.audit-devil` for `cmd` |
| `AUDIT_DEVIL_LANG` | Language for the report prose | `zh-TW` (set `en` for English) |
| `OPENBOT_SKILL_DIR` | Directory of the send-to-openbot skill | `~/.claude/skills/send-to-openbot` |
| `OPENBOT_AGENT` | OpenBot agent id, overrides the builder agent | Builder agent |
| `OPENBOT_TIMEOUT` | How long OpenBot may take | `45m` |

## Limits

`check` verifies locations only, never the truth of a claim. With `--diff`, the full post-change files are included automatically; files over 512 KB and deleted files are skipped. Nothing is fixed automatically. No secret handling is done: the bundle contents are sent to the second model, so decide for yourself before running it on a sensitive repo.

## Prior art / Credits

The review rules borrow from the kunchenguid/grok-ship adversarial-review skill (MIT). simonw/llm is recommended as the second-model connection. BeehiveInnovations/pal-mcp-server offers similar multi-model code review; this tool's focus is citation verification.

## Tests

```bash
python3 -I tests/test_audit_devil.py
```

The tests run offline and never call a model.

## License

MIT.
