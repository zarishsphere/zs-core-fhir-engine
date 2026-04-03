# ZarishSphere External Asset Repo Blueprint

This blueprint converts the external source material under `/home/ariful/Desktop/zarishsphere/_cloned` into a realistic ZarishSphere repository structure.

## First Principles

- Do not copy whole external platforms into ZarishSphere.
- Separate `standards`, `content`, `country config`, `analytics`, and `migration logic`.
- Keep one canonical home for each asset family.
- Treat OpenMRS/Bahmni forms as source content, not as final FHIR truth.
- Use country packages to extend shared core content instead of duplicating everything.

## What FSH Files Are

`*.fsh` files are **FHIR Shorthand** files. They are a compact authoring format used to define:

- FHIR profiles
- extensions
- code systems
- value sets
- naming systems

In ZarishSphere, these belong in standards and terminology repositories, not in runtime app repos.

## Repositories To Keep Or Strengthen Now

- `zs-data-fhir-profiles`
  Shared ZarishSphere FHIR R5 profiles, extensions, examples, and validation-ready artifacts.

- `zs-docs-platform`
  Platform narrative, diagrams, integration guidance, and country package documentation.

- `zs-docs-standards`
  Governance, naming conventions, architecture rules, and migration standards.

- `zs-core-fhir-engine`
  Runtime FHIR server only. No country-specific content should live here except sample/demo assets.

## Repositories To Create Next

- `zs-country-bgd-fhir-ig`
  Bangladesh derivative IG package and publishing assets.

- `zs-country-bgd-terminology`
  Bangladesh code systems, naming systems, value sets, and terminology bindings extracted from the Bangladesh IG.

- `zs-content-forms-core`
  Reusable cross-country form library from LIME-EMR and other neutral sources.

- `zs-content-forms-bgd`
  Bangladesh-specific forms and translations from `bangladesh-config`.

- `zs-content-forms-ken`
  Kenya-specific forms and translations from `kenyahmis`.

- `zs-content-terminology-core`
  Shared OpenMRS/OpenConceptLab-ready concepts, findings, questions, and answer sets.

- `zs-content-terminology-bgd`
  Bangladesh-specific concept templates and metadata packs.

- `zs-country-bgd-openmrs-config`
  Bangladesh runtime config for OpenMRS/Bahmni deployments.

- `zs-country-ken-openmrs-config`
  Kenya runtime config for Kenya-style OpenMRS/Ozone deployments.

- `zs-distro-openmrs3-humanitarian`
  Modern reference distro package modeled from LIME-EMR's inheritance pattern.

- `zs-country-site-templates`
  Site-level packs such as locations, ID generation rules, address hierarchy, frontend branding, and environment config.

- `zs-analytics-sql-bgd`
  Curated Bangladesh analytics SQL and warehouse views.

- `zs-content-reporting-maps`
  Reporting and interoperability maps such as IDSR and LIMS bridges.

- `zs-migration-bht`
  Legacy extraction scripts, reporting SQL, and conversion utilities from BHT sources.

## Source To Target Mapping

### Bangladesh Core FHIR IG

- Move FSH profiles and extensions into `zs-data-fhir-profiles`.
- Move Bangladesh-only code systems and value sets into `zs-country-bgd-terminology`.
- Move IG publishing assets and narrative pages into `zs-country-bgd-fhir-ig`.

### Bangladesh Config

- Move `clinical_forms/*.json` and translations into `zs-content-forms-bgd`.
- Move `openmrs/templates/*concept*.csv` into `zs-content-terminology-bgd`.
- Move `bahmni-mart/viewSql/*.sql` into `zs-analytics-sql-bgd`.
- Move deploy/runtime config into `zs-country-bgd-openmrs-config`.
- Keep database dumps out of the main content repos.

### LIME-EMR

- Use distro structure as the blueprint for `zs-distro-openmrs3-humanitarian`.
- Move reusable forms into `zs-content-forms-core`.
- Move multilingual translations into the same form repo, grouped by form id.
- Move reusable concept packs into `zs-content-terminology-core`.
- Move site configs into `zs-country-site-templates`.

### KenyaHMIS

- Move form JSON assets into `zs-content-forms-ken`.
- Move reusable HIV/TB program content into `zs-content-program-hiv`.
- Move runtime config into `zs-country-ken-openmrs-config`.

### BHT-EMR-API

- Extract reporting SQL, program maps, and metadata defaults into `zs-migration-bht` and `zs-content-reporting-maps`.
- Do not adopt the Ruby backend as a ZarishSphere platform dependency.

### Old ZarishSphere

- Reuse only validated messaging and diagrams in `zs-docs-platform`.
- Remove promises that do not match the current repo reality.

## Migration Sequence

1. Standardize Bangladesh FHIR assets.
2. Standardize LIME-EMR distro and core form inheritance.
3. Standardize Bangladesh forms, concepts, and analytics.
4. Standardize Kenya country packages.
5. Extract legacy BHT mappings.

## Definition Of Done For This Program

- Every external asset family has one canonical ZarishSphere repo.
- Country repos extend shared repos instead of copying them.
- Standards repos hold FHIR truth.
- Content repos hold forms, terminology, and translations.
- Runtime repos hold server code only.
