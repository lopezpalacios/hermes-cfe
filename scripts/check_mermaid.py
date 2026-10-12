#!/usr/bin/env python3
"""Check that Markdown Mermaid blocks are non-empty and structurally fenced."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []
blocks = 0
for path in sorted(ROOT.rglob("*.md")):
    if any(part in {".git", "node_modules", ".venv"} for part in path.parts):
        continue
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"```mermaid\s*\n(.*?)\n```", text, flags=re.S):
        blocks += 1
        diagram = match.group(1).strip()
        if not diagram:
            errors.append(f"{path.relative_to(ROOT)}: empty Mermaid block")
        elif not re.match(r"^(flowchart|graph|sequenceDiagram|stateDiagram-v2|classDiagram|erDiagram|journey|mindmap|C4Context|C4Container)\b", diagram):
            errors.append(f"{path.relative_to(ROOT)}: missing recognized Mermaid diagram declaration")
        if diagram.count("subgraph ") != diagram.count("end") and diagram.startswith(("flowchart", "graph")):
            errors.append(f"{path.relative_to(ROOT)}: unbalanced subgraph/end count")
if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print(f"Mermaid source check OK: {blocks} fenced diagrams")
