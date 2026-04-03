#!/usr/bin/env python3
"""
Create ZarishSphere-ready scaffolds from external form and distro sources.

Targets created:
- /_repos/LAYER_06_DATA/zs-content-forms-core
- /_repos/LAYER_06_DATA/zs-content-forms-bgd
- /_repos/LAYER_08_DISTROS/zs-distro-openmrs3-humanitarian
"""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path


CLONED = Path("/home/ariful/Desktop/zarishsphere/_cloned")
REPOS = Path("/home/ariful/Desktop/zarishsphere/_repos")

LIME_FORMS = CLONED / "LIME-EMR" / "distro" / "configs" / "openmrs" / "initializer_config" / "ampathforms"
LIME_TRANSLATIONS = CLONED / "LIME-EMR" / "distro" / "configs" / "openmrs" / "initializer_config" / "ampathformstranslations"
LIME_DISTRO_ROOT = CLONED / "LIME-EMR" / "distro"

BGD_FORMS = CLONED / "bangladesh-config" / "clinical_forms"
BGD_TRANSLATIONS = BGD_FORMS / "translations"

FORMS_CORE_REPO = REPOS / "LAYER_06_DATA" / "zs-content-forms-core"
FORMS_BGD_REPO = REPOS / "LAYER_06_DATA" / "zs-content-forms-bgd"
DISTRO_REPO = REPOS / "LAYER_08_DISTROS" / "zs-distro-openmrs3-humanitarian"


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


def summarize_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    summary = {"source": str(path)}
    if isinstance(data, dict):
        for key in ["uuid", "name", "version", "encounter", "encounterType", "defaultLocale", "translationsUrl"]:
            if key in data and isinstance(data[key], (str, int, float, bool)):
                summary[key] = data[key]
        if "pages" in data and isinstance(data["pages"], list):
            summary["page_count"] = len(data["pages"])
        if "controls" in data and isinstance(data["controls"], list):
            summary["control_count"] = len(data["controls"])
    return summary


def scaffold_forms_core() -> None:
    reset_dir(FORMS_CORE_REPO)
    forms_dir = FORMS_CORE_REPO / "forms"
    forms_dir.mkdir(parents=True, exist_ok=True)

    provenance = []
    translation_map: dict[str, list[Path]] = defaultdict(list)
    for translation in sorted(LIME_TRANSLATIONS.glob("*.json")):
        match = re.match(r"(.+)_translations_([a-zA-Z_]+)\.json$", translation.name)
        if match:
            translation_map[match.group(1)].append(translation)

    form_index = []
    for form in sorted(LIME_FORMS.glob("*.json")):
        stem = form.stem
        target_dir = forms_dir / normalize_name(stem)
        target_dir.mkdir(parents=True, exist_ok=True)
        copy2(form, target_dir / "source-form.json")
        provenance.append({"source": str(form), "target": str(target_dir / "source-form.json")})
        translations = []
        for translation in sorted(translation_map.get(stem, [])):
            lang_match = re.match(r".+_translations_([a-zA-Z_]+)\.json$", translation.name)
            lang = lang_match.group(1) if lang_match else translation.stem
            dst = target_dir / "translations" / f"{lang}.json"
            copy2(translation, dst)
            provenance.append({"source": str(translation), "target": str(dst)})
            translations.append(lang)
        summary = summarize_json(form)
        summary["id"] = normalize_name(stem)
        summary["translation_languages"] = translations
        form_index.append(summary)

    write(
        FORMS_CORE_REPO / "README.md",
        "\n".join(
            [
                "# zs-content-forms-core",
                "",
                "Reusable core clinical forms extracted from external humanitarian OpenMRS sources, starting with LIME-EMR.",
                "",
                "## Structure",
                "",
                "- `forms/<form-id>/source-form.json` keeps the original source form",
                "- `forms/<form-id>/translations/<lang>.json` keeps source translations grouped by language",
                "- `FORM_INDEX.json` summarizes the imported forms",
                "- `SOURCE_PROVENANCE.json` records where each asset came from",
                "",
                "## Notes",
                "",
                "- These are source-preserving imports, not yet converted to ZarishSphere native form schema.",
                "- Shared forms should be refined here before country-specific overrides are introduced.",
                "",
            ]
        )
        + "\n",
    )
    write(FORMS_CORE_REPO / ".gitignore", ".DS_Store\n")
    write(FORMS_CORE_REPO / "FORM_INDEX.json", json.dumps(form_index, indent=2) + "\n")
    write(
        FORMS_CORE_REPO / "SOURCE_PROVENANCE.json",
        json.dumps(
            {
                "source": str(LIME_FORMS.parent),
                "form_count": len(form_index),
                "copied": provenance,
            },
            indent=2,
        )
        + "\n",
    )


def scaffold_forms_bgd() -> None:
    reset_dir(FORMS_BGD_REPO)
    forms_dir = FORMS_BGD_REPO / "forms"
    forms_dir.mkdir(parents=True, exist_ok=True)
    provenance = []
    form_index = []

    for form in sorted(BGD_FORMS.glob("*.json")):
        if form.parent == BGD_TRANSLATIONS:
            continue
        summary = summarize_json(form)
        slug_base = summary.get("name") or summary.get("uuid") or form.stem
        form_id = normalize_name(str(slug_base))
        target_dir = forms_dir / form_id
        suffix = 2
        while target_dir.exists():
            target_dir = forms_dir / f"{form_id}-{suffix}"
            suffix += 1
        target_dir.mkdir(parents=True, exist_ok=True)

        dst_form = target_dir / "source-form.json"
        copy2(form, dst_form)
        provenance.append({"source": str(form), "target": str(dst_form)})

        translation_source = BGD_TRANSLATIONS / form.name
        langs = []
        if translation_source.exists():
            dst_translation = target_dir / "translations" / "en.json"
            copy2(translation_source, dst_translation)
            provenance.append({"source": str(translation_source), "target": str(dst_translation)})
            langs = ["en"]

        summary["id"] = target_dir.name
        summary["translation_languages"] = langs
        form_index.append(summary)

    write(
        FORMS_BGD_REPO / "README.md",
        "\n".join(
            [
                "# zs-content-forms-bgd",
                "",
                "Bangladesh-specific clinical forms extracted from the Bangladesh Bahmni/OpenMRS configuration.",
                "",
                "## Structure",
                "",
                "- `forms/<form-id>/source-form.json` keeps the original source form",
                "- `forms/<form-id>/translations/en.json` keeps the source translation payload when available",
                "- `FORM_INDEX.json` summarizes the imported forms",
                "- `SOURCE_PROVENANCE.json` records where each asset came from",
                "",
                "## Notes",
                "",
                "- These forms are preserved as source imports first.",
                "- The next refinement step is mapping them into ZarishSphere form schema and FHIR-backed semantics.",
                "",
            ]
        )
        + "\n",
    )
    write(FORMS_BGD_REPO / ".gitignore", ".DS_Store\n")
    write(FORMS_BGD_REPO / "FORM_INDEX.json", json.dumps(form_index, indent=2) + "\n")
    write(
        FORMS_BGD_REPO / "SOURCE_PROVENANCE.json",
        json.dumps(
            {
                "source": str(BGD_FORMS),
                "form_count": len(form_index),
                "copied": provenance,
            },
            indent=2,
        )
        + "\n",
    )


def scaffold_distro() -> None:
    reset_dir(DISTRO_REPO)
    copy_list = [
        "assembly.xml",
        "pom.xml",
        "configs/openmrs/frontend_assembly/spa-assemble-config.json",
        "configs/openmrs/frontend_config/msf-frontend-config.json",
        "configs/openmrs/frontend_config/msf-translations-frontend-config.json",
        "configs/openmrs/initializer_config/idgen/distro_msf_idgen_sequential.csv",
        "configs/openmrs/initializer_config/locations/distro_locations.csv",
        "configs/openmrs/initializer_config/visittypes/distro_visittypes.csv",
        "configs/openmrs/initializer_config/appointmentservicedefinitions/distro_service_definitions.csv",
        "configs/openmrs/initializer_config/appointmentservicetypes/distro_service_types.csv",
        "configs/openmrs/initializer_config/locationtags/distro_locationtags.csv",
        "configs/openmrs/initializer_config/encountertypes/distro_encounter_types.csv",
        "configs/openmrs/initializer_config/encountertypes/distro_ward_encountertypes.csv",
        "configs/openmrs/initializer_config/roles/distro_roles.csv",
        "configs/openmrs/initializer_config/privileges/distro_queue_privileges.csv",
        "configs/openmrs/initializer_config/privileges/distro_patient_chart_privileges.csv",
        "configs/openmrs/initializer_config/personattributetypes/distro_personattributetypes.csv",
        "configs/openmrs/initializer_config/conceptsources/msf_default_conceptsources-core.csv",
        "configs/openmrs/initializer_config/concepts/msf_default_findings.csv",
        "configs/openmrs/initializer_config/concepts/msf_default_misc-core.csv",
        "configs/openmrs/initializer_config/concepts/msf_default_questions.csv",
        "configs/openmrs/initializer_config/patientidentifiertypes/msf_default_patientidentifiertypes.csv",
        "configs/openfn/config.json",
        "configs/openfn/distro-project.yaml",
        "configs/traefik/config/traefik.yml",
        "configs/traefik/config/tls.yml",
    ]
    provenance = []
    for rel in copy_list:
        src = LIME_DISTRO_ROOT / rel
        dst = DISTRO_REPO / rel
        copy2(src, dst)
        provenance.append({"source": str(src), "target": str(dst)})

    write(
        DISTRO_REPO / "README.md",
        "\n".join(
            [
                "# zs-distro-openmrs3-humanitarian",
                "",
                "Reference humanitarian OpenMRS 3 distro scaffold for ZarishSphere, extracted from LIME-EMR structure.",
                "",
                "## What This Repo Holds",
                "",
                "- Base distro assembly and Maven packaging files",
                "- Representative initializer configuration for locations, ID generation, roles, visit types, and service definitions",
                "- Frontend assembly and frontend config templates",
                "- OpenFn and Traefik baseline configuration samples",
                "",
                "## Notes",
                "",
                "- This is a reference distro scaffold, not yet a final ZarishSphere branded runtime package.",
                "- MSF/LIME-specific assets need follow-up review before final standardization or redistribution.",
                "",
            ]
        )
        + "\n",
    )
    write(DISTRO_REPO / ".gitignore", ".DS_Store\n")
    write(
        DISTRO_REPO / "SOURCE_PROVENANCE.json",
        json.dumps(
            {
                "source": str(LIME_DISTRO_ROOT),
                "copied": provenance,
            },
            indent=2,
        )
        + "\n",
    )


def main() -> None:
    scaffold_forms_core()
    scaffold_forms_bgd()
    scaffold_distro()


if __name__ == "__main__":
    main()
