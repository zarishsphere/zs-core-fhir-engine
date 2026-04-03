# Repo Creation Matrix

This matrix defines the next ZarishSphere repositories that should be created from the external sources under `/home/ariful/Desktop/zarishsphere/_cloned`.

## Now

| Repo | Layer | Source | Purpose |
|---|---|---|---|
| `zs-country-bgd-fhir-ig` | `LAYER_06_DATA` | `BD-Core-FHIR-IG-main` | Bangladesh country implementation guide package |
| `zs-country-bgd-terminology` | `LAYER_06_DATA` | `BD-Core-FHIR-IG-main` | Bangladesh code systems, value sets, naming systems |
| `zs-content-forms-core` | `LAYER_06_DATA` | `LIME-EMR` | Shared humanitarian forms reused across countries |
| `zs-content-forms-bgd` | `LAYER_06_DATA` | `bangladesh-config` | Bangladesh-specific clinical forms and translations |
| `zs-content-terminology-bgd` | `LAYER_06_DATA` | `bangladesh-config` | Bangladesh-specific concepts and metadata templates |
| `zs-distro-openmrs3-humanitarian` | `LAYER_08_DISTROS` | `LIME-EMR` | Modern OpenMRS 3 distro structure and inheritance pattern |

## Next

| Repo | Layer | Source | Purpose |
|---|---|---|---|
| `zs-country-bgd-openmrs-config` | `LAYER_08_DISTROS` | `bangladesh-config` | Runtime deployment/config package for Bangladesh |
| `zs-country-site-templates` | `LAYER_08_DISTROS` | `LIME-EMR` | Site-level location, branding, idgen, and frontend packs |
| `zs-content-forms-ken` | `LAYER_06_DATA` | `kenyahmis` | Kenya program forms |
| `zs-country-ken-openmrs-config` | `LAYER_08_DISTROS` | `kenyahmis` | Kenya runtime config package |
| `zs-analytics-sql-bgd` | `LAYER_06_DATA` | `bangladesh-config` | Bangladesh reporting SQL and analytics views |
| `zs-content-reporting-maps` | `LAYER_10_INTEROP` | `BHT-EMR-API`, `bangladesh-config` | IDSR, LIMS, and reporting bridge maps |

## Later

| Repo | Layer | Source | Purpose |
|---|---|---|---|
| `zs-migration-bht` | `LAYER_10_INTEROP` | `BHT-EMR-API` | One-off legacy extraction and migration utilities |
| `zs-content-terminology-core` | `LAYER_06_DATA` | `LIME-EMR` | Shared non-country-specific concept packs |
| `zs-content-program-hiv` | `LAYER_06_DATA` | `kenyahmis`, `BHT-EMR-API` | HIV-specific cross-country content package |

## Rules

- Shared reusable assets go to `LAYER_06_DATA`.
- Runtime distro and deployment packages go to `LAYER_08_DISTROS`.
- Bridges, migration logic, and interoperability maps go to `LAYER_10_INTEROP`.
- Country-specific assets should not be placed in `zs-core-fhir-engine`.
- Generic assets should not stay trapped inside country repositories if they can be promoted to shared core content.
