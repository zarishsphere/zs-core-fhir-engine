#!/usr/bin/env python3
"""
Replace repeated inline form options with shared optionSetRef references.
"""

from __future__ import annotations

import json
from pathlib import Path


CORE_NORMALIZED = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA/zs-content-forms-core/normalized")
BGD_NORMALIZED = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA/zs-content-forms-bgd/normalized")
TERMINOLOGY_CORE = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA/zs-content-terminology-core")


def canonical_signature(options: list[dict]) -> str:
    payload = json.dumps(
        sorted(
            [
                {
                    "value": opt.get("value"),
                    "display": opt.get("display"),
                    "system": opt.get("system"),
                }
                for opt in options
            ],
            key=lambda item: (str(item.get("system")), str(item.get("value")), str(item.get("display"))),
        ),
        sort_keys=True,
    )
    import hashlib

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def load_option_sets() -> dict[str, dict]:
    index = json.loads((TERMINOLOGY_CORE / "OPTION_SET_INDEX.json").read_text(encoding="utf-8"))
    by_sig = {}
    for item in index:
        option_set = json.loads(
            (TERMINOLOGY_CORE / "option-sets" / f"{item['id']}.json").read_text(encoding="utf-8")
        )
        sig = canonical_signature(option_set["options"])
        by_sig[sig] = option_set
    return by_sig


def refactor_repo(root: Path, repo_name: str, option_sets: dict[str, dict]) -> list[dict]:
    changes = []
    for form_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        form_path = form_dir / "form.json"
        if not form_path.exists():
            continue
        form = json.loads(form_path.read_text(encoding="utf-8"))
        modified = False
        replacements = []
        for section in form.get("sections", []):
            for field in section.get("fields", []):
                options = field.get("options")
                if not options:
                    continue
                sig = canonical_signature(options)
                option_set = option_sets.get(sig)
                if not option_set:
                    continue
                field.pop("options", None)
                field["optionSetRef"] = option_set["id"]
                field["optionSetSource"] = "zs-content-terminology-core"
                field["optionCount"] = option_set["optionCount"]
                field["harmonizationStatus"] = "shared-option-set-ref"
                modified = True
                replacements.append(
                    {
                        "fieldId": field.get("id"),
                        "optionSetRef": option_set["id"],
                        "optionCount": option_set["optionCount"],
                    }
                )
        if modified:
            form_path.write_text(json.dumps(form, indent=2) + "\n", encoding="utf-8")
            changes.append(
                {
                    "repo": repo_name,
                    "formSlug": form_dir.name,
                    "formId": form.get("id"),
                    "replacements": replacements,
                }
            )
    return changes


def main() -> None:
    option_sets = load_option_sets()
    changes = []
    changes.extend(refactor_repo(CORE_NORMALIZED, "zs-content-forms-core", option_sets))
    changes.extend(refactor_repo(BGD_NORMALIZED, "zs-content-forms-bgd", option_sets))
    (TERMINOLOGY_CORE / "OPTION_SET_REFACTOR_REPORT.json").write_text(
        json.dumps(changes, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
