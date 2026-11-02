"""Write the metainfo release notes of one version as Markdown for a GitHub release.

Usage: python release_notes.py <version or tag> <output.md> [metainfo.xml]
"""

import sys
import xml.etree.ElementTree as ET

DEFAULT_METAINFO = "flatpak/io.github.mdmatthias.OpenLinkHub-Client.metainfo.xml"


def _text(element: ET.Element) -> str:
    """The element's text with inline markup flattened and whitespace collapsed."""
    return " ".join("".join(element.itertext()).split())


def release_notes(version: str, metainfo_path: str = DEFAULT_METAINFO) -> str | None:
    """The notes of ``version`` as Markdown, or None when the metainfo has no entry for it."""
    version = version.removeprefix("v")
    root = ET.parse(metainfo_path).getroot()
    for release in root.iterfind("releases/release"):
        if release.get("version") != version:
            continue
        description = release.find("description")
        if description is None:
            return ""
        blocks = []
        for child in description:
            if child.tag == "p":
                blocks.append(_text(child))
            elif child.tag in ("ul", "ol"):
                bullet = "-" if child.tag == "ul" else "1."
                blocks.append("\n".join(f"{bullet} {_text(li)}" for li in child.iterfind("li")))
        return "\n\n".join(blocks)
    return None


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    version, output, *metainfo = sys.argv[1:]
    notes = release_notes(version, *metainfo)
    if notes is None:
        print(f"::error::No <release version=\"{version.removeprefix('v')}\"> in the metainfo")
        return 1
    with open(output, "w", encoding="utf-8") as f:
        f.write(notes + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
