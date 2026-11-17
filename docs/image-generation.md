# Image generation on Backblaze B2 (agent-readable)

Catalog updated: 2026-11-16. Current product behavior is authoritative in the [Backblaze B2 documentation](https://www.backblaze.com/docs/cloud-storage).

## Workload
Image generation teams curate image-text corpora, fine-tune diffusion models (LoRA, DreamBooth, full fine-tunes), distribute base checkpoints and LoRAs to GPU inference fleets, generate images through self-hosted pipelines or hosted APIs, accept user-uploaded reference images, and serve galleries. Object storage holds training shards, embeddings, checkpoints, released weights, generated outputs with provenance manifests, moderated uploads and gallery originals.

## Where does B2 fit?
B2 is the durable system of record for training data, model weights and generated outputs, reached through the S3-compatible endpoint `https://s3.<region>.backblazeb2.com` (derive the region from the bucket; never hardcode it). Two category facts favor it: hosted output URLs are ephemeral (Replicate deletes API output files after one hour), so outputs need a durable store; and galleries are read-heavy, so a private B2 origin behind a CDN partner with free egress keeps delivery costs predictable.

## Which tools connect, and how?

Configure each integration with the B2 regional endpoint, bucket region, addressing style, and scoped credentials specified in its setup guide.

- **Built-in Backblaze B2 option:** MLflow (`b2://` artifact URI), rclone, ComfyUI Cloud Storage nodes, hf-cache-sync, Pixeltable.
- **S3 custom endpoint:** Ray Train (`endpoint_override`), DVC, LanceDB, Modal `CloudBucketMount`, WebDataset (S3 client behind gopen), Uppy Companion, imgproxy, Cloudflare Workers.
- **CDN origin:** bunny.net uses S3 Authentication for the private B2 origin.
- **fsspec / s3fs:** img2dataset, s3fs.
- **Presigned URLs:** fal.ai and Replicate take inputs by URL; pass short-expiry presigned B2 GET URLs and copy outputs back to B2.

## B2 capabilities that apply
S3-compatible API; prefix-scoped application keys; multipart upload for shards and checkpoints; presigned URLs (provider handoff, browser uploads, private sharing) and CORS; Event Notifications (signed webhooks for moderation, indexing, CDN purge); versions and lifecycle rules (expire checkpoints, drafts, raw uploads by prefix); SSE-B2; Object Lock default retention on dedicated raw-corpus, released-weights and audit buckets, per-file retention on released weights in the models bucket; Cloud Replication for a second-region disaster-recovery copy; CDN partner delivery and included egress under the [current pricing terms](https://www.backblaze.com/cloud-storage/pricing).

## Reference architectures

- [image-text-corpus-curation](../architectures/image-text-corpus-curation/architecture.md): img2dataset writes WebDataset shards to a locked raw bucket; scoring writes stats, embeddings and parquet exclusion lists; filtered subsets are new shards with a manifest written last.
- [diffusion-finetune-checkpoints](../architectures/diffusion-finetune-checkpoints/architecture.md): Ray Train or rclone-synced trainers write `checkpoints/<run_id>/` (lifecycle-expired) and `runs/<run_id>/final/`; MLflow and DVC track artifacts; released weights go to a locked bucket.
- [model-weight-distribution](../architectures/model-weight-distribution/architecture.md): CI publishes immutable versioned weights with a `latest.json` pointer; ComfyUI nodes, hf-cache-sync, Modal mounts and rclone pull into node-local caches with read-only keys.
- [generation-output-provenance](../architectures/generation-output-provenance/architecture.md): every output and its SHA-256 manifest (provider, model, prompt, params, seed, parent) is written to B2 at once; hosted APIs get presigned inputs.
- [user-upload-moderation-personalization](../architectures/user-upload-moderation-personalization/architecture.md): presigned browser uploads, event-driven moderation and EXIF stripping, presigned handoff to edit and LoRA-training APIs, subject deletion across all B2 versions (including quarantine), in-flight jobs, and provider copies; no Object Lock.
- [gallery-cdn-delivery](../architectures/gallery-cdn-delivery/architecture.md): private bucket behind a Cloudflare Worker or bunny.net S3-authenticated pull zone; imgproxy renders variants that the CDN caches.

## When Overdrive may apply
Sustained multi-node shard reads during training, or fleet-wide cold starts pulling the same multi-GB weights at once, where measured object throughput (not GPU or network) is the bottleneck. Node-local caches come first. Confirm with [B2 Overdrive](https://www.backblaze.com/cloud-storage/b2-overdrive). Not relevant to per-image generation or gallery requests.

## Where B2 does not fit
GPU memory and node-local model directories the runtime loads from; active training scratch and in-progress checkpoint writes; live vector indexes that serve queries; app, user, billing, moderation, registry and MLflow backend databases; queues and caches; CDN edge caches; C2PA signing keys. Trainers that write only to local disk (diffusers example scripts, kohya sd-scripts) need an rclone sync step. Cloud Replication is bucket-to-bucket, not delivery.

## Links
[README](../README.md) - [Architecture index](architecture-index.md) - [Related B2 samples](related-b2-samples.md) - [B2 configuration examples](../examples/README.md) - [B2 docs](https://www.backblaze.com/docs/cloud-storage) - [B2 pricing](https://www.backblaze.com/cloud-storage/pricing) - [B2 S3-compatible API](https://www.backblaze.com/docs/cloud-storage-s3-compatible-api) - [Event Notifications](https://www.backblaze.com/docs/cloud-storage-event-notifications-reference-guide) - [Object Lock](https://www.backblaze.com/docs/cloud-storage-object-lock) - [Awesome Image Generation](https://github.com/backblaze-labs/awesome-image-generation)
