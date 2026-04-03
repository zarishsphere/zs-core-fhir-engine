#!/usr/bin/env python3
"""
Extract reusable option sets from normalized forms into a shared terminology repo.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path


CORE_FORMS_NORMALIZED = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA/zs-content-forms-core/normalized")
BGD_FORMS_NORMALIZED = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA/zs-content-forms-bgd/normalized")
TERMINOLOGY_CORE = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA/zs-content-terminology-core")


def reset_repo(path: Path) -> None:
    if path.exists():
        import shutil

        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def collect_from_repo(root: Path, source_name: str) -> tuple[dict, list[dict]]:
    option_sets = defaultdict(lambda: {"options": None, "usages": []})
    inventories = []
    for form_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        form_path = form_dir / "form.json"
        if not form_path.exists():
            continue
        form = json.loads(form_path.read_text(encoding="utf-8"))
        inventories.append({"source": source_name, "slug": form_dir.name, "formId": form.get("id")})
        for section in form.get("sections", []):
            for field in section.get("fields", []):
                options = field.get("options")
                if not options:
                    continue
                sig = canonical_signature(options)
                entry = option_sets[sig]
                if entry["options"] is None:
                    entry["options"] = options
                entry["usages"].append(
                    {
                        "source": source_name,
                        "formSlug": form_dir.name,
                        "formId": form.get("id"),
                        "sectionId": section.get("id"),
                        "fieldId": field.get("id"),
                        "fieldLabel": field.get("label"),
                    }
                )
    return option_sets, inventories


def infer_name(usages: list[dict]) -> str:
    labels = [u.get("fieldLabel", "") for u in usages]
    joined = " ".join(labels).lower()
    if "phq9" in joined:
        return "phq9-frequency"
    if "triage" in joined or "avpu" in joined:
        return "triage-status"
    if "consultation type" in joined:
        return "consultation-type"
    if "yes" in joined and "no" in joined:
        return "yes-no"
    first = usages[0]
    return f"{first['source']}-{first['formSlug']}-{first['fieldId']}"


def build_repo() -> None:
    reset_repo(TERMINOLOGY_CORE)
    core_sets, inventories = collect_from_repo(CORE_FORMS_NORMALIZED, "core")
    bgd_sets, bgd_inventory = collect_from_repo(BGD_FORMS_NORMALIZED, "bgd")
    inventories.extend(bgd_inventory)

    combined = defaultdict(lambda: {"options": None, "usages": []})
    for bucket in [core_sets, bgd_sets]:
        for sig, payload in bucket.items():
            combined[sig]["options"] = payload["options"]
            combined[sig]["usages"].extend(payload["usages"])

    index = []
    report_lines = [
        "# Shared Option Set Harmonization Report",
        "",
        "This repo contains extracted reusable option sets mined from normalized ZarishSphere forms.",
        "",
    ]

    for sig, payload in sorted(combined.items(), key=lambda item: (-len(item[1]["usages"]), item[0])):
        name = infer_name(payload["usages"])
        slug = f"{name}-{sig}"
        option_set = {
            "id": slug,
            "name": name,
            "optionCount": len(payload["options"]),
            "options": payload["options"],
            "usages": payload["usages"],
        }
        write_json(TERMINOLOGY_CORE / "option-sets" / f"{slug}.json", option_set)
        index.append(
            {
                "id": slug,
                "name": name,
                "optionCount": len(payload["options"]),
                "usageCount": len(payload["usages"]),
            }
        )
        report_lines.extend(
            [
                f"## {slug}",
                "",
                f"- Name: `{name}`",
                f"- Option count: `{len(payload['options'])}`",
                f"- Usage count: `{len(payload['usages'])}`",
                "",
            ]
        )

    (TERMINOLOGY_CORE / "README.md").write_text(
        "\n".join(
            [
                "# zs-content-terminology-core",
                "",
                "Shared terminology scaffolds extracted from normalized ZarishSphere forms.",
                "",
                "## What This Repo Holds",
                "",
                "- reusable option sets deduplicated from normalized forms",
                "- usage inventory showing which forms and fields use each option set",
                "- first-step harmonization artifacts for future standard terminology replacement",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (TERMINOLOGY_CORE / ".gitignore").write_text(".DS_Store\n", encoding="utf-8")
    write_json(TERMINOLOGY_CORE / "OPTION_SET_INDEX.json", index)
    write_json(TERMINOLOGY_CORE / "FORM_INVENTORY.json", inventories)
    (TERMINOLOGY_CORE / "HARMONIZATION_REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build_repo()
