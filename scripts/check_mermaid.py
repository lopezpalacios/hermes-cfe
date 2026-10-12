#!/usr/bin/env python3
"""Check Markdown Mermaid blocks for valid fences and basic structure."""
import argparse
from pathlib import Path
import re
import sys


DECLARATION = re.compile(
    r"^(flowchart|graph|sequenceDiagram|stateDiagram-v2|classDiagram|erDiagram|"
    r"journey|mindmap|C4Context|C4Container)\b"
)
OPEN_FENCE = re.compile(r"^\s*(`{3,})\s*mermaid\s*$", re.IGNORECASE)
CLOSE_FENCE = re.compile(r"^\s*(`{3,})\s*$")


def check_markdown(root: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    blocks = 0
    for path in sorted(root.rglob("*.md")):
        if any(part in {".git", "node_modules", ".venv"} for part in path.parts):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        line_number = 0
        while line_number < len(lines):
            opening = OPEN_FENCE.match(lines[line_number])
            if not opening:
                line_number += 1
                continue

            blocks += 1
            fence = opening.group(1)
            start_line = line_number + 1
            line_number += 1
            diagram_lines: list[str] = []
            closed = False
            while line_number < len(lines):
                closing = CLOSE_FENCE.match(lines[line_number])
                if closing and len(closing.group(1)) == len(fence):
                    closed = True
                    break
                diagram_lines.append(lines[line_number])
                line_number += 1

            location = f"{path.relative_to(root)}:{start_line}"
            diagram = "\n".join(diagram_lines).strip()
            if not closed:
                errors.append(f"{location}: unclosed Mermaid fence")
            if not diagram:
                errors.append(f"{location}: empty Mermaid block")
            elif not DECLARATION.match(diagram):
                errors.append(f"{location}: missing recognized Mermaid diagram declaration")
            elif diagram.startswith(("flowchart", "graph")):
                # Structural keywords are standalone statements; a node label
                # such as [weekend] is not an `end` statement.
                subgraphs = sum(bool(re.match(r"^\s*subgraph(?:\s|$)", line)) for line in diagram_lines)
                ends = sum(bool(re.match(r"^\s*end\s*$", line)) for line in diagram_lines)
                if subgraphs != ends:
                    errors.append(f"{location}: unbalanced subgraph/end count")

            line_number += 1 if closed else 0

    return errors, blocks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    errors, blocks = check_markdown(root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Mermaid source check OK: {blocks} fenced diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
