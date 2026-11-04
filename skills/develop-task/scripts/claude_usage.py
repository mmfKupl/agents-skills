#!/usr/bin/env python3
"""Print per-subagent token usage for a Claude Code session.

The Agent tool reports only a total token count. Claude Code also writes every
subagent transcript to <config>/projects/<project>/<session>/subagents/, and
each assistant message there carries the API usage block. This script sums
those blocks per subagent and for the main session.

Some Claude Code versions write only the usage from the start of a response:
stop_reason stays empty and output_tokens is a small placeholder. Input columns
are still right, but output is unknown for those responses, so it is reported
as n/a or as a lower bound, never as a total.

Usage: claude_usage.py [--session ID] [--json]
The session defaults to $CLAUDE_CODE_SESSION_ID.
"""

import argparse
import glob
import json
import os
import sys

FIELDS = ("uncached_in", "cache_write", "cached_in", "out", "thinking")


def read_usage(path):
    """Sum usage over unique assistant messages in one transcript."""
    by_message = {}
    models = []
    for line in open(path, encoding="utf-8"):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") or {}
        usage = message.get("usage")
        if entry.get("type") != "assistant" or not usage:
            continue
        # One API response is split into several lines; the last one wins.
        by_message[message.get("id") or entry.get("uuid")] = usage, message.get("stop_reason")
        model = message.get("model")
        if model and model not in models and not model.startswith("<"):
            models.append(model)

    totals = dict.fromkeys(FIELDS, 0)
    missing = 0
    for usage, stop_reason in by_message.values():
        totals["uncached_in"] += usage.get("input_tokens", 0)
        totals["cache_write"] += usage.get("cache_creation_input_tokens", 0)
        totals["cached_in"] += usage.get("cache_read_input_tokens", 0)
        if stop_reason is None:
            missing += 1
            continue
        totals["out"] += usage.get("output_tokens", 0)
        details = usage.get("output_tokens_details") or {}
        totals["thinking"] += details.get("thinking_tokens", 0)
    totals["requests"] = len(by_message)
    totals["requests_without_output"] = missing
    if by_message and missing == len(by_message):
        totals["out"] = totals["thinking"] = None
    totals["models"] = models
    return totals


def format_out(row):
    if row["out"] is None:
        return "n/a"
    text = "{out:,} ({thinking:,})".format(**row)
    missing = row["requests_without_output"]
    return f">= {text}, {missing} of {row['requests']} requests unknown" if missing else text


def find_session_dir(config_dir, session):
    matches = glob.glob(os.path.join(config_dir, "projects", "*", session))
    return matches[0] if matches else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.session:
        sys.exit("No session: pass --session or set CLAUDE_CODE_SESSION_ID")

    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    session_dir = find_session_dir(config_dir, args.session)
    if not session_dir:
        sys.exit(f"Session {args.session} not found under {config_dir}/projects")

    rows = []
    for path in sorted(glob.glob(os.path.join(session_dir, "subagents", "agent-*.jsonl")),
                       key=os.path.getmtime):
        agent_id = os.path.basename(path)[len("agent-"):-len(".jsonl")]
        meta = {}
        meta_path = path[:-len(".jsonl")] + ".meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        row = read_usage(path)
        row.update(agent_id=agent_id, agent_type=meta.get("agentType", "n/a"),
                   description=meta.get("description", ""))
        rows.append(row)

    main_path = session_dir + ".jsonl"
    main_row = read_usage(main_path) if os.path.exists(main_path) else None

    if args.json:
        json.dump({"session": args.session, "subagents": rows, "main": main_row},
                  sys.stdout, indent=2)
        print()
        return

    print("| Agent | Role | Description | Model | Requests | Uncached in | Cache write | Cached in | Out (thinking) |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in rows + ([dict(main_row, agent_id="main", agent_type="main", description="")]
                       if main_row else []):
        print("| {agent_id} | {agent_type} | {description} | {model} | {requests} | {uncached_in:,} "
              "| {cache_write:,} | {cached_in:,} | {out_text} |".format(
                  model=", ".join(row["models"]) or "n/a", out_text=format_out(row), **row))


if __name__ == "__main__":
    main()
