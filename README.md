# B2 reference architectures for image generation

How image generation teams use Backblaze B2 across corpus curation, diffusion fine-tuning, model-weight distribution, generated-output persistence, user-upload moderation and gallery delivery. Each architecture documents the data flow, B2 zones and security boundaries, and links out to the third-party integrations and B2 sample applications that implement it.

Learn more about [Backblaze B2 for AI and machine learning](https://www.backblaze.com/cloud-storage/industries/ai-ml).

Start with the [architecture index](docs/architecture-index.md) or the [agent-readable summary](docs/image-generation.md). Current B2 product behavior is documented at [backblaze.com/docs](https://www.backblaze.com/docs/cloud-storage).

## Where does Backblaze B2 fit for image generation?

Image generation produces three kinds of large, durable data, and B2 can be the system of record for each through its S3-compatible endpoint (`https://s3.<region>.backblazeb2.com`):

- **Training data:** image-text corpora and curated subsets as WebDataset shards, from terabytes to petabytes.
- **Model weights:** multi-GB base checkpoints and many MB-scale LoRAs that every GPU worker needs.
- **Generated outputs:** millions of PNG/WebP files a month, plus provenance manifests, user uploads and galleries.

- **Store in B2:** shards, embeddings, checkpoints, released weights, generated images, manifests, moderated uploads.
- **Hand off from B2:** short-lived presigned GETs to hosted APIs that ingest only URLs (fal.ai, Replicate), whose own output URLs expire.
- **Deliver from B2:** a private origin behind a CDN partner, with free egress to partners such as Cloudflare, Fastly and bunny.net.
- **Protect in B2:** Object Lock on dedicated raw-corpus, released-weights and audit buckets; versions; scoped keys.
- **Automate with B2:** Event Notifications for moderation, indexing and cache purge.
- **Keep elsewhere:** GPUs and node-local model caches, vector serving, app, moderation and registry databases, queues, edge caches.

Pricing, egress terms and limits change: see [B2 pricing](https://www.backblaze.com/cloud-storage/pricing) and the [B2 docs](https://www.backblaze.com/docs/cloud-storage).

## Architectures

<!-- catalog:architectures:start -->
| Architecture | Purpose | Integrations |
|---|---|---|
| [Collect and curate image-text corpora into streamable training shards](architectures/image-text-corpus-curation/architecture.md) | Bulk-download URL and caption lists into WebDataset shards on B2, score them for CLIP alignment, quality, NSFW and near-duplicates, and write filtered subsets as new immutable shards with a subset manifest. Raw shards are never rewritten; diffusion training streams the subsets directly. | img2dataset, s3fs (fsspec), WebDataset, LanceDB |
| [Fine-tune LoRA and diffusion models with versioned checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) | Train LoRA, DreamBooth or full fine-tunes on curated subsets, and write each run's dataset snapshot, captions, checkpoints, sample grids and final .safetensors to run-scoped prefixes so interrupted runs resume and released weights trace back to their data. | Ray Train, MLflow, DVC, rclone, Replicate |
| [Distribute base checkpoints and LoRAs to a GPU inference fleet](architectures/model-weight-distribution/architecture.md) | Keep base checkpoints, VAEs, ControlNets and LoRAs once under a B2 models/ prefix; ComfyUI hosts, serverless GPU functions and CI pull from it into node-local caches with read-only keys and skip unchanged files. | ComfyUI Cloud Storage nodes, hf-cache-sync, Modal CloudBucketMount, rclone |
| [Generate images and persist every output with provenance manifests](architectures/generation-output-provenance/architecture.md) | Text-to-image and edit apps call self-hosted pipelines or hosted APIs, write every output to B2 immediately, and store a SHA-256 manifest of provider, model, prompt, params, seed and parent asset beside it so remix lineage, replays and audits stay possible. | ComfyUI Cloud Storage nodes, fal.ai, Replicate, Pixeltable |
| [Ingest, moderate and purge user-uploaded reference images](architectures/user-upload-moderation-personalization/architecture.md) | Browsers upload selfies, product photos and reference images directly to a private uploads/ prefix with presigned PUTs; an Event Notification triggers moderation and EXIF stripping; approved items reach edit APIs and likeness-LoRA training only as short-lived presigned GETs, and subject deletion coordinates active writers, every B2 version, quarantined originals, and provider copies. | Uppy + Companion, fal.ai, Replicate |
| [Serve generated galleries through a CDN with on-the-fly variants](architectures/gallery-cdn-delivery/architecture.md) | Approved outputs are served from a private B2 origin through Cloudflare Workers or a bunny.net pull zone with S3 authentication, and imgproxy resizes and converts originals on request so per-size variants live in the edge cache instead of the bucket. | Cloudflare Workers (private bucket), bunny.net, imgproxy |
<!-- catalog:architectures:end -->

## Third-party integrations

Use the connection method and settings listed for each integration, including its required operations and credential scope. Connection types: **Built-in Backblaze B2 option** (a B2 backend or B2-specific provider preset), **S3 custom endpoint** (set the endpoint in the tool, or in the S3 client it wraps, to `https://s3.<region>.backblazeb2.com`), **fsspec / s3fs** (`endpoint_url` in `client_kwargs`), **Presigned URLs** (time-limited URLs for provider inputs and private sharing), and **CDN origin** (the CDN authenticates requests to the private B2 origin).

<!-- catalog:integrations:start -->
| Tool | Role | Connection type | How it connects to B2 | Architectures |
|---|---|---|---|---|
| [img2dataset](https://github.com/rom1504/img2dataset) | Bulk image-text download, resize and WebDataset/parquet sharding | fsspec / s3fs | Set output_folder to `s3://<bucket>/<prefix>` and put client_kwargs.endpoint_url `https://s3.<region>.backblazeb2.com` in ~/.config/fsspec/s3.json; write webdataset or parquet output (the tfrecord writer bypasses fsspec) | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [s3fs (fsspec)](https://s3fs.readthedocs.io/en/latest/) | Shared Python filesystem layer for download, scoring and re-packing jobs | fsspec / s3fs | Pass endpoint_url `https://s3.<region>.backblazeb2.com` to S3FileSystem (or client_kwargs.endpoint_url in fsspec config) with a scoped B2 application key as key and secret | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [WebDataset](https://github.com/webdataset/webdataset) | Sequential tar-shard streaming into PyTorch training and scoring jobs | S3 custom endpoint | Open shards with `pipe:aws s3 cp --endpoint-url https://s3.<region>.backblazeb2.com s3://<bucket>/<shard>.tar -`, a gopen handler backed by boto3 with endpoint_url, or presigned HTTPS shard URLs | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [LanceDB](https://lancedb.com/) | Embedding tables for deduplication and similarity review | S3 custom endpoint | Use the pinned LanceDB 0.20.0 / pylance 0.23.2 connection profile in examples/lancedb.md, with the B2 endpoint, region and scoped credentials; serialize all table mutations through one writer service ([setup guide](https://github.com/lance-format/lance/blob/v0.23.2/rust/lance-table/src/io/commit.rs)) | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [Ray Train](https://docs.ray.io/en/latest/train/user-guides/persistent-storage.html) | Distributed training with checkpoint persistence and resume | S3 custom endpoint | Set RunConfig storage_path to `s3://<bucket>/checkpoints?endpoint_override=https://s3.<region>.backblazeb2.com`, or set AWS_ENDPOINT_URL_S3 with AWS credential variables holding a B2 application key; Ray's persistent-storage guide covers Backblaze B2 | [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) |
| [MLflow](https://mlflow.org/docs/latest/self-hosting/architecture/artifact-store/) | Experiment tracking, artifact store and model registry | Built-in Backblaze B2 option | Artifact store URI `b2://<bucket>@s3.<region>.backblazeb2.com/<path>` with AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_DEFAULT_REGION set to a B2 application key and region | [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) |
| [DVC](https://doc.dvc.org/user-guide/data-management/remote-storage/amazon-s3) | Git-pinned dataset and weight versions | S3 custom endpoint | Run `dvc remote modify <remote> endpointurl https://s3.<region>.backblazeb2.com` and store the B2 application key with `dvc remote modify --local` access_key_id and secret_access_key | [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) |
| [rclone](https://rclone.org/b2/) | Sync between B2 and local-disk trainers, bulk migration and node pre-warm | Built-in Backblaze B2 option | Use the native `b2` backend with a scoped application key (or the `s3` backend with the B2 endpoint); `rclone sync` and `rclone copy` move data between B2 and local disk | [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md), [model-weight-distribution](architectures/model-weight-distribution/architecture.md) |
| [Replicate](https://replicate.com/docs/topics/predictions/input-files) | Hosted inference and training API that ingests input files by URL | Presigned URLs | Presigned B2 GET URLs passed as hosted-file inputs; outputs are copied back to B2 because API output files are deleted after one hour ([setup guide](https://replicate.com/docs/topics/predictions/data-retention)) | [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md), [generation-output-provenance](architectures/generation-output-provenance/architecture.md), [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md) |
| [ComfyUI Cloud Storage nodes](https://github.com/backblaze-labs/comfyui-cloud-storage) | ComfyUI custom nodes for model download and cache, output save, input load and presigned sharing | Built-in Backblaze B2 option | "Backblaze B2" provider preset (COMFY_S3_PROVIDER, COMFY_S3_REGION) or COMFY_S3_ENDPOINT_URL; credentials resolve from env vars or a server-side JSON profile, never workflow JSON | [model-weight-distribution](architectures/model-weight-distribution/architecture.md), [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [hf-cache-sync](https://github.com/backblaze-labs/hf-cache-sync) | Push and pull the Hugging Face hub cache to B2 with LRU pruning | Built-in Backblaze B2 option | Set B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET, B2_REGION and B2_ENDPOINT (or the YAML storage block); the boto3 client talks to the B2 S3 endpoint | [model-weight-distribution](architectures/model-weight-distribution/architecture.md) |
| [Modal CloudBucketMount](https://modal.com/docs/reference/modal.CloudBucketMount) | Read-only bucket mount for serverless GPU functions | S3 custom endpoint | `CloudBucketMount(bucket_name, bucket_endpoint_url="https://s3.<region>.backblazeb2.com", key_prefix="models/", read_only=True, secret=...)` with a secret holding a B2 application key | [model-weight-distribution](architectures/model-weight-distribution/architecture.md) |
| [fal.ai](https://fal.ai/docs/documentation/model-apis/fal-cdn) | Hosted image generation and editing API | Presigned URLs | image_url inputs accept presigned S3-compatible URLs; outputs are copied back to B2 | [generation-output-provenance](architectures/generation-output-provenance/architecture.md), [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md) |
| [Pixeltable](https://docs.pixeltable.com/integrations/cloud-storage) | Multimodal tables that index generated images and their metadata | Built-in Backblaze B2 option | Backblaze B2 destination `https://s3.<region>.backblazeb2.com/<bucket>/<prefix>/` with b2_profile in config.toml and keys under a [b2] AWS credentials profile | [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [Uppy + Companion](https://uppy.io/docs/companion/) | Browser upload UI and signing server | S3 custom endpoint | Set s3.endpoint (COMPANION_AWS_ENDPOINT) to `https://s3.<region>.backblazeb2.com` and s3.region to the bucket region; browsers upload straight to the bucket with presigned PUT or multipart requests, so configure bucket CORS | [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md) |
| [Cloudflare Workers (private bucket)](https://www.backblaze.com/docs/cloud-storage-deliver-private-backblaze-b2-content-through-cloudflare-cdn) | CDN edge that signs requests to a private B2 origin | CDN origin | Deploy a Worker that signs origin requests to `s3.<region>.backblazeb2.com` with a read-only application key; the bucket stays private behind the CDN | [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md) |
| [bunny.net](https://www.backblaze.com/docs/cloud-storage-integrate-bunnynet-with-backblaze-b2) | CDN pull zone with S3-authenticated private origin | CDN origin | Set the pull zone origin to the bucket's S3 URL, enable S3 Authentication with the key ID, application key and bucket region, and enable Block Root Path Access ([setup guide](https://docs.bunny.net/cdn/integrations/storage/backblaze)) | [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md) |
| [imgproxy](https://docs.imgproxy.net/image_sources/amazon_s3) | On-the-fly resize and WebP/AVIF conversion behind the CDN | S3 custom endpoint | Set `IMGPROXY_USE_S3=true`, `IMGPROXY_S3_ENDPOINT=https://s3.<region>.backblazeb2.com` and `IMGPROXY_S3_REGION` to the bucket region; source URLs use `s3://<bucket>/<key>` | [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md) |
<!-- catalog:integrations:end -->

## Sample applications

External samples from [`backblaze-b2-samples`](https://github.com/backblaze-b2-samples) and [`backblaze-labs`](https://github.com/backblaze-labs) that implement B2-side patterns for these architectures.

<!-- catalog:samples:start -->
| Sample | Demonstrates | Related architectures |
|---|---|---|
| [img2dataset to WebDataset on B2](https://github.com/backblaze-b2-samples/img2dataset-webdataset-object-storage) | img2dataset shards, parquet and stats streamed into B2 with no local staging | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [DataComp image-text filtering](https://github.com/backblaze-b2-samples/datacomp-image-text-filtering) | CLIP scoring of streamed shards with filtered shards and metrics written back | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [Data-Juicer multimodal curation](https://github.com/backblaze-b2-samples/data-juicer-multimodal-curation) | Data-Juicer recipes over raw shards with refined outputs and stats per run | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [fastdup dataset cleaning](https://github.com/backblaze-b2-samples/fastdup-dataset-cleaning) | Duplicate, outlier and broken-file detection with server-side-copy quarantine | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md), [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) |
| [OpenCLIP batch embeddings](https://github.com/backblaze-b2-samples/openclip-batch-embeddings) | OpenCLIP .npy embedding shards and a FAISS index per job on B2 | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [WebDataset streaming PyTorch training](https://github.com/backblaze-b2-samples/webdataset-streaming-pytorch-training) | Tar shards streamed from B2 through a boto3-backed s3:// opener | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md), [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) |
| [Lance multimodal search](https://github.com/backblaze-b2-samples/lance-multimodal-search) | LanceDB multimodal tables on B2 for image similarity search | [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [LoRA Training Studio](https://github.com/backblaze-b2-samples/lora-training-studio) | Diffusers and peft LoRA training with every artifact under a run prefix | [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) |
| [AI Headshot Studio](https://github.com/backblaze-b2-samples/ai-headshot-studio) | Likeness LoRA from selfies with presigned-only access and per-subject purge | [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md), [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) |
| [hf-cache-sync](https://github.com/backblaze-labs/hf-cache-sync) | Hugging Face hub cache shared across machines through B2 with LRU pruning | [model-weight-distribution](architectures/model-weight-distribution/architecture.md) |
| [Backblaze B2 GitHub Action](https://github.com/backblaze-labs/b2-action) | CI upload, sync, verify, presign and Object Lock retention verbs | [model-weight-distribution](architectures/model-weight-distribution/architecture.md), [diffusion-finetune-checkpoints](architectures/diffusion-finetune-checkpoints/architecture.md) |
| [ComfyUI Cloud Storage nodes](https://github.com/backblaze-labs/comfyui-cloud-storage) | ComfyUI save, load, model-cache and presigned-share nodes | [model-weight-distribution](architectures/model-weight-distribution/architecture.md), [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [Genblaze SDK](https://github.com/backblaze-labs/genblaze) | Provider-agnostic generation with SHA-256 provenance manifests on B2 | [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [Genblaze multi-provider sample](https://github.com/backblaze-labs/genblaze-gen-media-multi-provider-sample) | Multi-provider pipeline with run-scoped prefixes and lifecycle suggestions | [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [Genblaze x GMICloud pipeline](https://github.com/backblaze-labs/genblaze-gmicloud-pipeline) | Anchor image fanned out to video models with manifests on B2 | [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [Image Generation Prompt Flow](https://github.com/backblaze-b2-samples/image-generation-prompt-flow) | Provider comparison app with image bytes on B2 and prompt history in SQLite | [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [AI Moodboard Generator](https://github.com/backblaze-b2-samples/ai-moodboard-generator) | Generated pins with sha256 sidecars delivered by presigned or CDN URLs | [generation-output-provenance](architectures/generation-output-provenance/architecture.md), [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md) |
| [AI Product Photo Studio](https://github.com/backblaze-b2-samples/ai-product-photo-studio) | Presigned reference handoff to image edits with per-run manifests | [generation-output-provenance](architectures/generation-output-provenance/architecture.md), [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md) |
| [AI Sticker Pack Generator](https://github.com/backblaze-b2-samples/ai-sticker-pack-generator) | Bucket as the system of record for generated packs, no database | [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [Comic Storyboard](https://github.com/backblaze-b2-samples/comic-storyboard-b2) | Character-consistent panels with variant lineage and SHA-256 manifests | [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [AI SaaS Starter Kit](https://github.com/backblaze-labs/ai-saas-starter-kit) | Multi-tenant generation into B2 with presigned browser uploads | [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md), [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [CLIP NSFW image moderation](https://github.com/backblaze-b2-samples/clip-nsfw-image-moderation) | Approve or quarantine routing with JSONL and CSV audit logs | [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md), [image-text-corpus-curation](architectures/image-text-corpus-curation/architecture.md) |
| [LaMa batch inpainting](https://github.com/backblaze-b2-samples/lama-batch-inpainting) | Source, mask and output prefixes with an approval step | [generation-output-provenance](architectures/generation-output-provenance/architecture.md) |
| [rembg product background removal](https://github.com/backblaze-b2-samples/rembg-product-background-removal) | Batch transparent cutouts with an optional public or CDN URL base | [generation-output-provenance](architectures/generation-output-provenance/architecture.md), [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md) |
| [B2 browser upload](https://github.com/backblaze-b2-samples/b2-browser-upload) | Direct browser uploads with presigned PUT, CORS and server-held keys | [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md) |
| [B2 Event Broker](https://github.com/backblaze-b2-samples/b2-event-broker) | Signed Event Notification fan-out to multiple subscribers | [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md), [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md) |
| [B2 Event Notifications thumbnail demo](https://github.com/backblaze-b2-samples/b2-node-thumbnail-demo) | Signed object-created event that writes a thumbnail back to B2 | [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md), [user-upload-moderation-personalization](architectures/user-upload-moderation-personalization/architecture.md) |
| [Cloudflare Worker for private B2 bucket](https://github.com/backblaze-b2-samples/cloudflare-b2) | SigV4-signing Worker that serves a private bucket through Cloudflare | [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md) |
| [Fastly Compute B2 (Rust)](https://github.com/backblaze-b2-samples/fastly-b2-rust) | Fastly Compute app with signed origin requests to a private bucket | [gallery-cdn-delivery](architectures/gallery-cdn-delivery/architecture.md) |
<!-- catalog:samples:end -->

See the [full sample cross-reference](docs/related-b2-samples.md) for selection guidance and category references.

## B2 capability map

| Area | Capabilities | Selection notes |
|---|---|---|
| Access | S3 API, presigned URLs, CORS, multipart, scoped keys (bucket + prefix + capabilities) | S3 API by default; presigned GETs for URL-only hosted APIs; presigned PUTs for browser uploads |
| Change and lifecycle | Event Notifications, versions, lifecycle (hide, then delete) | Events trigger moderation, indexing and CDN purge; lifecycle expires checkpoints, drafts and raw uploads by prefix |
| Protection | SSE-B2, SSE-C, Object Lock, Cloud Replication | Lock raw corpora, released weights and audit manifests in dedicated buckets; never lock purgeable user uploads; replication is bucket-to-bucket |
| Delivery | Egress, CDN partners, compute partners | Private origin behind a CDN for galleries; presigned URLs for private items |
| Performance | Standard B2, [Overdrive](https://www.backblaze.com/cloud-storage/b2-overdrive), local cache | Standard by default; node-local caches for model weights and repeated epochs; consider Overdrive only for measured multi-node shard reads or fleet-wide cold starts |

<!-- catalog:related:start -->
Other B2 reference architecture categories: [AI Data Providers](https://github.com/backblaze-b2-samples/b2-ai-data-provider-reference-architectures), [Generative Video](https://github.com/backblaze-b2-samples/b2-gen-video-reference-architectures), [Robotics](https://github.com/backblaze-b2-samples/b2-robotics-reference-architectures), [Autonomous Vehicles](https://github.com/backblaze-b2-samples/b2-autonomous-vehicle-reference-architectures), [Commercial Drones](https://github.com/backblaze-b2-samples/b2-commercial-drone-reference-architectures).
<!-- catalog:related:end -->

[Backblaze B2 documentation](https://www.backblaze.com/docs/cloud-storage) is canonical for product behavior; this repository provides workflow-specific designs.

## Repository layout

`catalog/` architecture, integration and sample metadata, `schemas/` catalog schema, `architectures/` docs and diagrams, `docs/` agent-readable pages, `examples/` B2 configs, `skill/` portable agent skill, `tools/` generators and checks, `tests/` tool tests, `.github/` CI and templates.

## Validate locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-catalog.txt pytest
python3 tools/generate_catalog.py --check
python3 tools/check_markdown_links.py            # add --external to probe outbound links
python3 -m pytest tests
```

## Contributing, security and license

See [CONTRIBUTING](.github/CONTRIBUTING.md); the catalog is the extension point. Report sensitive issues through the [security policy](.github/SECURITY.md). Released under the [MIT license](LICENSE); cite with [CITATION.cff](CITATION.cff).
