"""The repository installs as a Claude Code plugin whose skills Claude can load.

A marketplace entry that points at the wrong folder, a skill whose name differs from its folder, or
a path in a skill that names a file this repository no longer has all install without an error and
fail only when an agent reads the skill. These tests read the declarations back instead.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
MANIFEST = REPO / ".claude-plugin" / "plugin.json"
SKILLS = REPO / "skills"
PLUGIN_ROOT_VARIABLE = "${CLAUDE_PLUGIN_ROOT}"
PLUGIN_ROOT_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`)>]+)")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _frontmatter(skill_file: Path) -> dict[str, str]:
    """The `key: value` lines between the two `---` lines that open a SKILL.md."""
    lines = skill_file.read_text(encoding="utf-8").split("\n")
    if lines[0] != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return fields
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return {}


class TheMarketplaceListsThisRepositoryTest(unittest.TestCase):
    def test_it_lists_one_plugin_whose_source_is_the_repository_root(self) -> None:
        entries = _load(MARKETPLACE)["plugins"]
        self.assertEqual(len(entries), 1)
        source = (MARKETPLACE.parent.parent / entries[0]["source"]).resolve()
        self.assertEqual(source, REPO)

    def test_the_entry_and_the_manifest_carry_the_same_name(self) -> None:
        """A name that differs makes the install id a user types and the prefix of its skills two names."""
        entry = _load(MARKETPLACE)["plugins"][0]["name"]
        self.assertEqual(entry, _load(MANIFEST)["name"])

    def test_the_manifest_has_no_version_to_fall_behind_the_repository(self) -> None:
        """A version written here pins users to it until someone remembers to raise it with the release."""
        self.assertNotIn("version", _load(MANIFEST))
        self.assertNotIn("version", _load(MARKETPLACE)["plugins"][0])


class EverySkillCanBeLoadedTest(unittest.TestCase):
    def test_there_is_at_least_one_skill(self) -> None:
        self.assertTrue(list(SKILLS.glob("*/SKILL.md")))

    def test_each_skill_is_named_after_its_folder_and_says_when_to_use_it(self) -> None:
        for skill_file in sorted(SKILLS.glob("*/SKILL.md")):
            with self.subTest(skill=skill_file.parent.name):
                fields = _frontmatter(skill_file)
                self.assertEqual(fields.get("name"), skill_file.parent.name)
                self.assertTrue(fields.get("description"))

    def test_each_path_a_skill_reads_from_the_plugin_exists(self) -> None:
        for skill_file in sorted(SKILLS.glob("*/SKILL.md")):
            text = skill_file.read_text(encoding="utf-8")
            for relative in PLUGIN_ROOT_PATH.findall(text):
                with self.subTest(skill=skill_file.parent.name, path=relative):
                    self.assertTrue((REPO / relative).is_file(),
                                    f"{PLUGIN_ROOT_VARIABLE}/{relative} is not in this repository")


if __name__ == "__main__":
    unittest.main()
