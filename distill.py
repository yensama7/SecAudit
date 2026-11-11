#!/usr/bin/env python3
"""secaudit distill — build the distilled-knowledge library, headless.

Drives Claude Code (same launcher resolution as audit.py) to run the knowledge
distillation workflow against a source, convergently: read reports one at a
time, extract "what to look for / how it's fixed" lessons, merge them into
`.claude/skills/security-audit/knowledge/<category>.md`, and stop when the source
stops teaching anything new. Reports are never stored — only the distilled
lessons. Re-running resumes from the saved cursor in `knowledge/distill-state.json`.

    python distill.py --source sherlock      # do this first
    python distill.py --source cyfrin         # then this
    python distill.py --source sherlock --dry-run

Needs a working Claude Code launcher (claude-work / claude; or SECAUDIT_CLAUDE_BIN)
and, for PDF sources, PyMuPDF available to the `python` Claude will call.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from audit import PROJECT_ROOT, find_claude_binary


def build_prompt(source: str) -> str:
    return (
        "Run the knowledge distillation workflow now. Read and follow exactly:\n"
        "  .claude/skills/security-audit/workflows/distill-knowledge.md\n\n"
        f"SOURCE: {source}\n"
        "Pull reports with `python intelligence-engine/report_feed.py --source "
        f"{source} --index N` (use --count first). Extract distinct vulnerability "
        "lessons (what to look for / root cause / how it was fixed) and merge them "
        "into .claude/skills/security-audit/knowledge/<category>.md per that "
        "directory's README format. Deduplicate aggressively: sharpen or add a "
        "'Seen in' URL rather than appending near-duplicates.\n\n"
        "Persist knowledge/distill-state.json after every report so the run is "
        "resumable. Run the CONVERGENT loop: stop this source when no_new_streak "
        "reaches the convergence_threshold, or when all reports are consumed. "
        "Update knowledge/INDEX.md counts at the end. Report what you added."
    )


def build_command(claude_bin: str, model: str | None, extra: list[str]) -> list[str]:
    cmd = [claude_bin, "-p", "--permission-mode", "acceptEdits"]
    if model:
        cmd += ["--model", model]
    cmd += extra
    low = claude_bin.lower()
    if os.name == "nt" and (low.endswith(".bat") or low.endswith(".cmd")):
        cmd = ["cmd", "/c", *cmd]
    return cmd


def _kill_tree(proc) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, text=True)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        proc.kill()


def run_with_budget(cmd: list[str], prompt: str, budget: int) -> int:
    """Run the nested session with streaming-JSON output, meter cumulative
    tokens, and kill the process TREE once they cross `budget`. Metered on
    input+output+cache tokens reported per assistant/result event. The distill
    workflow checkpoints distill-state.json per report, so a mid-run stop is
    clean and resumable."""
    proc = subprocess.Popen(
        cmd, cwd=str(PROJECT_ROOT), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        start_new_session=(os.name != "nt"),
    )
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except Exception:
        pass

    total = 0
    msgs = 0
    killed = False

    def tally(u):
        if not isinstance(u, dict):
            return 0
        return sum(int(u.get(k, 0) or 0) for k in
                   ("input_tokens", "output_tokens",
                    "cache_read_input_tokens", "cache_creation_input_tokens"))

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            print(line, flush=True)  # distill.py / claude non-JSON lines
            continue
        usage = None
        if isinstance(ev, dict):
            t = ev.get("type")
            if t == "assistant" and isinstance(ev.get("message"), dict):
                usage = ev["message"].get("usage")
            elif t == "result":
                usage = ev.get("usage")
        if usage:
            msgs += 1
            total += tally(usage)
            print(f"[budget] msg {msgs}: cumulative ~{total}/{budget} tokens", flush=True)
            if total >= budget:
                print(f"[budget] reached {total} >= {budget}; stopping the "
                      f"distill process tree (resumable from the saved cursor).",
                      flush=True)
                killed = True
                _kill_tree(proc)
                break

    if not killed:
        proc.wait()
    print(f"[budget] done: killed={killed} messages={msgs} cumulative_tokens~={total}")
    if msgs == 0:
        print("[budget] NOTE: no token usage seen — the nested Claude session "
              "never produced output (rate limit, or a broken `claude` launcher "
              "on this PATH). Run from a terminal where `claude-work` works.")
    return 0 if killed else (proc.returncode or 0)


def main() -> None:
    ap = argparse.ArgumentParser(prog="distill.py",
                                 description="Distil historical reports into the knowledge library (headless).")
    ap.add_argument("--source", required=True, help="source name (e.g. sherlock, cyfrin)")
    ap.add_argument("--model", help="Claude model id (default: your Claude Code default)")
    ap.add_argument("--claude-bin", help="path to the claude launcher (or SECAUDIT_CLAUDE_BIN)")
    ap.add_argument("--claude-args", default="", help="extra args passed to claude, space-separated")
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="stop once the nested session's cumulative tokens cross "
                         "this budget (metered via streaming JSON; resumable)")
    ap.add_argument("--dry-run", action="store_true", help="print the command + prompt, don't run")
    args = ap.parse_args()

    try:
        claude_bin = find_claude_binary(args.claude_bin)
    except SystemExit:
        if not args.dry_run:
            raise
        claude_bin = "claude"

    prompt = build_prompt(args.source)
    extra = args.claude_args.split() if args.claude_args else []
    # Token metering needs streaming JSON from the nested session.
    if args.max_tokens and not any(a.startswith("--output-format") for a in extra):
        extra += ["--verbose", "--output-format", "stream-json"]
    cmd = build_command(claude_bin, args.model, extra)

    if args.dry_run:
        print("[distill] cwd:", PROJECT_ROOT)
        print("[distill] source:", args.source)
        if args.max_tokens:
            print("[distill] token budget:", args.max_tokens)
        print("[distill] command (prompt piped via stdin):")
        print("   " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        print("[distill] --- prompt (stdin) ---")
        print(prompt)
        return

    print(f"[distill] distilling '{args.source}' knowledge (convergent)"
          + (f", budget {args.max_tokens} tokens..." if args.max_tokens else "..."))
    if args.max_tokens:
        sys.exit(run_with_budget(cmd, prompt, args.max_tokens))
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), input=prompt,
                            text=True, encoding="utf-8")
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
