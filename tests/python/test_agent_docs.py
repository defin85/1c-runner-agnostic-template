from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.python.agent_docs import (
    _CURATED_PATH,
    _command_is_repo_owned,
    _Docs,
    _jq_text,
    _posix_to_python_regex,
    _quickstart_rows,
)


class AgentDocsCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_docs(self, check: str, *args: str) -> tuple[int, str]:
        docs = _Docs(self.root)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            getattr(docs, check)(*args)
        return docs.status, stderr.getvalue()

    def test_missing_required_markdown_link_fails(self) -> None:
        self.write("AGENTS.md", "See `docs/agent/architecture.md` without a link.\n")

        status, stderr = self.run_docs("require_markdown_link", "AGENTS.md", "docs/agent/architecture.md")

        self.assertEqual(status, 1)
        self.assertIn("missing required markdown link in AGENTS.md: docs/agent/architecture.md", stderr)

    def test_present_markdown_link_passes(self) -> None:
        self.write("AGENTS.md", "Start with [architecture](docs/agent/architecture.md).\n")

        status, stderr = self.run_docs("require_markdown_link", "AGENTS.md", "docs/agent/architecture.md")

        self.assertEqual((status, stderr), (0, ""))

    def test_missing_file_is_reported_once(self) -> None:
        docs = _Docs(self.root)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            docs.require_contains("README.md", "one")
            docs.require_contains("README.md", "two")

        self.assertEqual(stderr.getvalue().count("missing or unreadable agent-facing path: README.md"), 1)

    def test_check_links_reports_broken_link_anchor_and_agent_reference(self) -> None:
        self.write("docs/target.md", "# Раздел проверки\n")
        self.write(
            "docs/index.md",
            "\n".join(
                [
                    "[ok](target.md#раздел-проверки)",
                    "[gone](missing.md)",
                    "[bad anchor](target.md#unknown)",
                    "Read @/docs/absent.md first.",
                    "[web](https://example.com/page)",
                    "",
                ]
            ),
        )

        status, stderr = self.run_docs("check_links", "docs/index.md")

        self.assertEqual(status, 1)
        self.assertIn("broken markdown link in docs/index.md:2: missing.md", stderr)
        self.assertIn("missing markdown anchor in docs/index.md:3: target.md#unknown", stderr)
        self.assertIn("broken agent path reference in docs/index.md:4: @/docs/absent.md", stderr)
        self.assertNotIn("раздел-проверки", stderr)
        self.assertNotIn("example.com", stderr)

    def test_placeholder_pattern_uses_posix_classes_and_reports_original_pattern(self) -> None:
        self.write("automation/context/project-map.md", "Owner: <описание модуля>\n")

        status, stderr = self.run_docs(
            "require_no_placeholder_pattern", "automation/context/project-map.md", "<[[:alnum:]_][^>]*>"
        )

        self.assertEqual(status, 1)
        self.assertIn(
            "unexpected placeholder or template note in automation/context/project-map.md: <[[:alnum:]_][^>]*>",
            stderr,
        )

    def test_curated_path_stops_at_markdown_link_brackets(self) -> None:
        text = "See [.codex/README.md](../../.codex/README.md) and (docs/agent/index.md) or [scripts/a.sh]."
        self.assertEqual(
            sorted(set(_CURATED_PATH.findall(text))),
            [".codex/README.md", "docs/agent/index.md", "scripts/a.sh"],
        )

    def test_curated_path_check_accepts_existing_markdown_link_target(self) -> None:
        self.write(".codex/README.md", "# Codex\n")
        self.write("docs/agent/page.md", "Read [.codex/README.md](../../.codex/README.md).\n")
        status, stderr = self.run_docs("check_curated_paths", "docs/agent/page.md")
        self.assertEqual((status, stderr), (0, ""))

    def test_posix_to_python_regex(self) -> None:
        self.assertEqual(_posix_to_python_regex("<[[:alnum:]_][^>]*>"), r"<\w[^>]*>")
        self.assertEqual(_posix_to_python_regex("[[:space:]]+[[:alnum:]-]"), r"[\s]+[\w-]")

    def test_command_is_repo_owned(self) -> None:
        self.write("scripts/test/run-smoke.sh", "#!/usr/bin/env bash\n")

        self.assertTrue(_command_is_repo_owned(self.root, ["make", "smoke"]))
        self.assertTrue(_command_is_repo_owned(self.root, ["./scripts/test/run-smoke.sh"]))
        self.assertFalse(_command_is_repo_owned(self.root, ["make", "-n"]))
        self.assertFalse(_command_is_repo_owned(self.root, ["./scripts/test/missing.sh"]))
        self.assertFalse(_command_is_repo_owned(self.root, ["bash", "-lc", "echo ok"]))
        self.assertFalse(_command_is_repo_owned(self.root, []))

    def test_quickstart_rows_and_jq_text(self) -> None:
        table = "\n".join(
            [
                "| Контур | Статус | Профиль | Платформа | Доказательство |",
                "| --- | --- | --- | --- | --- |",
                "| `doctor` | `supported` | `env/local.json` | `linux` | `make doctor` |",
                "| plain | ignored | row | without | backticks |",
                "",
            ]
        )

        self.assertEqual(
            _quickstart_rows(table),
            {"doctor": ["supported", "env/local.json", "linux", "make doctor"]},
        )
        self.assertEqual(_jq_text(None), "null")
        self.assertEqual(_jq_text("text"), "text")
        self.assertEqual(_jq_text(True), "true")


if __name__ == "__main__":
    unittest.main()
