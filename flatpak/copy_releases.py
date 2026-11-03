"""Write an app's metainfo with the <releases> of OpenLinkHub Client's metainfo.

The three apps (see src/olhclient/edition.py) ship from one tag with the same release notes, which
are written once, in io.github.mdmatthias.OpenLinkHub-Client.metainfo.xml. Every manifest runs:

    python3 copy_releases.py <source metainfo> <app metainfo> <output>

The text is spliced, not re-serialised, so the files keep their layout.
"""

import re
import sys

RELEASES = re.compile(r"[ \t]*<releases\s*/>|[ \t]*<releases>.*?</releases>", re.DOTALL)


def copy_releases(source: str, target: str) -> str:
    """``target`` with its <releases> element (or ``<releases/>``) replaced by the one in ``source``."""
    releases = RELEASES.search(source)
    if releases is None:
        raise ValueError("the source metainfo has no <releases>")
    result, count = RELEASES.subn(lambda _: releases.group(0), target, count=1)
    if count != 1:
        raise ValueError("the app metainfo has no <releases> to replace")
    return result


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    source, target, output = sys.argv[1:]
    with open(source, encoding="utf-8") as f:
        source_text = f.read()
    with open(target, encoding="utf-8") as f:
        target_text = f.read()
    with open(output, "w", encoding="utf-8") as f:
        f.write(copy_releases(source_text, target_text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
