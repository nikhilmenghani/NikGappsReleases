import unittest
from validate_changelog import validate


class ChangelogValidationTest(unittest.TestCase):
    def test_dev_and_stable_exact_versions(self):
        validate("## 0.80.22\n- New change\n## 0.80.21\n- Previous", "0.80.22")
        validate("## v0.81 — 2026-10-28\n- Stable release", "0.81")

    def test_missing_or_similar_heading_rejected(self):
        for text in ("## 0.80.220\n- Wrong version", "## 0.80.21\n- Older release"):
            with self.assertRaises(ValueError):
                validate(text, "0.80.22")

    def test_empty_notes_do_not_borrow_previous_release_items(self):
        for text in ("## 0.80.22\n## 0.80.21\n- Old", "## 0.80.22\n- TBD", "## 0.80.22\n- TODO"):
            with self.assertRaises(ValueError):
                validate(text, "0.80.22")

    def test_duplicate_headings_rejected(self):
        with self.assertRaises(ValueError):
            validate("## 0.80.22\n- One\n## 0.80.22\n- Two", "0.80.22")

    def test_commented_and_fenced_release_notes_are_ignored(self):
        for text in ("<!--\n## 0.80.22\n- Hidden\n-->", "```markdown\n## 0.80.22\n- Example\n```", "## 0.80.22\n```\n- Example\n```"):
            with self.assertRaises(ValueError):
                validate(text, "0.80.22")

    def test_empty_version_rejected(self):
        with self.assertRaises(ValueError):
            validate("## 0.80.22\n- Change", "")


if __name__ == "__main__":
    unittest.main()
