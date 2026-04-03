#!/usr/bin/env python3
"""
Extract the Bangladesh Core FHIR IG into ZarishSphere-ready local repositories.

This creates two local repo scaffolds under `_repos/LAYER_06_DATA`:

- zs-country-bgd-fhir-ig
- zs-country-bgd-terminology

The extraction is intentionally conservative:
- profiles and extensions go to the country IG package
- code systems, value sets, and naming systems go to the terminology package
- supporting narrative/page assets are copied to the IG package
- a provenance manifest is generated in each target
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


SOURCE_ROOT = Path("/home/ariful/Desktop/zarishsphere/_cloned/BD-Core-FHIR-IG-main")
TARGET_BASE = Path("/home/ariful/Desktop/zarishsphere/_repos/LAYER_06_DATA")

IG_REPO = TARGET_BASE / "zs-country-bgd-fhir-ig"
TERMINOLOGY_REPO = TARGET_BASE / "zs-country-bgd-terminology"

COPY_SETS = {
    IG_REPO: [
        "input/fsh/profile",
        "input/fsh/extensions",
        "input/pagecontent",
        "input/includes",
        "input/images",
        "input/bd.fhir.core.xml",
        "README.md",
        "CHANGELOG.md",
        "ig.ini",
        "package-list.json",
        "sushi-config.yaml",
        "LICENSE",
        ".gitignore",
    ],
    TERMINOLOGY_REPO: [
        "input/fsh/codeSystems",
        "input/fsh/valueSets",
        "input/fsh/namingSystems",
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        ".gitignore",
    ],
}


def ensure_clean_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def copy_item(rel_path: str, destination_root: Path) -> dict:
    src = SOURCE_ROOT / rel_path
    dst = destination_root / rel_path
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return {
        "source": str(src),
        "target": str(dst),
        "type": "directory" if src.is_dir() else "file",
    }


def write_repo_readme(repo: Path, title: str, summary: str, bullets: list[str]) -> None:
    lines = [
        f"# {repo.name}",
        "",
        summary,
        "",
        "## What This Repo Holds",
        "",
    ]
    for bullet in bullets:
        lines.append(f"- {bullet}")
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            "This repository was scaffolded from the Bangladesh Core FHIR Implementation Guide source material located at:",
            "",
            f"- `{SOURCE_ROOT}`",
            "",
            "The extraction manifest is recorded in `SOURCE_PROVENANCE.json`.",
            "",
            "## Notes",
            "",
            "- This is a ZarishSphere packaging scaffold, not yet a final published country package.",
            "- Country-specific assets should remain here unless they are intentionally promoted into shared ZarishSphere standards.",
            "",
        ]
    )
    (repo / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_gitignore(repo: Path) -> None:
    (repo / ".gitignore").write_text(
        "\n".join(
            [
                ".DS_Store",
                "output/",
                ".fhir/",
                ".sushi/",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_provenance(repo: Path, copied: list[dict], role: str) -> None:
    payload = {
        "source_repo": str(SOURCE_ROOT),
        "target_repo": str(repo),
        "role": role,
        "copied_items": copied,
    }
    (repo / "SOURCE_PROVENANCE.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def write_ig_scaffold(repo: Path) -> None:
    write_repo_readme(
        repo,
        "zs-country-bgd-fhir-ig",
        "Bangladesh-specific FHIR implementation guide package for ZarishSphere.",
        [
            "Bangladesh FHIR profiles",
            "Bangladesh-specific extensions",
            "IG page content and publication assets",
            "Country packaging scaffold for future GitHub repo creation",
        ],
    )


def write_terminology_scaffold(repo: Path) -> None:
    write_repo_readme(
        repo,
        "zs-country-bgd-terminology",
        "Bangladesh-specific terminology package for ZarishSphere.",
        [
            "Bangladesh code systems",
            "Bangladesh value sets",
            "Bangladesh naming systems",
            "Country terminology scaffold for future GitHub repo creation",
        ],
    )


def main() -> None:
    ensure_clean_dir(IG_REPO)
    ensure_clean_dir(TERMINOLOGY_REPO)

    ig_copied = [copy_item(path, IG_REPO) for path in COPY_SETS[IG_REPO]]
    term_copied = [copy_item(path, TERMINOLOGY_REPO) for path in COPY_SETS[TERMINOLOGY_REPO]]

    write_ig_scaffold(IG_REPO)
    write_terminology_scaffold(TERMINOLOGY_REPO)
    write_gitignore(IG_REPO)
    write_gitignore(TERMINOLOGY_REPO)
    write_provenance(IG_REPO, ig_copied, "country_ig")
    write_provenance(TERMINOLOGY_REPO, term_copied, "country_terminology")


if __name__ == "__main__":
    main()
