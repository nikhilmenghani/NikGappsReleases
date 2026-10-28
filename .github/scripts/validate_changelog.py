"""Require real release notes for the exact public version before building or signing."""
import re
import sys
from pathlib import Path


def validate(text, version):
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version):
        raise ValueError("Invalid release version")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    sections = []
    current = None
    fence = None
    for line in text.splitlines():
        stripped = line.strip()
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if marker:
            value = marker.group(1)
            if fence is None:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        if re.match(r"^#{1,2}\s", stripped):
            current = None
            heading = re.fullmatch(r"##\s+v?(\d+\.\d+(?:\.\d+)?)(?:\s+[—|]\s+\d{4}-\d{2}-\d{2})?", stripped)
            if heading and heading.group(1) == version:
                current = []
                sections.append(current)
            continue
        if current is not None:
            item = re.match(r"^(?:[-*+]|\d+[.)])\s+(\S.*)$", stripped)
            if item:
                current.append(item.group(1))
    if len(sections) != 1:
        raise ValueError(f"Expected exactly one changelog heading for {version}; found {len(sections)}")
    meaningful = [item for item in sections[0] if not re.fullmatch(r"(?:TODO|TBD|coming soon)[.!…]*", item, re.I)]
    if not meaningful:
        raise ValueError(f"Changelog {version} must contain at least one change")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: validate_changelog.py VERSION CHANGELOG.md")
    version, path = sys.argv[1:]
    try:
        validate(Path(path).read_text(encoding="utf-8-sig"), version)
    except (OSError, ValueError) as error:
        raise SystemExit(f"{error}. Commit and push the source changelog before updating the public version file.") from None
    print(f"Changelog validated for {version}")


if __name__ == "__main__":
    main()
