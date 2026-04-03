#!/usr/bin/env python3
"""
Build a migration-oriented inventory of external healthcare assets that sit
outside the current ZarishSphere repos.

The goal is not to copy vendor platforms wholesale. Instead, we classify the
reusable assets and map them into ZarishSphere-owned target repositories.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path


WORKSPACE = Path("/home/ariful/Desktop/zarishsphere/_cloned")
OUTPUT_DIR = WORKSPACE / "zs-core-fhir-engine" / "_resources" / "external-assets"

SOURCES = [
    {
        "id": "bd-core-fhir-ig",
        "name": "Bangladesh Core FHIR IG",
        "path": WORKSPACE / "BD-Core-FHIR-IG-main",
        "type": "national_fhir_ig",
        "priority": "highest",
        "target_repos": [
            "zs-data-fhir-profiles",
            "zs-country-bgd-fhir-ig",
            "zs-country-bgd-terminology",
        ],
        "intended_use": "National profiles, value sets, code systems, naming systems, and narrative governance for Bangladesh.",
        "migration_rule": "Extract FSH, terminology, and profile definitions. Do not keep the full IG publisher cache/template in product repos.",
    },
    {
        "id": "bangladesh-config",
        "name": "Bangladesh Bahmni/OpenMRS Config",
        "path": WORKSPACE / "bangladesh-config",
        "type": "country_openmrs_bahmni_config",
        "priority": "highest",
        "target_repos": [
            "zs-country-bgd-openmrs-config",
            "zs-content-forms-bgd",
            "zs-content-terminology-bgd",
            "zs-analytics-sql-bgd",
        ],
        "intended_use": "Bangladesh-specific clinical forms, translations, concepts, SQL marts, and operational config.",
        "migration_rule": "Split forms, translations, concepts, analytics SQL, and deployment config into separate content packages. Avoid keeping database dumps in the main content repos.",
    },
    {
        "id": "lime-emr",
        "name": "LIME-EMR",
        "path": WORKSPACE / "LIME-EMR",
        "type": "openmrs3_humanitarian_distro",
        "priority": "highest",
        "target_repos": [
            "zs-distro-openmrs3-humanitarian",
            "zs-content-forms-core",
            "zs-content-terminology-core",
            "zs-country-site-templates",
        ],
        "intended_use": "Modern distro pattern, reusable humanitarian forms, translations, and site-level initializer structure.",
        "migration_rule": "Use as the structural reference for packaging and inheritance. Extract reusable form content and site pattern, not MSF branding or unrelated deployment baggage.",
    },
    {
        "id": "kenyahmis",
        "name": "KenyaHMIS",
        "path": WORKSPACE / "kenyahmis",
        "type": "country_openmrs3_distro",
        "priority": "high",
        "target_repos": [
            "zs-country-ken-openmrs-config",
            "zs-content-forms-ken",
            "zs-content-program-hiv",
        ],
        "intended_use": "Country-specific HIV, TB, maternal, and service-delivery forms plus Ozone/OpenMRS initializer config.",
        "migration_rule": "Extract clinical forms and country config patterns. Treat SQL concept dumps as import sources, not canonical truth.",
    },
    {
        "id": "bht-emr-api",
        "name": "BHT-EMR-API",
        "path": WORKSPACE / "BHT-EMR-API",
        "type": "legacy_emr_backend",
        "priority": "medium",
        "target_repos": [
            "zs-migration-bht",
            "zs-content-program-hiv",
            "zs-content-reporting-maps",
        ],
        "intended_use": "Legacy program mappings, default concept/program metadata, reporting SQL, and interoperability mappings.",
        "migration_rule": "Mine domain knowledge and mappings only. Do not adopt the full legacy backend stack into ZarishSphere.",
    },
    {
        "id": "old-zarishsphere",
        "name": "Old ZarishSphere",
        "path": WORKSPACE / "_old_zarishsphere",
        "type": "legacy_strategy_docs",
        "priority": "medium",
        "target_repos": [
            "zs-docs-platform",
            "zs-docs-standards",
        ],
        "intended_use": "Legacy platform narrative, value proposition, and positioning language.",
        "migration_rule": "Reuse only validated product language and diagrams after aligning to the current repo reality.",
    },
]

COUNT_RULES = {
    "fsh": lambda rel, low: low.endswith(".fsh"),
    "json_forms": lambda rel, low: low.endswith(".json")
    and ("clinical_forms" in rel or "ampathforms" in rel or "forms/" in rel),
    "json_translations": lambda rel, low: low.endswith(".json")
    and ("translation" in rel or "translations/" in rel),
    "csv_concepts": lambda rel, low: low.endswith(".csv")
    and ("concept" in rel or "concepts/" in rel),
    "sql": lambda rel, low: low.endswith(".sql"),
    "yaml": lambda rel, low: low.endswith(".yaml") or low.endswith(".yml"),
    "xml": lambda rel, low: low.endswith(".xml"),
}

SAMPLE_PATTERNS = [
    ("fsh_samples", lambda rel, low: low.endswith(".fsh")),
    (
        "form_samples",
        lambda rel, low: low.endswith(".json")
        and ("clinical_forms" in rel or "ampathforms" in rel or "forms/" in rel),
    ),
    (
        "concept_samples",
        lambda rel, low: low.endswith(".csv")
        and ("concept" in rel or "concepts/" in rel),
    ),
    ("sql_samples", lambda rel, low: low.endswith(".sql")),
]


def detect_license(root: Path) -> str:
    for name in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]:
        candidate = root / name
        if candidate.exists():
            return candidate.name
    return "not_found"


def inventory_source(source: dict) -> dict:
    root = source["path"]
    counts = Counter()
    samples = {name: [] for name, _ in SAMPLE_PATTERNS}

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(root).as_posix().lower()
        low = file_path.name.lower()
        for key, matcher in COUNT_RULES.items():
            if matcher(rel, low):
                counts[key] += 1
        for key, matcher in SAMPLE_PATTERNS:
            if len(samples[key]) < 12 and matcher(rel, low):
                samples[key].append(file_path.relative_to(root).as_posix())

    return {
        "id": source["id"],
        "name": source["name"],
        "path": str(root),
        "source_type": source["type"],
        "priority": source["priority"],
        "license": detect_license(root),
        "counts": dict(counts),
        "target_repos": source["target_repos"],
        "intended_use": source["intended_use"],
        "migration_rule": source["migration_rule"],
        "samples": samples,
    }


def build_report(data: list[dict]) -> str:
    lines = [
        "# External Asset Migration Audit",
        "",
        "This report inventories external repositories under `_cloned` and maps them into ZarishSphere-owned standards, content, and country packages.",
        "",
        "## Core Decisions",
        "",
        "- Treat `BD-Core-FHIR-IG-main` as the Bangladesh standards source, not as the runtime platform.",
        "- Treat `bangladesh-config`, `LIME-EMR`, and `kenyahmis` as content mines for forms, concepts, translations, and distro patterns.",
        "- Treat `BHT-EMR-API` as a legacy knowledge source for mappings, metadata, and reporting logic rather than code to adopt directly.",
        "- Treat `_old_zarishsphere` as product-language input only after validating against the current repo reality.",
        "",
        "## Recommended Target Repository Families",
        "",
        "- `zs-data-fhir-profiles`: shared ZarishSphere FHIR profiles and extensions.",
        "- `zs-country-bgd-fhir-ig`: Bangladesh-specific derivative IG package and publishing assets.",
        "- `zs-country-bgd-terminology`: Bangladesh-specific code systems, value sets, and naming systems.",
        "- `zs-content-forms-core`: reusable cross-program OpenMRS/Bahmni form library.",
        "- `zs-content-forms-bgd`: Bangladesh-specific clinical forms and translations.",
        "- `zs-content-forms-ken`: Kenya-specific clinical forms and translations.",
        "- `zs-content-terminology-core`: reusable concepts, answer sets, and metadata term mappings.",
        "- `zs-content-terminology-bgd`: Bangladesh-specific concept and metadata packs.",
        "- `zs-country-bgd-openmrs-config`: country runtime config package for Bangladesh OpenMRS/Bahmni deployments.",
        "- `zs-country-ken-openmrs-config`: country runtime config package for Kenya-style OpenMRS deployments.",
        "- `zs-distro-openmrs3-humanitarian`: modern reference distro structure modeled from LIME-EMR.",
        "- `zs-country-site-templates`: site-level initializer packages, logos, frontend configs, and location packs.",
        "- `zs-analytics-sql-bgd`: curated analytics SQL and warehouse views from Bangladesh sources.",
        "- `zs-content-reporting-maps`: interoperability/reporting maps such as IDSR and LIMS connectors.",
        "- `zs-migration-bht`: one-off migration logic and legacy extraction utilities from BHT sources.",
        "",
        "## Source Summary",
        "",
    ]

    for item in data:
        counts = item["counts"]
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- Source type: `{item['source_type']}`",
                f"- Priority: `{item['priority']}`",
                f"- License marker: `{item['license']}`",
                f"- Counts: FSH `{counts.get('fsh', 0)}`, forms `{counts.get('json_forms', 0)}`, translations `{counts.get('json_translations', 0)}`, concept CSVs `{counts.get('csv_concepts', 0)}`, SQL `{counts.get('sql', 0)}`",
                f"- Intended use: {item['intended_use']}",
                f"- Migration rule: {item['migration_rule']}",
                f"- Target repos: {', '.join('`' + repo + '`' for repo in item['target_repos'])}",
                "",
            ]
        )

    lines.extend(
        [
            "## Immediate Migration Order",
            "",
            "1. Bangladesh FHIR IG into `zs-data-fhir-profiles`, `zs-country-bgd-fhir-ig`, and `zs-country-bgd-terminology`.",
            "2. LIME-EMR distro structure into `zs-distro-openmrs3-humanitarian` and `zs-country-site-templates`.",
            "3. Bangladesh Bahmni/OpenMRS forms, concepts, and analytics into country content repos.",
            "4. KenyaHMIS forms into a Kenya package and program-specific content packs.",
            "5. BHT-EMR-API mappings and metadata into migration/reporting repos after legal and relevance review.",
            "",
            "## Important Risks",
            "",
            "- Some sources include database dumps and installer payloads that should not become canonical truth in content repos.",
            "- Not every source has an obvious license marker; legal review is needed before broad redistribution of extracted assets.",
            "- OpenMRS/Bahmni forms are not automatically FHIR-native. They need concept and field mapping into ZarishSphere resources before runtime use.",
            "- Country packages should inherit from shared core content rather than duplicate forms and terminology.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inventory = [inventory_source(source) for source in SOURCES]

    payload = {
        "generated_by": "tools/external_inventory.py",
        "workspace_root": str(WORKSPACE),
        "summary": {
            "source_count": len(inventory),
            "highest_priority_sources": [
                item["id"] for item in inventory if item["priority"] == "highest"
            ],
        },
        "sources": inventory,
    }

    (OUTPUT_DIR / "migration-manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "MIGRATION_AUDIT.md").write_text(
        build_report(inventory),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
