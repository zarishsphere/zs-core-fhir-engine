#!/usr/bin/env python3
"""
Create Bangladesh terminology scaffolding and form normalization manifests.

Outputs:
- /_repos/LAYER_06_DATA/zs-content-terminology-bgd
- normalization manifests for zs-content-forms-core and zs-content-forms-bgd
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path


CLONED = Path("/home/ariful/Desktop/zarishsphere/_cloned")
REPOS = Path("/home/ariful/Desktop/zarishsphere/_repos")

BGD_CONFIG = CLONED / "bangladesh-config"
BGD_TEMPLATES = BGD_CONFIG / "openmrs" / "templates"
BGD_CONFIGURATION = BGD_CONFIG / "configuration"
BGD_JSON = BGD_CONFIG / "bd.json"

TERMINOLOGY_REPO = REPOS / "LAYER_06_DATA" / "zs-content-terminology-bgd"
FORMS_CORE_REPO = REPOS / "LAYER_06_DATA" / "zs-content-forms-core"
FORMS_BGD_REPO = REPOS / "LAYER_06_DATA" / "zs-content-forms-bgd"


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy2(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def normalize_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unnamed"


def classify_template(filename: str) -> tuple[str, str]:
    name = filename.rsplit(".", 1)[0]
    if name.endswith("_concept_sets"):
        return name[: -len("_concept_sets")], "concept_sets"
    if name.endswith("_concepts"):
        return name[: -len("_concepts")], "concepts"
    if name.endswith("_generic_concepts"):
        return name[: -len("_generic_concepts")], "generic_concepts"
    return name, "misc"


def extract_bgd_terminology() -> None:
    reset_dir(TERMINOLOGY_REPO)
    copied = []
    families: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for csv_file in sorted(BGD_TEMPLATES.glob("*.csv")):
        family, kind = classify_template(csv_file.name)
        target = TERMINOLOGY_REPO / "source" / "openmrs-templates" / family / csv_file.name
        copy2(csv_file, target)
        copied.append({"source": str(csv_file), "target": str(target)})
        families[family][kind].append(csv_file.name)

    metadata_dirs = [
        "appointmentsservicesdefinitions",
        "locations",
        "personattributetypes",
    ]
    for rel in metadata_dirs:
        src_dir = BGD_CONFIGURATION / rel
        if src_dir.exists():
            for file_path in sorted(src_dir.glob("*")):
                if file_path.is_file():
                    target = TERMINOLOGY_REPO / "source" / "metadata-packs" / rel / file_path.name
                    copy2(file_path, target)
                    copied.append({"source": str(file_path), "target": str(target)})

    if BGD_JSON.exists():
        target = TERMINOLOGY_REPO / "source" / "metadata-packs" / "bd.json"
        copy2(BGD_JSON, target)
        copied.append({"source": str(BGD_JSON), "target": str(target)})

    family_index = []
    for family, grouped in sorted(families.items()):
        row_counts = {}
        for kind_files in grouped.values():
            for name in kind_files:
                with (BGD_TEMPLATES / name).open(encoding="utf-8", errors="ignore") as fh:
                    row_counts[name] = sum(1 for _ in csv.DictReader(fh))
        family_index.append(
            {
                "family": family,
                "files": grouped,
                "row_counts": row_counts,
            }
        )

    write(
        TERMINOLOGY_REPO / "README.md",
        "\n".join(
            [
                "# zs-content-terminology-bgd",
                "",
                "Bangladesh-specific terminology and metadata packs extracted from the Bangladesh Bahmni/OpenMRS configuration.",
                "",
                "## What This Repo Holds",
                "",
                "- OpenMRS concept template CSV files grouped by clinical family",
                "- Supporting metadata packs such as locations, service definitions, and person attribute types",
                "- Family-level index metadata for later conversion into ZarishSphere terminology packages",
                "",
                "## Notes",
                "",
                "- This is a source-preserving terminology scaffold.",
                "- The next refinement step is converting these templates into ZarishSphere-native terminology, value-set, and concept-pack formats.",
                "",
            ]
        )
        + "\n",
    )
    write(TERMINOLOGY_REPO / ".gitignore", ".DS_Store\n")
    write(TERMINOLOGY_REPO / "FAMILY_INDEX.json", json.dumps(family_index, indent=2) + "\n")
    write(
        TERMINOLOGY_REPO / "SOURCE_PROVENANCE.json",
        json.dumps(
            {
                "source_root": str(BGD_CONFIG),
                "copied": copied,
            },
            indent=2,
        )
        + "\n",
    )


DOMAIN_HINTS = [
    ("mental-health", ["mhpss", "mhgap", "mental", "phq-9", "anxiety", "depression"]),
    ("maternity", ["anc", "pnc", "maternity", "antenatal", "delivery", "obstetric", "neonatal", "gynaecology"]),
    ("nutrition", ["nutrition", "feeding", "itfc", "atfc", "muac", "wound", "undernutrition"]),
    ("cd", ["tb", "hiv", "hcv", "hbv", "cholera", "snakebite", "dengue", "filariasis", "schistosomiasis", "covid", "prep", "tpt", "sti"]),
    ("emergency", ["triage", "er", "icu", "discharge", "admission", "operative", "anesthesia", "surgery", "transfusion", "radiology"]),
    ("ncd", ["ncd", "diabetes", "hypertension", "cancer", "cervical", "palliative"]),
    ("family-planning", ["family planning"]),
    ("social-work", ["social work", "referral"]),
    ("core", ["patient", "vitals", "diagnosis", "clinical encounter", "clinic visit", "patient data"]),
]


def guess_domain(name: str) -> str:
    lower = name.lower()
    for domain, hints in DOMAIN_HINTS:
        if any(hint in lower for hint in hints):
            return domain
    return "unclassified"


def build_actions(form_data: dict, source_kind: str) -> list[str]:
    actions = []
    if source_kind == "lime_openmrs":
        actions.extend(
            [
                "convert pages.sections.questions into zs-form sections.fields",
                "replace inline labels with i18n keys",
                "map encounter/question semantics to FHIR R5 resources and fhirPath fields",
                "normalize coded answers to terminology-backed options",
            ]
        )
    elif source_kind == "bahmni_openmrs":
        actions.extend(
            [
                "convert controls list into zs-form fields",
                "extract inline labels and create i18n keys",
                "map concept references to FHIR-backed field semantics",
                "normalize control type and validation metadata",
            ]
        )
    elif source_kind == "bahmni_wrapper":
        actions.extend(
            [
                "unwrap embedded formJson payload",
                "split bundled translations into language files",
                "convert resulting controls into zs-form fields",
            ]
        )
    return actions


def build_manifest(repo: Path, source_label: str) -> None:
    forms_root = repo / "forms"
    items = []
    domain_counts = Counter()

    for form_dir in sorted([p for p in forms_root.iterdir() if p.is_dir()]):
        source_form = form_dir / "source-form.json"
        if not source_form.exists():
            continue
        with source_form.open(encoding="utf-8") as fh:
            data = json.load(fh)

        if source_label == "core":
            source_kind = "lime_openmrs"
            name = data.get("name", form_dir.name)
            translation_languages = sorted(
                [p.stem for p in (form_dir / "translations").glob("*.json")]
            )
            source_structure = {
                "top_level": sorted(data.keys()),
                "has_pages": isinstance(data.get("pages"), list),
                "page_count": len(data.get("pages", [])) if isinstance(data.get("pages"), list) else 0,
            }
        else:
            if "formJson" in data and "translations" in data:
                source_kind = "bahmni_wrapper"
                unwrapped = data.get("formJson", {})
                name = unwrapped.get("name", form_dir.name)
                translation_languages = ["embedded"]
                source_structure = {
                    "top_level": sorted(data.keys()),
                    "wrapped_top_level": sorted(unwrapped.keys()) if isinstance(unwrapped, dict) else [],
                }
            else:
                source_kind = "bahmni_openmrs"
                name = data.get("name", form_dir.name)
                translation_languages = sorted(
                    [p.stem for p in (form_dir / "translations").glob("*.json")]
                )
                source_structure = {
                    "top_level": sorted(data.keys()),
                    "control_count": len(data.get("controls", [])) if isinstance(data.get("controls"), list) else 0,
                }

        domain = guess_domain(name)
        domain_counts[domain] += 1
        items.append(
            {
                "id": form_dir.name,
                "name": name,
                "source_kind": source_kind,
                "recommended_domain": domain,
                "translation_languages": translation_languages,
                "source_structure": source_structure,
                "normalization_actions": build_actions(data, source_kind),
            }
        )

    write(repo / "NORMALIZATION_QUEUE.json", json.dumps(items, indent=2) + "\n")
    write(
        repo / "NORMALIZATION_SUMMARY.json",
        json.dumps(
            {
                "repo": str(repo),
                "form_count": len(items),
                "domain_counts": dict(domain_counts),
                "source_kinds": dict(Counter(item["source_kind"] for item in items)),
            },
            indent=2,
        )
        + "\n",
    )


def main() -> None:
    extract_bgd_terminology()
    build_manifest(FORMS_CORE_REPO, "core")
    build_manifest(FORMS_BGD_REPO, "bgd")


if __name__ == "__main__":
    main()
