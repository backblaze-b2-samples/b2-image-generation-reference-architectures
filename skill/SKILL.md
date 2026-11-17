---
name: b2-image-generation
description: Design or review Backblaze B2 storage for image generation, including image-text corpus curation (img2dataset, WebDataset, LanceDB), diffusion and LoRA fine-tuning checkpoints (Ray Train, MLflow, DVC, rclone, Replicate), model-weight distribution (ComfyUI, hf-cache-sync, Modal), generated-output provenance (application workers, fal.ai, Pixeltable), user-upload moderation and purge (Uppy Companion, Event Notifications), and CDN gallery delivery (Cloudflare, bunny.net, imgproxy). Use for bucket and prefix layout, key scoping, presigned handoff, lifecycle, Object Lock, or event-driven pipelines.
---

# B2 for image generation

Choose a workflow from the bundled [architecture catalog](references/architecture-catalog.md), which also lists related B2 sample applications.

For changing service behavior, limits, and setup steps, use the canonical [Backblaze B2 documentation](https://www.backblaze.com/docs/cloud-storage). Link pricing claims to [B2 pricing](https://www.backblaze.com/cloud-storage/pricing) instead of copying numbers.

## Rules
- For LanceDB embedding tables, follow the architecture's pinned connection profile and serialize all table mutations through one writer service. Endpoint settings alone do not establish safe commit behavior across Lance versions.
- Use the S3-compatible API. Derive `https://s3.<region>.backblazeb2.com` from `B2_REGION`; never hardcode region or endpoint.
- Env (repo convention): `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION`, optional `B2_ENDPOINT`. Tools differ: hf-cache-sync and Genblaze read `B2_BUCKET`, and Genblaze reads `B2_KEY_ID` / `B2_APP_KEY`; check each tool's README. Tools that read AWS variables get a B2 application key in `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. Secrets in gitignored 0600 `.env`; never print keys.
- Restrict each key to one bucket + one prefix + the capabilities its role needs (ingest-writer, training-reader, `trainer-<run_id>`, fleet-reader, ci-publisher, upload-signer, provider-signer, cdn-origin). Master key only for provisioning; it does not work with the S3-compatible API.
- Bucket names are globally unique; prefix them with the org.
- Object Lock cannot be disabled and default retention is bucket-level: use dedicated raw-corpus, released-weights and audit buckets, or per-file retention set by CI with no default (models bucket). Never lock a bucket that holds purgeable user uploads.
- Lifecycle uses B2 semantics (hide, then delete) and matches by prefix: put checkpoints, drafts and raw uploads under their own top-level prefix.
- Hosted APIs that ingest URLs (fal.ai, Replicate) get short-TTL presigned GETs; copy their outputs to B2 at once (Replicate deletes API outputs after one hour).
- Shards inside tar files cannot be edited per sample: record exclusion lists and re-pack into new filtered shards; write the subset manifest last.
- Model weights: immutable versioned keys, `latest.json` pointer written last, read-only fleet keys, SHA-256 verification (multipart ETags are not content hashes).
- Events: webhook, verify `X-Bz-Event-Notification-Signature`, ack fast, be idempotent. For subject deletion, block new signing and writer leases, drain or cancel in-flight work, delete every version including quarantine and subject audit records, and reconcile provider copies before completion. Keep a tombstone for late callbacks.
- Galleries: private bucket behind a CDN partner with a read-only origin key; variants cached at the edge, not stored. Cloud Replication is bucket-to-bucket, not delivery.
- B2's S3-compatible API does not fully support object tagging; keep metadata in manifests.
- Overdrive only for measured sustained multi-node reads or fleet-wide cold starts; node-local caches first.

## Verify

When operating inside the full repository, use its `AGENTS.md` validation commands. When this skill is installed by itself, validate recommendations against the linked canonical product and integration documentation.
