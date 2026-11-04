#!/usr/bin/env python3
"""audit-devil checks: the parser, the evidence verifier, and the loud failure.

Run: python3 -I tests/test_audit_devil.py   (no deps, no network, no model call)
These exist because `check` is the only thing standing between a fabricated
finding and a believed finding. If it stops catching bad citations, this fails.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin/audit-devil"

# Never read the operator's real defaults: every run below starts unconfigured.
for k in [k for k in os.environ if k.startswith("AUDIT_DEVIL_")]:
    del os.environ[k]
_CONF_DIR = tempfile.mkdtemp()
os.environ["AUDIT_DEVIL_CONFIG"] = str(Path(_CONF_DIR) / "config")

spec = importlib.util.spec_from_loader("ad", importlib.machinery.SourceFileLoader("ad", str(CLI)))
ad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ad)

fails = []


def ok(cond, label):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        fails.append(label)


# --- parser ---------------------------------------------------------------
REPORT = """\
## Verdict
Fix first.

### F1 silent except swallows write errors
severity: high
kind: audit
action: auto-fix
evidence: files/app.py:3, files/app.py:5-6
claim: the bare except hides a failed write
why-not-caught: no test exercises the failure path
fix: let the error propagate

### F2 same pattern in the retry helper
severity: medium
kind: postmortem
evidence: files/app.py:99
claim: duplicated swallow
why-not-caught: no lint rule for bare except
fix: add a lint rule
"""

f = ad.parse_report(REPORT)
ok(len(f) == 2, "parses both finding blocks")
ok(f[0]["id"] == "F1" and f[0]["severity"] == "high", "reads id and severity")
ok(f[0]["action"] == "auto-fix", "reads action field")
ok(f[0]["why-not-caught"] == "no test exercises the failure path", "reads hyphenated field")
ok(ad.parse_report("## Verdict\nlooks fine\n") == [], "no blocks -> no findings")

# --- evidence verifier ----------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    mat = Path(td) / "material"
    (mat / "files").mkdir(parents=True)
    (mat / "files/app.py").write_text("one\ntwo\nthree\nfour\nfive\nsix\n")

    ok(ad.locate(mat, "files/app.py:3")[0] == "OK", "resolves material-relative path")
    ok(ad.locate(mat, "app.py:3")[0] == "OK", "resolves repo-relative path via files/")
    ok(ad.locate(mat, "files/app.py:2-4")[2] == [(2, "two"), (3, "three"), (4, "four")],
       "quotes the cited range verbatim")
    ok(ad.locate(mat, "files/ghost.py:1")[0] == "MISSING", "invented file -> MISSING")
    ok(ad.locate(mat, "files/app.py:99")[0] == "OUTOFRANGE", "line past EOF -> OUTOFRANGE")
    ok(ad.locate(mat, "../../etc/passwd:1")[0] == "OUTSIDE", "path escape -> OUTSIDE")
    ok(ad.locate(mat, "app.py")[0] == "BADFORM", "no line number -> BADFORM")

    # --- check exits non-zero on an unverifiable finding ------------------
    b = Path(td) / "bundle"
    b.mkdir()
    (b / "meta.json").write_text(json.dumps({"id": "t", "preset": "cmd", "kind": "cmd",
                                             "material": str(mat)}))
    (b / "report.md").write_text(REPORT)  # F2 cites app.py:99, which does not exist
    r = subprocess.run([sys.executable, "-I", str(CLI), "check", str(b)],
                       capture_output=True, text=True)
    ok(r.returncode == 1, "check exits 1 when a citation cannot be verified")
    ok("unverified=1" in r.stderr, "check reports the unverified count")
    checked = (b / "checked.md").read_text()
    ok("UNVERIFIED (OUTOFRANGE)" in checked, "checked.md marks the bad citation")
    ok("three" in checked, "checked.md quotes the verified code")
    ok("decision: TODO" in (b / "verdict.md").read_text(), "verdict skeleton written")

    # a clean report verifies and exits 0
    (b / "report.md").write_text(REPORT.replace("evidence: files/app.py:99",
                                                "evidence: files/app.py:4"))
    (b / "checked.md").unlink()
    r = subprocess.run([sys.executable, "-I", str(CLI), "check", str(b)],
                       capture_output=True, text=True)
    ok(r.returncode == 0, "check exits 0 when every citation verifies")

    # Verdict + zero findings is a valid clean answer (the spec says so)
    (b / "report.md").write_text("## Verdict\nship: nothing found\n")
    r = subprocess.run([sys.executable, "-I", str(CLI), "check", str(b)],
                       capture_output=True, text=True)
    ok(r.returncode == 0, "check exits 0 on a clean verdict with no findings")

    # a bare heading with nothing under it is not a verdict
    (b / "report.md").write_text("## Verdict\n\n")
    r = subprocess.run([sys.executable, "-I", str(CLI), "check", str(b)],
                       capture_output=True, text=True)
    ok(r.returncode == 1, "check exits 1 on an empty Verdict heading")

    # no Verdict and no findings = the model ignored the format: fail loud
    (b / "report.md").write_text("Looks good to me!\n")
    r = subprocess.run([sys.executable, "-I", str(CLI), "check", str(b)],
                       capture_output=True, text=True)
    ok(r.returncode == 1, "check exits 1 when the report ignores the format")

    # a symlink loop is UNVERIFIED, not a traceback
    import os
    os.symlink(mat / "files/lb", mat / "files/la")
    os.symlink(mat / "files/la", mat / "files/lb")
    ok(ad.locate(mat, "files/la:1")[0] == "MISSING", "symlink loop -> MISSING, no crash")
    # a symlink escaping the root is OUTSIDE
    os.symlink("/etc/hosts", mat / "files/esc")
    ok(ad.locate(mat, "files/esc:1")[0] == "OUTSIDE", "symlink escape -> OUTSIDE")

# --- same-named --file outside root must not overwrite silently -----------
with tempfile.TemporaryDirectory() as td:
    for d in ("a", "b"):
        (Path(td) / d).mkdir()
        (Path(td) / d / "config.py").write_text(d)
    r = subprocess.run([sys.executable, "-I", str(CLI), "bundle", "--preset", "cmd", "--root", str(ROOT),
                        "--out", str(Path(td) / "out"), "--file", str(Path(td) / "a/config.py"),
                        "--file", str(Path(td) / "b/config.py")], capture_output=True, text=True)
    ok(r.returncode == 2 and "already taken" in r.stderr, "same-named --file -> usage error")

# --- --file naming a file --diff already brought in is not a collision ------
with tempfile.TemporaryDirectory() as td:
    repo = Path(td) / "r"
    repo.mkdir()
    g = lambda *c: subprocess.run(["git", "-C", str(repo), *c], capture_output=True, check=True)
    g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
    (repo / "a.py").write_text("1\n"); g("add", "."); g("commit", "-qm", "1")
    (repo / "a.py").write_text("2\n"); g("commit", "-qam", "2")
    r = subprocess.run([sys.executable, "-I", str(CLI), "bundle", "--preset", "cmd", "--root", str(repo),
                        "--out", str(Path(td) / "out"), "--diff", "HEAD~1..HEAD", "--file", "a.py"],
                       capture_output=True, text=True)
    ok(r.returncode == 0, "--diff + --file of the same file -> no collision")

# --- cmd send refuses an empty material set --------------------------------
with tempfile.TemporaryDirectory() as td:
    import os
    b = Path(td) / "b"
    b.mkdir()
    (b / "task.md").write_text("t")
    (b / "meta.json").write_text(json.dumps({"id": "e", "preset": "cmd", "kind": "cmd",
                                             "material": str(Path(td) / "gone")}))
    r = subprocess.run([sys.executable, "-I", str(CLI), "send", str(b)], capture_output=True, text=True,
                       env=dict(os.environ, AUDIT_DEVIL_CMD="cat"))
    ok(r.returncode == 1 and "missing or empty" in r.stderr, "cmd send with missing material -> fail loud")

# --- send records task_id only when delivered ------------------------------
with tempfile.TemporaryDirectory() as td:
    import os
    sk = Path(td) / "skill"
    sk.mkdir()
    for rc in (5, 4):
        (sk / "send.sh").write_text(f"cat >/dev/null; echo fake; exit {rc}\n")
        b = Path(td) / f"b{rc}"
        b.mkdir()
        (b / "task.md").write_text("t")
        (b / "meta.json").write_text(json.dumps({"id": f"t{rc}", "preset": "builder", "kind": "openbot"}))
        r = subprocess.run([sys.executable, "-I", str(CLI), "send", str(b)], capture_output=True,
                           text=True, env=dict(os.environ, OPENBOT_SKILL_DIR=str(sk)))
        tid = json.loads((b / "meta.json").read_text()).get("task_id")
        if rc == 5:
            ok(r.returncode == 1 and tid is None, "send.sh unreachable (5) -> no task_id")
        else:
            ok(r.returncode == 4 and tid == "ad-t4", "send.sh still running (4) -> task_id kept")

# --- cmd preset inlines the material (stdin models cannot open files) ------
with tempfile.TemporaryDirectory() as td:
    import os
    src = Path(td) / "repo"
    src.mkdir()
    (src / "app.py").write_text("alpha\nneedle-line\n")
    probe = Path(td) / "probe.sh"
    probe.write_text("#!/bin/sh\nif grep -q '2\tneedle-line' && true; then echo '## Verdict'; echo ok; else exit 9; fi\n")
    probe.chmod(0o755)
    env = dict(os.environ, AUDIT_DEVIL_PRESET="cmd", AUDIT_DEVIL_CMD=str(probe),
               AUDIT_DEVIL_OUT=str(Path(td) / "out"))
    r = subprocess.run([sys.executable, "-I", str(CLI), "bundle", "--root", str(src), "--file", "app.py",
                        "--id", "inl"], capture_output=True, text=True, env=env)
    r = subprocess.run([sys.executable, "-I", str(CLI), "send", r.stdout.strip()],
                       capture_output=True, text=True, env=env)
    ok(r.returncode == 0, "cmd send inlines material with line numbers")

# --- bundle refuses to guess ---------------------------------------------
r = subprocess.run([sys.executable, "-I", str(CLI), "bundle", "--preset", "cmd"],
                   capture_output=True, text=True, cwd=ROOT)
ok(r.returncode == 2 and "nothing to audit" in r.stderr, "bundle with no material -> usage error")

# --- choosing the second model: flag > env > config > ask (tty) > fail ----
with tempfile.TemporaryDirectory() as td:
    src = Path(td) / "repo"
    src.mkdir()
    (src / "a.py").write_text("x\n")
    conf = Path(td) / "conf"

    def bundle(*extra, **env):
        e = dict(os.environ, AUDIT_DEVIL_CONFIG=str(conf), AUDIT_DEVIL_OUT=str(Path(td) / "out"), **env)
        r = subprocess.run([sys.executable, "-I", str(CLI), "bundle", "--root", str(src), "--file", "a.py",
                            *extra], capture_output=True, text=True, env=e, stdin=subprocess.DEVNULL)
        meta = json.loads((Path(r.stdout.strip()) / "meta.json").read_text()) if r.returncode == 0 else None
        return r, meta

    r, _ = bundle("--id", "none")
    ok(r.returncode != 0 and "no second model configured" in r.stderr,
       "unconfigured + no terminal -> fails loud instead of guessing a model")

    r = subprocess.run([sys.executable, "-I", str(CLI), "config", "--preset", "nope"], capture_output=True,
                       text=True, env=dict(os.environ, AUDIT_DEVIL_CONFIG=str(conf)))
    ok(r.returncode != 0 and not conf.exists(), "config rejects an unknown preset and writes nothing")

    subprocess.run([sys.executable, "-I", str(CLI), "config", "--preset", "deepseek"], check=True,
                   capture_output=True, env=dict(os.environ, AUDIT_DEVIL_CONFIG=str(conf)))
    r, m = bundle("--id", "fromconf")
    ok(m and m["preset"] == "deepseek" and "--dir " + str(Path(m["material"]).resolve()) in (m["cmd"] or ""),
       "config default is used and {material} is filled in as an absolute path")

    r, m = bundle("--id", "fromenv", AUDIT_DEVIL_PRESET="cmd", AUDIT_DEVIL_CMD="cat")
    ok(m and m["preset"] == "cmd" and m["cmd"] == "cat", "env beats config")

    r, m = bundle("--id", "fromflag", "--preset", "builder", AUDIT_DEVIL_PRESET="cmd")
    ok(m and m["preset"] == "builder" and str(Path(td) / "out") in m["material"],
       "flag beats env, and AUDIT_DEVIL_OUT applies to every preset")

    conf.write_text("# my note\npreset=builder\nlang=en\n")
    subprocess.run([sys.executable, "-I", str(CLI), "config", "--preset", "deepseek"], check=True,
                   capture_output=True, env=dict(os.environ, AUDIT_DEVIL_CONFIG=str(conf)))
    ok(conf.read_text() == "# my note\nlang=en\npreset=deepseek\n",
       "config save keeps a person's comments and other keys, replaces only the set key")

    conf.write_text("cmd=cat\n")
    r, m = bundle("--id", "cmdonly")
    ok(m and m["preset"] == "cmd" and m["cmd"] == "cat", "a configured cmd alone implies the cmd preset")

# --- gate: no ruling, no progress ------------------------------------------
with tempfile.TemporaryDirectory() as td:
    def gate(decisions, ledger=None, checked="severity: high\nseverity: low\n"):
        b = Path(tempfile.mkdtemp(dir=td))
        (b / "meta.json").write_text(json.dumps({"id": "g", "preset": "cmd", "kind": "cmd",
                                                 "material": str(b)}))
        (b / "checked.md").write_text(checked)
        (b / "verdict.md").write_text("".join(
            f"## F{i} t\ndecision: {d}\nreason: {r}\n\n" for i, (d, r) in enumerate(decisions, 1)))
        cmd = [sys.executable, "-I", str(CLI), "gate", str(b)] + (["--ledger", str(Path(td) / ledger)]
                                                                  if ledger else [])
        return subprocess.run(cmd, capture_output=True, text=True), b

    r, _ = gate([("TODO", ""), ("accept", "")])
    ok(r.returncode == 3 and "ADJUDICATION-GATE: F1 未裁決" in r.stderr, "gate: undecided -> exit 3")
    r, _ = gate([("accept", ""), ("", "")])
    ok(r.returncode == 3 and "F2 未裁決" in r.stderr, "gate: blank decision -> exit 3")
    r, _ = gate([("accept", ""), ("reject", "")])
    ok(r.returncode == 3 and "F2 缺理由" in r.stderr, "gate: reject without reason -> exit 3")
    r, _ = gate([("reject", "not real"), ("defer", "next sprint")])
    ok(r.returncode == 0, "gate: all reject/defer with reasons -> exit 0")
    ok(r.stdout.strip() == "findings=2 high=1 accept=0 reject=1 defer=1", "gate: counts printed")
    r, _ = gate([("accept", ""), ("reject", "no")])
    ok(r.returncode == 10, "gate: any accept -> exit 10")
    (Path(td) / "nobundle").mkdir()
    r = subprocess.run([sys.executable, "-I", str(CLI), "gate", str(Path(td) / "nobundle")],
                       capture_output=True, text=True)
    ok(r.returncode == 3 and "verdict.md not found" in r.stderr, "gate: no verdict.md -> exit 3")

    # spinning means three non-decreasing >0 rounds in a row; 2,1 breaks it
    r, _ = gate([("accept", "")] * 2 + [("reject", "no")], ledger="l2.tsv")
    r, _ = gate([("accept", "")] * 2 + [("reject", "no")], ledger="l2.tsv")
    r, _ = gate([("accept", "")] * 3, ledger="l2.tsv")
    ok(r.returncode == 4 and "NOT-CONVERGING: accept 2,2,3" in r.stderr, "ledger 2,2,3 -> exit 4")
    r, _ = gate([("accept", "")] * 2 + [("reject", "no")], ledger="l1.tsv")
    ok(r.returncode == 10, "ledger round 1 (2 accept) -> exit 10")
    r, _ = gate([("accept", "")] + [("reject", "no")], ledger="l1.tsv")
    ok(r.returncode == 10, "ledger 2,1 -> exit 10, not 4 (progress)")
    r, _ = gate([("accept", "")] * 2 + [("reject", "no")], ledger="l1.tsv")
    ok(r.returncode == 10, "ledger 2,1,2 -> exit 10, not 4 (progress)")
    r, _ = gate([("accept", "")] * 2 + [("reject", "no")], ledger="l1.tsv")
    ok(r.returncode == 4 and "NOT-CONVERGING: accept 1,2,2" in r.stderr,
       "ledger 2,1,2,2 -> last 3 (1,2,2) spin -> exit 4")
    rows = (Path(td) / "l1.tsv").read_text().splitlines()
    ok(rows[0] == "round\ttime\tbundle\thigh\taccept" and len(rows) == 5,
       "ledger header written once, one row per round")
    ok(rows[-1].split("\t")[0] == "4" and len(rows[-1].split("\t")) == 5, "ledger row shape")
    ok((Path(td) / "l2.tsv").read_text().splitlines()[0] == "round\ttime\tbundle\thigh\taccept",
       "ledger gets its header on first write only")


# --- codex preset asks for a read-only sandbox -----------------------------
ok("codex" in ad.PRESETS and "-s read-only" in ad.PRESETS["codex"]["cmd"]
   and "{material}" in ad.PRESETS["codex"]["cmd"], "codex preset: read-only sandbox inside material")

print()
if fails:
    print(f"{len(fails)} check(s) failed:")
    for x in fails:
        print("  - " + x)
    sys.exit(1)
print("all checks passed")
