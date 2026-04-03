# External Asset Migration Audit

This report inventories external repositories under `_cloned` and maps them into ZarishSphere-owned standards, content, and country packages.

## Core Decisions

- Treat `BD-Core-FHIR-IG-main` as the Bangladesh standards source, not as the runtime platform.
- Treat `bangladesh-config`, `LIME-EMR`, and `kenyahmis` as content mines for forms, concepts, translations, and distro patterns.
- Treat `BHT-EMR-API` as a legacy knowledge source for mappings, metadata, and reporting logic rather than code to adopt directly.
- Treat `_old_zarishsphere` as product-language input only after validating against the current repo reality.

## Recommended Target Repository Families

- `zs-data-fhir-profiles`: shared ZarishSphere FHIR profiles and extensions.
- `zs-country-bgd-fhir-ig`: Bangladesh-specific derivative IG package and publishing assets.
- `zs-country-bgd-terminology`: Bangladesh-specific code systems, value sets, and naming systems.
- `zs-content-forms-core`: reusable cross-program OpenMRS/Bahmni form library.
- `zs-content-forms-bgd`: Bangladesh-specific clinical forms and translations.
- `zs-content-forms-ken`: Kenya-specific clinical forms and translations.
- `zs-content-terminology-core`: reusable concepts, answer sets, and metadata term mappings.
- `zs-content-terminology-bgd`: Bangladesh-specific concept and metadata packs.
- `zs-country-bgd-openmrs-config`: country runtime config package for Bangladesh OpenMRS/Bahmni deployments.
- `zs-country-ken-openmrs-config`: country runtime config package for Kenya-style OpenMRS deployments.
- `zs-distro-openmrs3-humanitarian`: modern reference distro structure modeled from LIME-EMR.
- `zs-country-site-templates`: site-level initializer packages, logos, frontend configs, and location packs.
- `zs-analytics-sql-bgd`: curated analytics SQL and warehouse views from Bangladesh sources.
- `zs-content-reporting-maps`: interoperability/reporting maps such as IDSR and LIMS connectors.
- `zs-migration-bht`: one-off migration logic and legacy extraction utilities from BHT sources.

## Source Summary

### Bangladesh Core FHIR IG

- Source type: `national_fhir_ig`
- Priority: `highest`
- License marker: `LICENSE`
- Counts: FSH `41`, forms `0`, translations `0`, concept CSVs `0`, SQL `0`
- Intended use: National profiles, value sets, code systems, naming systems, and narrative governance for Bangladesh.
- Migration rule: Extract FSH, terminology, and profile definitions. Do not keep the full IG publisher cache/template in product repos.
- Target repos: `zs-data-fhir-profiles`, `zs-country-bgd-fhir-ig`, `zs-country-bgd-terminology`

### Bangladesh Bahmni/OpenMRS Config

- Source type: `country_openmrs_bahmni_config`
- Priority: `highest`
- License marker: `LICENSE`
- Counts: FSH `0`, forms `113`, translations `57`, concept CSVs `66`, SQL `58`
- Intended use: Bangladesh-specific clinical forms, translations, concepts, SQL marts, and operational config.
- Migration rule: Split forms, translations, concepts, analytics SQL, and deployment config into separate content packages. Avoid keeping database dumps in the main content repos.
- Target repos: `zs-country-bgd-openmrs-config`, `zs-content-forms-bgd`, `zs-content-terminology-bgd`, `zs-analytics-sql-bgd`

### LIME-EMR

- Source type: `openmrs3_humanitarian_distro`
- Priority: `highest`
- License marker: `LICENSE`
- Counts: FSH `0`, forms `230`, translations `153`, concept CSVs `6`, SQL `1`
- Intended use: Modern distro pattern, reusable humanitarian forms, translations, and site-level initializer structure.
- Migration rule: Use as the structural reference for packaging and inheritance. Extract reusable form content and site pattern, not MSF branding or unrelated deployment baggage.
- Target repos: `zs-distro-openmrs3-humanitarian`, `zs-content-forms-core`, `zs-content-terminology-core`, `zs-country-site-templates`

### KenyaHMIS

- Source type: `country_openmrs3_distro`
- Priority: `high`
- License marker: `LICENSE`
- Counts: FSH `0`, forms `81`, translations `0`, concept CSVs `0`, SQL `6`
- Intended use: Country-specific HIV, TB, maternal, and service-delivery forms plus Ozone/OpenMRS initializer config.
- Migration rule: Extract clinical forms and country config patterns. Treat SQL concept dumps as import sources, not canonical truth.
- Target repos: `zs-country-ken-openmrs-config`, `zs-content-forms-ken`, `zs-content-program-hiv`

### BHT-EMR-API

- Source type: `legacy_emr_backend`
- Priority: `medium`
- License marker: `not_found`
- Counts: FSH `0`, forms `0`, translations `0`, concept CSVs `0`, SQL `90`
- Intended use: Legacy program mappings, default concept/program metadata, reporting SQL, and interoperability mappings.
- Migration rule: Mine domain knowledge and mappings only. Do not adopt the full legacy backend stack into ZarishSphere.
- Target repos: `zs-migration-bht`, `zs-content-program-hiv`, `zs-content-reporting-maps`

### Old ZarishSphere

- Source type: `legacy_strategy_docs`
- Priority: `medium`
- License marker: `not_found`
- Counts: FSH `0`, forms `0`, translations `0`, concept CSVs `0`, SQL `0`
- Intended use: Legacy platform narrative, value proposition, and positioning language.
- Migration rule: Reuse only validated product language and diagrams after aligning to the current repo reality.
- Target repos: `zs-docs-platform`, `zs-docs-standards`

## Immediate Migration Order

1. Bangladesh FHIR IG into `zs-data-fhir-profiles`, `zs-country-bgd-fhir-ig`, and `zs-country-bgd-terminology`.
2. LIME-EMR distro structure into `zs-distro-openmrs3-humanitarian` and `zs-country-site-templates`.
3. Bangladesh Bahmni/OpenMRS forms, concepts, and analytics into country content repos.
4. KenyaHMIS forms into a Kenya package and program-specific content packs.
5. BHT-EMR-API mappings and metadata into migration/reporting repos after legal and relevance review.

## Important Risks

- Some sources include database dumps and installer payloads that should not become canonical truth in content repos.
- Not every source has an obvious license marker; legal review is needed before broad redistribution of extracted assets.
- OpenMRS/Bahmni forms are not automatically FHIR-native. They need concept and field mapping into ZarishSphere resources before runtime use.
- Country packages should inherit from shared core content rather than duplicate forms and terminology.

