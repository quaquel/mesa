"""Update docs/_static/switcher.json for a new release tag."""

import json
import sys

SWITCHER_PATH = "docs/_static/switcher.json"


def update_switcher(tag: str) -> None:
    version = tag.lstrip("v")
    major_minor = ".".join(version.split(".")[:2])

    with open(SWITCHER_PATH) as f:
        switcher = json.load(f)

    # Remove older patch entry for the same minor version
    switcher = [
        e
        for e in switcher
        if not (
            e["version"] not in ("latest", "stable")
            and ".".join(e["name"].split(".")[:2]) == major_minor
        )
    ]

    new_entry = {
        "name": version,
        "version": tag,
        "url": f"https://mesa.readthedocs.io/en/{tag}/",
    }

    insert_pos = next(
        i for i, e in enumerate(switcher) if e["version"] not in ("latest", "stable")
    )
    switcher.insert(insert_pos, new_entry)

    with open(SWITCHER_PATH, "w") as f:
        json.dump(switcher, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    update_switcher(sys.argv[1])
