#!/usr/bin/env python3
"""secaudit — one-command security audit CLI.

Point it at a GitHub URL or a local folder. It drives the Claude Code
`security-audit` skill in headless mode and collects the final report.

    python audit.py https://github.com/org/repo
    python audit.py ./path/to/repo
    python audit.py ./repo --output ./audits --model claude-opus-4-8

How it talks to Claude
----------------------
It does NOT call the Anthropic API directly. It launches Claude Code
non-interactively (`claude -p`) from THIS project directory, so the
`security-audit` skill (.claude/skills/) and the `audit-intel` MCP server
(.mcp.json) are auto-discovered. The target repo is granted to Claude via
`--add-dir`. Claude then runs the same flow as interactive `/security-audit`:
repository discovery -> full-source coverage -> findings -> validated handoff
-> historical-intelligence retrieval -> final report. Auth is your existing
Claude Code login; there is no per-token API key and no separate agent loop to
maintain — Claude Code *is* the harness.

The exact `claude` command is assembled in build_claude_command() below. Run
with --dry-run to print it without executing (recommended before your first
live run, especially if your `claude` launcher isn't on PATH).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

GIT_URL_PREFIXES = ("http://", "https://", "git@", "ssh://", "git://")


def is_git_url(target: str) -> bool:
    t = target.strip()
    return t.startswith(GIT_URL_PREFIXES) or t.endswith(".git")


def find_claude_binary(override: str | None) -> str:
    """Resolve the Claude Code launcher.

    Order: explicit --claude-bin / $SECAUDIT_CLAUDE_BIN, then `claude-work`
    (preferred — it sets CLAUDE_CONFIG_DIR to your work profile), then `claude`,
    then common install locations. On Windows the bare npm `claude` shim is known
    to break, so `claude-work` / `claude.cmd` are preferred.
    """
    if override:
        return override
    env = os.environ.get("SECAUDIT_CLAUDE_BIN")
    if env:
        return env
    for name in ("claude-work", "claude.cmd", "claude"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd",
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".claude" / "local" / "claude",
    ]
    for c in candidates:
        if c and c.exists():
            return str(c)
    raise SystemExit(
        "error: could not find a Claude Code launcher (tried claude-work, claude).\n"
        "       Set SECAUDIT_CLAUDE_BIN=/path/to/claude-work (or pass --claude-bin)."
    )


def resolve_target(target: str, branch: str | None, workdir_root: Path) -> tuple[Path, bool]:
    """Return (local_path_to_audit, was_cloned)."""
    if is_git_url(target):
        workdir_root.mkdir(parents=True, exist_ok=True)
        name = target.rstrip("/").split("/")[-1].removesuffix(".git") or "repo"
        dest = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=workdir_root))
        cmd = ["git", "clone", "--depth", "1", "--single-branch",
               "-c", "http.postBuffer=524288000"]
        if branch:
            cmd += ["--branch", branch]
        cmd += [target, str(dest)]
        print(f"[secaudit] cloning {target} -> {dest}")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            raise SystemExit(f"error: git clone failed (exit {r.returncode})")
        return dest, True
    p = Path(target).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"error: path does not exist: {p}")
    if not p.is_dir():
        raise SystemExit(f"error: not a directory: {p}")
    return p, False


def build_audit_prompt(target: Path, report_dir: Path) -> str:
    return (
        "Run a complete security audit using the `security-audit` skill.\n\n"
        f"AUDIT ROOT: {target}\n"
        "Treat that directory as the repository under audit. Do NOT audit this "
        "current working directory (it holds the audit tooling, not the target).\n\n"
        "Follow the skill end to end: repository discovery, full-source coverage "
        "(every in-scope file tracked in the coverage ledger), vulnerability "
        "hunting with evidence, validated handoff, then automatic historical "
        "intelligence retrieval and per-finding verification.\n\n"
        f"Write all audit artifacts to: {report_dir}\n"
        f"The submittable report MUST be written to: {report_dir / 'final-report.md'}\n"
        "Do not claim the audit is complete if any in-scope file was not examined."
    )


def build_claude_command(claude_bin: str, target: Path, report_dir: Path,
                         model: str | None, extra: list[str]) -> list[str]:
    """Assemble the headless Claude Code invocation.

    The prompt is NOT a positional arg — it is piped over stdin (see main), which
    sidesteps Windows batch quoting for the multi-line prompt. Stable flags used:
    `-p` (print/headless, reads the piped stdin), `--add-dir` (grant the target
    repo + report dir), `--permission-mode acceptEdits` (write the report
    unattended). Adjust here if your Claude Code version differs; pass extras via
    `--claude-args "..."`.

    On Windows, a `.bat`/`.cmd` launcher (e.g. claude-work.bat) is run through
    `cmd /c` so the batch file executes.
    """
    cmd = [
        claude_bin, "-p",
        "--add-dir", str(target),
        "--add-dir", str(report_dir),
        "--permission-mode", "acceptEdits",
    ]
    if model:
        cmd += ["--model", model]
    cmd += extra
    low = claude_bin.lower()
    if os.name == "nt" and (low.endswith(".bat") or low.endswith(".cmd")):
        cmd = ["cmd", "/c", *cmd]
    return cmd


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="audit.py",
        description="One-command security audit: GitHub URL or local folder -> submittable report.",
    )
    ap.add_argument("target", help="GitHub URL (https/git) or path to a local repo folder")
    ap.add_argument("--branch", help="branch to clone (git URL targets only)")
    ap.add_argument("--model", help="Claude model id (default: your Claude Code default)")
    ap.add_argument("--output", help="copy the final report here when done")
    ap.add_argument("--report-dir", help="where Claude writes artifacts "
                    "(default: <target>/.security-audit)")
    ap.add_argument("--claude-bin", help="path to the claude launcher "
                    "(or set SECAUDIT_CLAUDE_BIN)")
    ap.add_argument("--claude-args", default="",
                    help="extra args passed through to claude, space-separated")
    ap.add_argument("--keep", action="store_true",
                    help="keep the cloned repo (git targets) instead of deleting it")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the resolved claude command and exit")
    args = ap.parse_args()

    try:
        claude_bin = find_claude_binary(args.claude_bin)
    except SystemExit:
        if not args.dry_run:
            raise
        claude_bin = "claude"  # placeholder so --dry-run can still show the command
    work_root = PROJECT_ROOT / "storage" / "targets"
    target, cloned = resolve_target(args.target, args.branch, work_root)

    report_dir = (Path(args.report_dir).expanduser().resolve()
                  if args.report_dir else target / ".security-audit")
    report_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_audit_prompt(target, report_dir)
    extra = args.claude_args.split() if args.claude_args else []
    cmd = build_claude_command(claude_bin, target, report_dir, args.model, extra)

    if args.dry_run:
        print("[secaudit] project root (cwd for claude):", PROJECT_ROOT)
        print("[secaudit] audit root:", target)
        print("[secaudit] report dir:", report_dir)
        print("[secaudit] command (prompt piped via stdin):")
        print("   " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        print("[secaudit] --- prompt (stdin) ---")
        print(prompt)
        return

    print(f"[secaudit] auditing {target}")
    print(f"[secaudit] report -> {report_dir / 'final-report.md'}")
    # cwd = PROJECT_ROOT so the security-audit skill and audit-intel MCP server
    # are discovered from this project's .claude/ and .mcp.json. The prompt is
    # fed on stdin (claude -p reads it) to avoid batch/arg quoting problems.
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), input=prompt,
                            text=True, encoding="utf-8")

    report = report_dir / "final-report.md"
    if report.exists():
        print(f"[secaudit] report written: {report}")
        if args.output:
            out = Path(args.output).expanduser().resolve()
            out.mkdir(parents=True, exist_ok=True)
            dest = out / f"{target.name}-final-report.md"
            shutil.copy2(report, dest)
            print(f"[secaudit] report copied: {dest}")
    else:
        print(f"[secaudit] WARNING: no final report at {report} "
              "(audit may have failed or been incomplete)", file=sys.stderr)

    if cloned and not args.keep:
        shutil.rmtree(target, ignore_errors=True)
        print(f"[secaudit] removed cloned repo {target}")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
