#!/usr/bin/env python3
"""audit-devil checks: the parser, the evidence verifier, and the loud failure.

Run: python3 -I tests/test_audit_devil.py   (no deps, no network, no model call)
These exist because `check` is the only thing standing between a fabricated
finding and a believed finding. If it stops catching bad citations, this fails.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin/audit-devil"

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

# --- bundle refuses to guess ---------------------------------------------
r = subprocess.run([sys.executable, "-I", str(CLI), "bundle", "--preset", "cmd"],
                   capture_output=True, text=True, cwd=ROOT)
ok(r.returncode == 2 and "nothing to audit" in r.stderr, "bundle with no material -> usage error")

print()
if fails:
    print(f"{len(fails)} check(s) failed:")
    for x in fails:
        print("  - " + x)
    sys.exit(1)
print("all checks passed")
