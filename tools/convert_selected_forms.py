#!/usr/bin/env python3
"""
Convert a small, high-value set of imported Bangladesh forms into the first
ZarishSphere-native normalized form artifacts.

Scope:
- unwrap Bangladesh wrapper-style forms
- convert Patient Data, Patient Vitals, and Patient Diagnosis
- emit normalized forms, i18n files, and field mapping scaffolds
"""

from __future__ import annotations

import json
from pathlib import Path


BGD_REPO = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA/zs-content-forms-bgd")
BGD_FORMS_DIR = BGD_REPO / "forms"
BGD_NORMALIZED_DIR = BGD_REPO / "normalized"
CORE_REPO = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA/zs-content-forms-core")
CORE_FORMS_DIR = CORE_REPO / "forms"
CORE_NORMALIZED_DIR = CORE_REPO / "normalized"


def read_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def option_label(answer: dict) -> str:
    name = answer.get("name") or {}
    if isinstance(name, dict):
        return name.get("display") or name.get("name") or answer.get("uuid", "Unknown")
    return answer.get("uuid", "Unknown")


def unwrap_wrapper_forms() -> list[dict]:
    unwrapped = []
    for form_dir in sorted([p for p in BGD_FORMS_DIR.iterdir() if p.is_dir()]):
        source_path = form_dir / "source-form.json"
        if not source_path.exists():
            continue
        data = read_json(source_path)
        if not (isinstance(data, dict) and "formJson" in data and "translations" in data):
            continue

        form_json = data["formJson"]
        resource_payload = None
        if isinstance(form_json, dict):
            for resource in form_json.get("resources", []):
                dtype = resource.get("dataType", "")
                if "FileSystemStorageDatatype" in dtype:
                    resource_payload = resource.get("value")
                    break
        if not resource_payload:
            continue

        derived_dir = form_dir / "derived"
        derived_dir.mkdir(parents=True, exist_ok=True)
        unwrapped_form = json.loads(resource_payload)
        write_json(derived_dir / "unwrapped-form.json", unwrapped_form)
        write_json(derived_dir / "unwrapped-translations.json", data.get("translations", []))
        unwrapped.append(
            {
                "form_id": form_dir.name,
                "name": unwrapped_form.get("name"),
                "outputs": [
                    str(derived_dir / "unwrapped-form.json"),
                    str(derived_dir / "unwrapped-translations.json"),
                ],
            }
        )
    return unwrapped


FHIR_CODE_HINTS = {
    "5089AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": {
        "system": "http://loinc.org",
        "code": "29463-7",
        "display": "Body weight",
        "resource": "Observation",
        "path": "Observation.valueQuantity.value",
        "unit": "kg",
        "ucumUnit": "kg",
    },
    "5090AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": {
        "system": "http://loinc.org",
        "code": "8302-2",
        "display": "Body height",
        "resource": "Observation",
        "path": "Observation.valueQuantity.value",
        "unit": "cm",
        "ucumUnit": "cm",
    },
    "1342AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": {
        "system": "http://loinc.org",
        "code": "39156-5",
        "display": "Body mass index (BMI) [Ratio]",
        "resource": "Observation",
        "path": "Observation.valueQuantity.value",
        "unit": "kg/m2",
        "ucumUnit": "kg/m2",
    },
    "5085AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": {
        "system": "http://loinc.org",
        "code": "8480-6",
        "display": "Systolic blood pressure",
        "resource": "Observation",
        "path": "Observation.valueQuantity.value",
        "unit": "mmHg",
        "ucumUnit": "mm[Hg]",
    },
    "5086AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": {
        "system": "http://loinc.org",
        "code": "8462-4",
        "display": "Diastolic blood pressure",
        "resource": "Observation",
        "path": "Observation.valueQuantity.value",
        "unit": "mmHg",
        "ucumUnit": "mm[Hg]",
    },
}


def build_validation(control: dict) -> dict:
    validation = {}
    if control.get("lowAbsolute") is not None:
        validation["min"] = control["lowAbsolute"]
    if control.get("hiAbsolute") is not None:
        validation["max"] = control["hiAbsolute"]
    concept_props = control.get("concept", {}).get("properties", {})
    if concept_props.get("allowDecimal") is False:
        validation["decimalPlaces"] = 0
    elif concept_props.get("allowDecimal") is True:
        validation["decimalPlaces"] = 1
    return validation


def field_type(control: dict) -> str:
    concept = control.get("concept", {})
    datatype = (concept.get("datatype") or "").lower()
    props = control.get("properties", {})
    if datatype == "numeric":
        return "number"
    if datatype == "date":
        return "date"
    if datatype == "text":
        return "text"
    if datatype == "coded":
        if props.get("multiSelect"):
            return "multiselect"
        return "select"
    return "text"


def build_field(control: dict, form_domain: str, index: int) -> tuple[dict, dict]:
    concept = control.get("concept", {})
    concept_uuid = concept.get("uuid")
    mapping = FHIR_CODE_HINTS.get(concept_uuid, {})
    ftype = field_type(control)
    fid = f"field-{index:03d}"
    translation_key = control.get("label", {}).get("translationKey") or fid.upper()
    field = {
        "id": fid,
        "type": ftype,
        "label": f"{{{{i18n:forms.{form_domain}.{fid}_label}}}}",
        "hint": f"{{{{i18n:forms.{form_domain}.{fid}_hint}}}}",
        "placeholder": f"{{{{i18n:forms.{form_domain}.{fid}_placeholder}}}}",
        "fhirPath": mapping.get("path", "Observation.valueString"),
        "fhirResource": mapping.get("resource", "Observation"),
        "required": bool(control.get("properties", {}).get("mandatory")),
        "readOnly": False,
        "hidden": False,
        "validation": build_validation(control),
        "displayCondition": None,
        "sourceConceptUuid": concept_uuid,
        "sourceConceptName": concept.get("name"),
        "sourceTranslationKey": translation_key,
        "normalizationStatus": "draft-converted",
    }
    if ftype == "date":
        field["fhirPath"] = "Observation.valueDateTime"
    elif ftype == "select":
        field["fhirPath"] = "Observation.valueCodeableConcept"
    elif ftype == "multiselect":
        field["fhirPath"] = "Observation.valueCodeableConcept"
    if "code" in mapping:
        field["loincCode"] = mapping["code"]
        field["loincDisplay"] = mapping["display"]
    if "unit" in mapping:
        field["unit"] = mapping["unit"]
    if "ucumUnit" in mapping:
        field["ucumUnit"] = mapping["ucumUnit"]

    if ftype in {"select", "multiselect"}:
        field["options"] = [
            {
                "value": ans.get("uuid"),
                "display": option_label(ans),
                "system": "urn:openmrs:concept",
            }
            for ans in concept.get("answers", [])
        ]

    hint_value = ""
    description = concept.get("description")
    if isinstance(description, dict):
        hint_value = description.get("value", "")

    i18n = {
        f"forms.{form_domain}.{fid}_label": control.get("label", {}).get("value") or concept.get("name") or fid,
        f"forms.{form_domain}.{fid}_hint": hint_value,
        f"forms.{form_domain}.{fid}_placeholder": "",
    }
    return field, i18n


def convert_bahmni_form(source_path: Path, domain: str, title: str, description: str, fhir_resource: str, tags: list[str], programs: list[str]) -> tuple[dict, dict, list[dict]]:
    source = read_json(source_path)
    if "formJson" in source and "translations" in source:
        raise ValueError(f"{source_path} is wrapped and should use unwrapped data first")
    fields = []
    i18n = {
        f"forms.{domain}.title": title,
        f"forms.{domain}.description": description,
    }
    mapping_rows = []
    for idx, control in enumerate(source.get("controls", []), start=1):
        field, field_i18n = build_field(control, domain, idx)
        fields.append(field)
        i18n.update(field_i18n)
        mapping_rows.append(
            {
                "fieldId": field["id"],
                "sourceConceptUuid": field["sourceConceptUuid"],
                "sourceConceptName": field["sourceConceptName"],
                "fhirResource": field["fhirResource"],
                "fhirPath": field["fhirPath"],
                "normalizationStatus": field["normalizationStatus"],
                "standardCodeResolved": "loincCode" in field,
            }
        )
    form = {
        "$schema": "https://zarishsphere.com/schema/form/v1",
        "id": f"zs-form-{domain}",
        "title": f"{{{{i18n:forms.{domain}.title}}}}",
        "description": f"{{{{i18n:forms.{domain}.description}}}}",
        "version": "0.1.0-draft",
        "fhirResource": fhir_resource,
        "status": "draft",
        "tags": tags,
        "programs": programs,
        "sections": [
            {
                "id": "section-1",
                "title": f"{{{{i18n:forms.{domain}.title}}}}",
                "description": f"{{{{i18n:forms.{domain}.description}}}}",
                "repeating": False,
                "fields": fields,
            }
        ],
        "logic": [],
        "calculatedFields": [],
    }
    return form, i18n, mapping_rows


def convert_patient_data() -> tuple[dict, dict, list[dict]]:
    return convert_bahmni_form(
        BGD_FORMS_DIR / "patient-data" / "source-form.json",
        "bgd_core_patient_data",
        "Bangladesh Core Patient Data",
        "Draft conversion of Bangladesh source form 'Patient Data' into ZarishSphere schema.",
        "Observation",
        ["core", "bgd", "chronic-care"],
        ["bgd-general"],
    )


def convert_patient_vitals() -> tuple[dict, dict, list[dict]]:
    return convert_bahmni_form(
        BGD_FORMS_DIR / "patient-vitals" / "source-form.json",
        "bgd_vitals_patient_vitals",
        "Bangladesh Patient Vitals",
        "Draft conversion of Bangladesh source form 'Patient Vitals' into ZarishSphere schema.",
        "Observation",
        ["core", "vitals", "bgd"],
        ["bgd-general"],
    )


def convert_patient_diagnosis() -> tuple[dict, dict, list[dict]]:
    return convert_bahmni_form(
        BGD_FORMS_DIR / "patient-diagnosis" / "source-form.json",
        "bgd_diagnosis_patient_diagnosis",
        "Bangladesh Patient Diagnosis",
        "Draft conversion of Bangladesh source form 'Patient Diagnosis' into ZarishSphere schema.",
        "Condition",
        ["core", "diagnosis", "bgd"],
        ["bgd-general"],
    )


def convert_entrance_and_exit() -> tuple[dict, dict, list[dict]]:
    return convert_bahmni_form(
        BGD_FORMS_DIR / "entrance-and-exit-1" / "derived" / "unwrapped-form.json",
        "bgd_cohort_entrance_exit",
        "Bangladesh Cohort Entrance and Exit",
        "Draft conversion of Bangladesh source form 'Entrance and Exit' into ZarishSphere schema.",
        "Observation",
        ["bgd", "cohort", "program-management"],
        ["bgd-general"],
    )


def convert_hepatitis_c() -> tuple[dict, dict, list[dict]]:
    return convert_bahmni_form(
        BGD_FORMS_DIR / "hepatitis-c-v1" / "derived" / "unwrapped-form.json",
        "bgd_cd_hepatitis_c",
        "Bangladesh Hepatitis C Follow-up",
        "Draft conversion of Bangladesh source form 'Hepatitis C' into ZarishSphere schema.",
        "Observation",
        ["bgd", "cd", "hepatitis-c"],
        ["bgd-hepatitis"],
    )


def lime_field_type(question: dict) -> str:
    rendering = question.get("questionOptions", {}).get("rendering", "")
    if rendering == "number":
        return "number"
    if rendering == "datetime":
        return "datetime"
    if rendering == "radio":
        return "select"
    if rendering in {"text", "textarea"}:
        return "text"
    return "text"


def convert_lime_form(
    form_slug: str,
    domain: str,
    title: str,
    description: str,
    fhir_resource: str,
    tags: list[str],
    programs: list[str],
) -> tuple[dict, dict, list[dict]]:
    source = read_json(CORE_FORMS_DIR / form_slug / "source-form.json")
    translation_dir = CORE_FORMS_DIR / form_slug / "translations"
    translation_files = {}
    if translation_dir.exists():
        for p in sorted(translation_dir.glob("*.json")):
            translation_files[p.stem] = read_json(p)

    i18n_by_lang: dict[str, dict] = {"en": {}}
    i18n_by_lang["en"][f"forms.{domain}.title"] = title
    i18n_by_lang["en"][f"forms.{domain}.description"] = description
    sections = []
    mappings = []
    field_idx = 1

    def translate(lang: str, text: str) -> str:
        payload = translation_files.get(lang)
        if not payload:
            return text
        return payload.get("translations", {}).get(text, text)

    for page_idx, page in enumerate(source.get("pages", []), start=1):
        for section_idx, section in enumerate(page.get("sections", []), start=1):
            section_id = f"section-{page_idx}-{section_idx}"
            title_key = f"forms.{domain}.{section_id}_title"
            desc_key = f"forms.{domain}.{section_id}_description"
            i18n_by_lang["en"][title_key] = section.get("label", section_id)
            i18n_by_lang["en"][desc_key] = page.get("label", "")
            for lang in translation_files:
                i18n_by_lang.setdefault(lang, {})
                i18n_by_lang[lang][title_key] = translate(lang, section.get("label", section_id))
                i18n_by_lang[lang][desc_key] = translate(lang, page.get("label", ""))

            fields = []
            for question in section.get("questions", []):
                fid = f"field-{field_idx:03d}"
                field_idx += 1
                qopts = question.get("questionOptions", {})
                label = question.get("label", question.get("id", fid))
                concept_uuid = qopts.get("concept")
                key_prefix = f"forms.{domain}.{fid}"
                i18n_by_lang["en"][f"{key_prefix}_label"] = label
                i18n_by_lang["en"][f"{key_prefix}_hint"] = question.get("questionInfo", "")
                i18n_by_lang["en"][f"{key_prefix}_placeholder"] = ""
                for lang in translation_files:
                    i18n_by_lang.setdefault(lang, {})
                    i18n_by_lang[lang][f"{key_prefix}_label"] = translate(lang, label)
                    i18n_by_lang[lang][f"{key_prefix}_hint"] = translate(lang, question.get("questionInfo", ""))
                    i18n_by_lang[lang][f"{key_prefix}_placeholder"] = ""

                field = {
                    "id": fid,
                    "type": lime_field_type(question),
                    "label": f"{{{{i18n:{key_prefix}_label}}}}",
                    "hint": f"{{{{i18n:{key_prefix}_hint}}}}",
                    "placeholder": f"{{{{i18n:{key_prefix}_placeholder}}}}",
                    "fhirPath": "Observation.valueString",
                    "fhirResource": fhir_resource,
                    "required": bool(question.get("required")),
                    "readOnly": False,
                    "hidden": False,
                    "validation": {},
                    "displayCondition": None,
                    "sourceConceptUuid": concept_uuid,
                    "sourceQuestionId": question.get("id"),
                    "normalizationStatus": "draft-converted",
                }
                if field["type"] == "number":
                    field["fhirPath"] = "Observation.valueQuantity.value"
                elif field["type"] == "datetime":
                    field["fhirPath"] = "Observation.valueDateTime"
                elif field["type"] == "select":
                    field["fhirPath"] = "Observation.valueCodeableConcept"
                    field["options"] = [
                        {
                            "value": ans.get("concept"),
                            "display": ans.get("label") or ans.get("concept"),
                            "system": "urn:openmrs:concept",
                        }
                        for ans in qopts.get("answers", [])
                    ]
                fields.append(field)
                mappings.append(
                    {
                        "fieldId": fid,
                        "sourceQuestionId": question.get("id"),
                        "sourceConceptUuid": concept_uuid,
                        "fhirResource": fhir_resource,
                        "fhirPath": field["fhirPath"],
                        "standardCodeResolved": False,
                        "normalizationStatus": "draft-converted",
                    }
                )

            sections.append(
                {
                    "id": section_id,
                    "title": f"{{{{i18n:{title_key}}}}}",
                    "description": f"{{{{i18n:{desc_key}}}}}",
                    "repeating": False,
                    "fields": fields,
                }
            )

    form = {
        "$schema": "https://zarishsphere.com/schema/form/v1",
        "id": f"zs-form-{domain}",
        "title": f"{{{{i18n:forms.{domain}.title}}}}",
        "description": f"{{{{i18n:forms.{domain}.description}}}}",
        "version": "0.1.0-draft",
        "fhirResource": fhir_resource,
        "status": "draft",
        "tags": tags,
        "programs": programs,
        "sections": sections,
        "logic": [],
        "calculatedFields": [],
    }
    return form, i18n_by_lang, mappings


def convert_lime_phq9() -> tuple[dict, dict, list[dict]]:
    return convert_lime_form(
        "f07-mh-phq-9",
        "core_mental_health_phq9",
        "PHQ-9 Depression Screening",
        "Draft conversion of the LIME PHQ-9 form into ZarishSphere schema.",
        "Observation",
        ["core", "mental-health", "phq9"],
        ["shared-mental-health"],
    )


def convert_lime_er_triage() -> tuple[dict, dict, list[dict]]:
    return convert_lime_form(
        "f41-er-triage-form",
        "core_emergency_er_triage",
        "Emergency Room Triage",
        "Draft conversion of the LIME ER Triage form into ZarishSphere schema.",
        "Observation",
        ["core", "emergency", "triage"],
        ["shared-emergency"],
    )


def convert_lime_opd_general() -> tuple[dict, dict, list[dict]]:
    return convert_lime_form(
        "f44-opd-general-form",
        "core_clinical_opd_general",
        "General Outpatient Consultation",
        "Draft conversion of the LIME OPD General form into ZarishSphere schema.",
        "Observation",
        ["core", "opd", "general-consultation"],
        ["shared-opd"],
    )


def write_normalized_outputs() -> None:
    BGD_NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    conversions = {
        "patient-data": convert_patient_data(),
        "patient-vitals": convert_patient_vitals(),
        "patient-diagnosis": convert_patient_diagnosis(),
        "entrance-and-exit": convert_entrance_and_exit(),
        "hepatitis-c": convert_hepatitis_c(),
    }
    index = []
    for slug, (form, i18n, mapping_rows) in conversions.items():
        base = BGD_NORMALIZED_DIR / slug
        write_json(base / "form.json", form)
        write_json(base / "i18n" / "en.json", {"en": i18n})
        write_json(base / "field-mappings.json", mapping_rows)
        index.append(
            {
                "slug": slug,
                "formId": form["id"],
                "status": form["status"],
                "fieldCount": len(form["sections"][0]["fields"]),
                "mappingFile": str(base / "field-mappings.json"),
            }
        )
    write_json(BGD_NORMALIZED_DIR / "NORMALIZED_FORMS_INDEX.json", index)


def write_core_normalized_outputs() -> None:
    CORE_NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    conversions = {
        "phq9": convert_lime_phq9(),
        "er-triage": convert_lime_er_triage(),
        "opd-general": convert_lime_opd_general(),
    }
    index = []
    for slug, (form, i18n_by_lang, mapping_rows) in conversions.items():
        base = CORE_NORMALIZED_DIR / slug
        write_json(base / "form.json", form)
        for lang, payload in i18n_by_lang.items():
            write_json(base / "i18n" / f"{lang}.json", {lang: payload})
        write_json(base / "field-mappings.json", mapping_rows)
        index.append(
            {
                "slug": slug,
                "formId": form["id"],
                "status": form["status"],
                "sectionCount": len(form["sections"]),
                "fieldCount": sum(len(section["fields"]) for section in form["sections"]),
                "languages": sorted(i18n_by_lang.keys()),
                "mappingFile": str(base / "field-mappings.json"),
            }
        )
    write_json(CORE_NORMALIZED_DIR / "NORMALIZED_FORMS_INDEX.json", index)


def write_conversion_summary(unwrapped: list[dict]) -> None:
    summary = {
        "unwrappedForms": unwrapped,
        "normalizedForms": [
            {
                "slug": "patient-data",
                "output": str(BGD_NORMALIZED_DIR / "patient-data" / "form.json"),
            },
            {
                "slug": "patient-vitals",
                "output": str(BGD_NORMALIZED_DIR / "patient-vitals" / "form.json"),
            },
            {
                "slug": "patient-diagnosis",
                "output": str(BGD_NORMALIZED_DIR / "patient-diagnosis" / "form.json"),
            },
            {
                "slug": "entrance-and-exit",
                "output": str(BGD_NORMALIZED_DIR / "entrance-and-exit" / "form.json"),
            },
            {
                "slug": "hepatitis-c",
                "output": str(BGD_NORMALIZED_DIR / "hepatitis-c" / "form.json"),
            },
            {
                "slug": "core-phq9",
                "output": str(CORE_NORMALIZED_DIR / "phq9" / "form.json"),
            },
            {
                "slug": "core-er-triage",
                "output": str(CORE_NORMALIZED_DIR / "er-triage" / "form.json"),
            },
        ],
        "notes": [
            "These are first-pass normalized forms.",
            "Vitals fields have the strongest resolved LOINC mappings.",
            "Diagnosis and core forms still require deeper terminology harmonization to replace OpenMRS-only coded options.",
        ],
    }
    write_json(BGD_REPO / "CONVERSION_SUMMARY.json", summary)


def main() -> None:
    unwrapped = unwrap_wrapper_forms()
    write_normalized_outputs()
    write_core_normalized_outputs()
    write_conversion_summary(unwrapped)


if __name__ == "__main__":
    main()
