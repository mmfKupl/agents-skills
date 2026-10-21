#!/usr/bin/env python3
"""Convert Codex custom agent TOML files into Claude Code subagent Markdown files."""

import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

READ_ONLY_TOOLS = "Read, Grep, Glob, Bash, WebFetch, WebSearch"

CLAUDE_RUNTIME_NOTE = """## Claude Code runtime

These instructions were written for Codex. In Claude Code:
- read `CLAUDE.md` files as well as `AGENTS.md` files;
- Codex model names map to Claude models: Luna / `gpt-6-luna` / Terra -> `sonnet`,
  Sol / `gpt-6.1-sol` / `gpt-6-sol` -> `opus`, Astra / `gpt-6-astra` -> `fable`;
  effort levels are unchanged. When you name a model/effort, use the Claude name;
- there is no runner backend: you were started as a Claude Code subagent;
- do not start further subagents."""


def load_toml(path: Path) -> dict:
    text = path.read_text()
    if tomllib is not None:
        return tomllib.loads(text)
    # Minimal fallback for the flat key = "..." / key = """...""" files in agents/.
    data = {}
    for match in re.finditer(r'^(\w+)\s*=\s*"""\n?(.*?)"""', text, re.S | re.M):
        data[match.group(1)] = match.group(2)
    for match in re.finditer(r'^(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"\s*$', text, re.M):
        data.setdefault(match.group(1), json.loads(f'"{match.group(2)}"'))
    return data


def convert(path: Path) -> str:
    agent = load_toml(path)
    for key in ("name", "description", "developer_instructions"):
        if not agent.get(key):
            raise ValueError(f"{path}: missing {key}")
    lines = [
        "---",
        f"name: {agent['name']}",
        f"description: {json.dumps(agent['description'], ensure_ascii=False)}",
    ]
    if agent.get("sandbox_mode", "read-only") == "read-only":
        lines.append(f"tools: {READ_ONLY_TOOLS}")
    lines += [
        "---",
        "",
        f"<!-- Generated from agents/{path.name} by scripts/codex_agents_to_claude.py. Edit the TOML, not this file. -->",
        "",
        agent["developer_instructions"].strip(),
        "",
        CLAUDE_RUNTIME_NOTE,
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: codex_agents_to_claude.py <agents-dir> <output-dir>", file=sys.stderr)
        return 2
    source, target = Path(argv[1]), Path(argv[2])
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.glob("*.toml")):
        out = target / f"{path.stem}.md"
        out.write_text(convert(path))
        print(f"Converted {path.name} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
