# Agent guide

Use this repository to design or review storage workflows for image generation teams using Backblaze B2.

<!-- CODEGRAPH_START -->
## CodeGraph

When a `.codegraph/` directory exists at the repository root, use `codegraph explore "<question or symbols>"` before grep, find, or broad file reads when locating or understanding code. If the directory does not exist, skip CodeGraph; indexing is a maintainer decision.
<!-- CODEGRAPH_END -->

## Sources of truth

1. `catalog/architectures.yaml` is the machine-readable catalog of architectures, third-party integrations (with `connection_type`) and external sample applications. `schemas/architecture-catalog.schema.json` validates it.
2. `architectures/*/architecture.md` contains the detailed design, B2 zones, boundaries and security.
3. `examples/` contains B2 configuration templates.
4. Current Backblaze product behavior is authoritative at <https://www.backblaze.com/docs/cloud-storage>. Pricing is authoritative at <https://www.backblaze.com/cloud-storage/pricing>.

Describe the documented connection for each integration: a B2 backend or provider preset, a custom S3 endpoint, presigned URLs, or an application worker using an SDK. Specify the endpoint, region, addressing style, required operations, and credential scope. Attribute product capabilities to the linked vendor documentation or source code. Describe sample applications by the workflow they implement. Use `native-b2-option` for an actual B2 backend or B2-specific provider preset; use `s3-custom-endpoint` for a configurable S3 connection.

For a single-file read of the summary and every architecture, use `llms-full.txt`.

## Generated files

Run `python3 tools/generate_catalog.py` after editing the catalog. Do not hand-edit generated sections in `README.md`, `docs/related-b2-samples.md`, `docs/architecture-index.md`, `skill/references/architecture-catalog.md`, `llms.txt`, or `llms-full.txt`. `llms-full.txt` concatenates narrative pages, so regenerate after editing `docs/image-generation.md` or any `architecture.md`.

Validate generated output with:

```bash
python3 tools/generate_catalog.py --check
python3 tools/check_markdown_links.py            # add --external to probe outbound links
python3 -m pytest tests
```

## Operational invariants

- Derive `https://s3.<region>.backblazeb2.com` from the bucket region; do not hardcode a real region.
- Use prefix-scoped application keys. Keep master or administrative keys out of runtime services.
- The master application key does not work with the S3-compatible API; use an application key ([B2 S3-compatible API](https://www.backblaze.com/docs/cloud-storage-s3-compatible-api), [MLflow B2 artifact store](https://mlflow.org/docs/latest/self-hosting/architecture/artifact-store/)).
- Treat presigned URLs as bearer credentials; hand hosted APIs short-TTL presigned GETs, never keys.
- Copy hosted-API outputs to B2 on arrival; their URLs expire.
- Default retention is bucket-level: use it only on dedicated raw-corpus, released-weights and audit buckets. A mixed bucket (models) gets per-file retention set by CI and no default. Never lock purgeable user uploads.
- Lifecycle rules match by prefix: keep expiring data (checkpoints, drafts, raw uploads) under its own top-level prefix.
- Write manifests and pointers last as completion markers; never overwrite a released version.
- Keep GPUs, node-local model caches, vector serving, databases, queues and edge caches off object storage.
- Never commit credentials, customer data, or real presigned URLs.
