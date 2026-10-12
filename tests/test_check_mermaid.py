import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_mermaid.py"


class MermaidCheckTests(unittest.TestCase):
    def run_check(self, markdown):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "diagram.md").write_text(markdown, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_rejects_subgraph_missing_end_even_when_node_label_contains_end(self):
        result = self.run_check(
            "```mermaid\nflowchart TD\n  subgraph A\n  a[weekend]\n```\n"
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unbalanced subgraph/end", result.stderr)

    def test_rejects_unclosed_mermaid_fence(self):
        result = self.run_check("```mermaid\nflowchart TD\n  A --> B\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unclosed Mermaid fence", result.stderr)

    def test_accepts_balanced_diagram(self):
        result = self.run_check(
            "```mermaid\nflowchart TD\n  subgraph A\n    a --> b\n  end\n```\n"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 fenced diagrams", result.stdout)


if __name__ == "__main__":
    unittest.main()
