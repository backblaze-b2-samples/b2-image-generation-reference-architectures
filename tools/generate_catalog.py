#!/usr/bin/env python3
"""Validate the architecture catalog and render its human/agent indexes."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog" / "architectures.yaml"
SCHEMA_PATH = ROOT / "schemas" / "architecture-catalog.schema.json"
README_PATH = ROOT / "README.md"
DOC_INDEX_PATH = ROOT / "docs" / "architecture-index.md"
SKILL_INDEX_PATH = ROOT / "skill" / "references" / "architecture-catalog.md"
LLMS_PATH = ROOT / "llms.txt"
LLMS_FULL_PATH = ROOT / "llms-full.txt"
RELATED_SAMPLES_PATH = ROOT / "docs" / "related-b2-samples.md"

TITLE = "B2 Reference Architectures for Image Generation"
ARCH_START = "<!-- catalog:architectures:start -->"
ARCH_END = "<!-- catalog:architectures:end -->"
INT_START = "<!-- catalog:integrations:start -->"
INT_END = "<!-- catalog:integrations:end -->"
SAMPLES_START = "<!-- catalog:samples:start -->"
SAMPLES_END = "<!-- catalog:samples:end -->"
RELATED_START = "<!-- catalog:related:start -->"
RELATED_END = "<!-- catalog:related:end -->"

# Display labels keyed by schema enum values. Labels are shared verbatim across the B2 category repos;
# each repo keeps only the values its catalog uses, and tests assert labels, schema enum and catalog agree.
CONNECTION_LABELS = {
    "s3-custom-endpoint": "S3 custom endpoint",
    "native-b2-option": "Built-in Backblaze B2 option",
    "fsspec-s3": "fsspec / s3fs",
    "presigned-url": "Presigned URLs",
    "cdn-origin": "CDN origin",
}
SAMPLE_GROUPS = {
    "workflow": "Closest workflow matches",
    "building-block": "Operational building blocks",
    "domain": "Category references",
}
# Fields that must agree when one integration id appears under several architectures.
SHARED_INTEGRATION_FIELDS = ("name", "url", "connection_type")

# Narrative pages concatenated into llms-full.txt, in reading order; architectures are inserted after the summary.
LLMS_FULL_LEAD = ["docs/image-generation.md"]
LLMS_FULL_TAIL: list[str] = []
MARKDOWN_TARGET = re.compile(r"(\]\()([^)\s]+)")


def load_catalog() -> dict:
    catalog = yaml.safe_load(CATALOG_PATH.read_text())
    validate_catalog(catalog)
    return catalog


def validate_catalog(catalog: dict) -> None:
    """Raise ValueError when the catalog breaks its schema, cross-references, or local paths."""
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    errors = sorted(validator.iter_errors(catalog), key=lambda error: list(error.path))
    if errors:
        details = "\n".join(
            f"- {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"catalog validation failed:\n{details}")
    validate_references(catalog)
    validate_local_links(catalog)


def validate_references(catalog: dict) -> None:
    # JSON Schema cannot enforce unique ids across objects or cross-list references.
    problems: list[str] = []
    for kind in ("architectures", "samples"):
        ids = [item["id"] for item in catalog.get(kind, [])]
        problems += [f"duplicate {kind} id: {item_id}" for item_id in sorted({i for i in ids if ids.count(i) > 1})]
    architecture_ids = {architecture["id"] for architecture in catalog["architectures"]}
    for sample in catalog.get("samples", []):
        problems += [
            f"sample {sample['id']} references unknown architecture: {ref}"
            for ref in sample.get("architectures", []) if ref not in architecture_ids
        ]
    first_seen: dict[str, dict] = {}
    for architecture in catalog["architectures"]:
        for integration in architecture["integrations"]:
            first = first_seen.setdefault(integration["id"], integration)
            problems += [
                f"integration {integration['id']} has conflicting {field} in {architecture['id']}"
                for field in SHARED_INTEGRATION_FIELDS if integration[field] != first[field]
            ]
    if problems:
        raise ValueError("catalog reference check failed:\n" + "\n".join(f"- {problem}" for problem in problems))


def validate_local_links(catalog: dict) -> None:
    missing: list[str] = []
    for architecture in catalog["architectures"]:
        targets = list(architecture["links"].values())
        missing += [value for value in targets if not value.startswith(("http://", "https://")) and not (ROOT / value).exists()]
    if missing:
        raise ValueError("catalog contains missing local paths: " + ", ".join(sorted(set(missing))))


def relative_link(target: str, base: Path) -> str:
    if target.startswith(("http://", "https://")):
        return target
    return Path(os.path.relpath(ROOT / target, base)).as_posix()


def markdown_link(label: str, target: str, base: Path) -> str:
    return f"[{label}]({relative_link(target, base)})"


def workflow_summary(architecture: dict) -> str:
    return " → ".join(architecture["workflow"])


def connection_detail(integration: dict) -> str:
    """Connection prose plus the optional setup-guide link."""
    setup = integration.get("setup_url")
    return integration["connection"] + (f" ([setup guide]({setup}))" if setup else "")


def architectures_by_id(catalog: dict) -> dict[str, dict]:
    return {architecture["id"]: architecture for architecture in catalog["architectures"]}


def architecture_links(architectures: list[dict], base: Path) -> str:
    """Label by id: workflow titles are too long to repeat in table cells."""
    return ", ".join(markdown_link(item["id"], item["links"]["architecture"], base) for item in architectures)


def sample_architecture_links(catalog: dict, sample: dict, base: Path) -> str:
    lookup = architectures_by_id(catalog)
    return architecture_links([lookup[ref] for ref in sample.get("architectures", [])], base)


def samples_in(catalog: dict, *groups: str) -> list[dict]:
    return [sample for sample in catalog.get("samples", []) if sample["group"] in groups]


def integration_names(architecture: dict) -> str:
    return ", ".join(item["name"] for item in architecture["integrations"])


def render_readme_architectures(catalog: dict) -> str:
    rows = [
        "| Architecture | Purpose | Integrations |",
        "|---|---|---|",
    ]
    for architecture in catalog["architectures"]:
        rows.append(
            f"| {markdown_link(architecture['name'], architecture['links']['architecture'], ROOT)} | "
            f"{architecture['summary']} | {integration_names(architecture)} |"
        )
    return "\n".join(rows)


def integrations(catalog: dict) -> list[tuple[dict, list[dict]]]:
    """Unique integrations in catalog order, each with every architecture that uses it."""
    grouped: dict[str, tuple[dict, list[dict]]] = {}
    for architecture in catalog["architectures"]:
        for integration in architecture["integrations"]:
            grouped.setdefault(integration["id"], (integration, []))[1].append(architecture)
    return list(grouped.values())


def render_readme_integrations(catalog: dict) -> str:
    rows = [
        "| Tool | Role | Connection type | How it connects to B2 | Architectures |",
        "|---|---|---|---|---|",
    ]
    for integration, architectures in integrations(catalog):
        rows.append(
            f"| [{integration['name']}]({integration['url']}) | {integration['role']} | "
            f"{CONNECTION_LABELS[integration['connection_type']]} | {connection_detail(integration)} | "
            f"{architecture_links(architectures, ROOT)} |"
        )
    return "\n".join(rows)


def render_readme_samples(catalog: dict) -> str:
    rows = [
        "| Sample | Demonstrates | Related architectures |",
        "|---|---|---|",
    ]
    for sample in samples_in(catalog, "workflow", "building-block"):
        rows.append(
            f"| [{sample['name']}]({sample['url']}) | {sample['summary']} | "
            f"{sample_architecture_links(catalog, sample, ROOT) or '—'} |"
        )
    return "\n".join(rows)


def render_readme_related(catalog: dict) -> str:
    siblings = ", ".join(f"[{item['name']}]({item['url']})" for item in catalog["related_categories"])
    return f"Other B2 reference architecture categories: {siblings}."


def related_samples_section(catalog: dict, group: str) -> str:
    base = RELATED_SAMPLES_PATH.parent
    samples = samples_in(catalog, group)
    if group == "domain":
        return "\n".join(f"- [{sample['name']}]({sample['url']}): {sample['description']}" for sample in samples)
    rows = ["| Sample | What it demonstrates | Most relevant here |", "|---|---|---|"]
    for sample in samples:
        relevance = " — ".join(part for part in (sample_architecture_links(catalog, sample, base), sample.get("relevance")) if part)
        rows.append(f"| [{sample['name']}]({sample['url']}) | {sample['description']} | {relevance or '—'} |")
    return "\n".join(rows)


def render_related_samples(catalog: dict) -> str:
    text = RELATED_SAMPLES_PATH.read_text()
    for group in SAMPLE_GROUPS:
        text = replace_section(
            text, f"<!-- catalog:samples-{group}:start -->", f"<!-- catalog:samples-{group}:end -->",
            related_samples_section(catalog, group),
        )
    return text


def replace_section(text: str, start: str, end: str, body: str) -> str:
    if start not in text or end not in text:
        raise ValueError(f"missing generated section markers: {start} / {end}")
    prefix, remainder = text.split(start, 1)
    _, suffix = remainder.split(end, 1)
    return f"{prefix}{start}\n{body}\n{end}{suffix}"


def render_readme(catalog: dict) -> str:
    text = README_PATH.read_text()
    text = replace_section(text, ARCH_START, ARCH_END, render_readme_architectures(catalog))
    text = replace_section(text, INT_START, INT_END, render_readme_integrations(catalog))
    text = replace_section(text, RELATED_START, RELATED_END, render_readme_related(catalog))
    return replace_section(text, SAMPLES_START, SAMPLES_END, render_readme_samples(catalog))


def render_docs_index(catalog: dict) -> str:
    base = DOC_INDEX_PATH.parent
    lines = [
        "<!-- Generated by tools/generate_catalog.py; edit catalog/architectures.yaml. -->",
        "# Image generation architecture index",
        "",
        "Canonical B2 product documentation: "
        f"<{catalog['canonical_documentation']}>.",
        "",
        "Use this index to choose a workflow. Each linked architecture documents its data flow, B2 zones and security boundaries.",
    ]
    for architecture in catalog["architectures"]:
        lines.extend([
            "",
            f"## {markdown_link(architecture['name'], architecture['links']['architecture'], base)}",
            "",
            architecture["summary"],
            "",
            f"- **Audience:** {', '.join(architecture['audience'])}",
            f"- **Problem:** {architecture['problem']}",
            f"- **Workflow:** {workflow_summary(architecture)}",
            f"- **Integrations:** {integration_names(architecture)}",
            f"- **Keep off B2:** {'; '.join(architecture['off_object_storage'])}",
            f"- **Expected scale:** {architecture['expected_scale']['profile']}. {architecture['expected_scale']['notes']}",
        ])
    lines.extend([
        "",
        "## Machine-readable source",
        "",
        f"The catalog is available as [{CATALOG_PATH.name}]({relative_link('catalog/architectures.yaml', base)}) "
        f"and is validated by [JSON Schema]({relative_link('schemas/architecture-catalog.schema.json', base)}).",
        "",
    ])
    return "\n".join(lines)


def render_skill_index(catalog: dict) -> str:
    lines = [
        "<!-- Generated by tools/generate_catalog.py; edit the repository catalog, then package this skill directory. -->",
        "# Architecture catalog",
        "",
        f"Catalog date: {catalog['updated']}. For changing B2 product details, use "
        f"<{catalog['canonical_documentation']}> as the authority.",
    ]
    for architecture in catalog["architectures"]:
        lines.extend([
            "",
            f"## {architecture['name']}",
            "",
            architecture["summary"],
            "",
            f"**Use when:** {architecture['problem']}",
            "",
            f"**Workflow:** {workflow_summary(architecture)}",
            "",
            f"**B2 capabilities:** {', '.join(architecture['capabilities'])}.",
            "",
            "**Integrations:** " + "; ".join(
                f"[{item['name']}]({item['url']}) ({CONNECTION_LABELS[item['connection_type']]}) — {connection_detail(item)}"
                for item in architecture["integrations"]
            ) + ".",
            "",
            f"**Keep off B2:** {'; '.join(architecture['off_object_storage'])}.",
            "",
            f"**Scale:** {architecture['expected_scale']['profile']}. {architecture['expected_scale']['notes']}",
            "",
            "**Security:** " + "; ".join(architecture["security_considerations"]) + ".",
        ])
    lines.extend([
        "",
        "## Related sample applications",
        "",
        "Sample applications for these storage workflows. Each linked repository includes source code and setup instructions.",
        "",
    ])
    lines += [f"- [{sample['name']}]({sample['url']}): {sample['summary']}." for sample in catalog.get("samples", [])]
    lines.append("")
    return "\n".join(lines)


def render_llms(catalog: dict) -> str:
    lines = [
        f"# {TITLE}",
        "",
        "> Reference architectures, third-party integrations, and B2 sample applications for curating image-text corpora, "
        "fine-tuning diffusion models, distributing model weights, persisting generated images with provenance, "
        "moderating user uploads, and delivering galleries with Backblaze B2.",
        "",
        f"Canonical Backblaze product documentation: {catalog['canonical_documentation']}. "
        "Use this index to select an architecture, integration configuration, or sample application.",
        "",
        "## Start here",
        "",
        "- [Image generation summary](docs/image-generation.md): Concise workload and capability overview.",
        "- [Architecture index](docs/architecture-index.md): Human-readable index generated from the catalog.",
        "- [Machine-readable catalog](catalog/architectures.yaml): Audiences, workflows, capabilities, integrations, security, and compliance.",
        "- [Full text](llms-full.txt): Summary and every architecture in one file.",
        "",
        "## Architectures",
        "",
    ]
    for architecture in catalog["architectures"]:
        lines.append(f"- [{architecture['name']}]({architecture['links']['architecture']}): {architecture['summary']}")
    lines.extend(["", "## Third-party integrations", ""])
    for integration, architectures in integrations(catalog):
        lines.append(
            f"- [{integration['name']}]({integration['url']}): {CONNECTION_LABELS[integration['connection_type']]}. "
            f"{connection_detail(integration)}. Architectures: {', '.join(a['links']['architecture'] for a in architectures)}"
        )
    for group, heading in SAMPLE_GROUPS.items():
        lines.extend(["", f"## Sample applications: {heading.lower()}", ""])
        lines += [f"- [{sample['name']}]({sample['url']}): {sample['summary']}." for sample in samples_in(catalog, group)]
    lines.extend([
        "",
        "## Schemas and configuration",
        "",
        "- [Architecture catalog schema](schemas/architecture-catalog.schema.json): JSON Schema for catalog/architectures.yaml.",
        "- [B2 configuration examples](examples/README.md): CORS, lifecycle, Object Lock, encryption, notifications, replication, and keys.",
        "- [Related B2 sample applications](docs/related-b2-samples.md): Sample-to-architecture mapping and selection guidance.",
        "",
        "## Official product documentation",
        "",
        f"- [Backblaze AI and machine learning]({catalog['canonical_documentation']}): Canonical B2 documentation hub.",
        "- [Backblaze B2 documentation](https://www.backblaze.com/docs/cloud-storage): Current product behavior and setup.",
        "- [Backblaze B2 pricing](https://www.backblaze.com/cloud-storage/pricing): Current pricing and egress terms.",
        "",
        "## Other B2 reference architecture categories",
        "",
        *(f"- [{item['name']}]({item['url']})" for item in catalog["related_categories"]),
        "",
        "## Optional",
        "",
        "- [Repository agent guide](AGENTS.md): Source hierarchy, generation commands, and operational invariants.",
        "- [Portable agent skill](skill/SKILL.md): Self-contained guidance for B2 image generation storage work.",
        "",
    ])
    return "\n".join(lines)


def rewrite_links(text: str, source: Path) -> str:
    """Rewrite relative Markdown link targets in a page so they resolve from the repository root."""
    def rewrite(match: re.Match) -> str:
        target = match.group(2)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)
        path, _, anchor = target.partition("#")
        resolved = Path(os.path.relpath((source.parent / path).resolve(), ROOT)).as_posix()
        return match.group(1) + resolved + (f"#{anchor}" if anchor else "")
    return MARKDOWN_TARGET.sub(rewrite, text)


def render_llms_full(catalog: dict) -> str:
    sources = LLMS_FULL_LEAD + [a["links"]["architecture"] for a in catalog["architectures"]] + LLMS_FULL_TAIL
    parts = [
        f"# {TITLE}: full text",
        "",
        "> Generated by tools/generate_catalog.py from the pages listed below; links are relative to the repository root. "
        f"Product behavior is authoritative at {catalog['canonical_documentation']}.",
    ]
    for source in sources:
        parts += ["", f"<!-- source: {source} -->", "", rewrite_links((ROOT / source).read_text().strip(), ROOT / source)]
    return "\n".join(parts) + "\n"


def expected_outputs(catalog: dict) -> dict[Path, str]:
    return {
        README_PATH: render_readme(catalog),
        DOC_INDEX_PATH: render_docs_index(catalog),
        SKILL_INDEX_PATH: render_skill_index(catalog),
        RELATED_SAMPLES_PATH: render_related_samples(catalog),
        LLMS_PATH: render_llms(catalog),
        LLMS_FULL_PATH: render_llms_full(catalog),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()
    try:
        catalog = load_catalog()
        outputs = expected_outputs(catalog)
    except (OSError, ValueError, jsonschema.SchemaError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    stale = [path for path, content in outputs.items() if not path.exists() or path.read_text() != content]
    if args.check:
        if stale:
            print("stale generated files: " + ", ".join(str(path.relative_to(ROOT)) for path in stale), file=sys.stderr)
            return 1
        print(f"catalog valid; {len(outputs)} generated files current")
        return 0

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
