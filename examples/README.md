# B2 configuration examples

Configuration templates for the buckets in these [reference architectures](../docs/architecture-index.md). Run command blocks from this repository's `examples/` directory using Bash and the B2 CLI v4. Authenticate the CLI with a provisioning credential before creating buckets or application keys. Configuration fields are documented in the [B2 API reference](https://www.backblaze.com/apidocs).

Set `ORG` to a globally unique bucket-name prefix. Set the additional variables used by the selected command block, and replace values shown in `<angle brackets>` before running it. Choose retention periods, lifecycle settings, and application-key capabilities for the workload; lifecycle rules permanently delete expired object versions.

| Variable | Purpose |
|---|---|
| `ORG` | Globally unique bucket-name prefix. |
| `RUN_ID` | Training-run identifier used to scope checkpoint writes. |

| File | Applies to | Purpose |
|---|---|---|
| `cors.json` | uploads bucket | Browser presigned PUT from the app origin ([user-upload-moderation-personalization](../architectures/user-upload-moderation-personalization/architecture.md)) |
| `event-notifications.json` | uploads bucket | Signed webhook on new uploads to trigger moderation; the `runs/` and `public/` rules in other architectures follow the same shape and have no separate file |
| `lifecycle-corpus-work.json` | corpus work bucket | Expire re-computable `stats/` ([image-text-corpus-curation](../architectures/image-text-corpus-curation/architecture.md)) |
| `lifecycle-training.json` | training bucket | Expire intermediate `checkpoints/` and `samples/` ([diffusion-finetune-checkpoints](../architectures/diffusion-finetune-checkpoints/architecture.md)) |
| `lifecycle-uploads.json` | uploads bucket | Expire raw uploads and quarantine |
| `lifecycle-gallery.json` | gallery bucket | Delete hidden `public/` versions after unpublish ([gallery-cdn-delivery](../architectures/gallery-cdn-delivery/architecture.md)) |
| `lifecycle-outputs.json` | outputs bucket | Expire drafts and provider inputs; purge hidden run versions ([generation-output-provenance](../architectures/generation-output-provenance/architecture.md)) |
| `object-lock.json` | raw-corpus, released-weights, audit buckets | Default governance retention (the models bucket uses per-file retention instead) |
| `sse.json` | any bucket | SSE-B2 default encryption |
| `replication.json` | models bucket | Bucket-to-bucket copy to a second-region fleet bucket ([model-weight-distribution](../architectures/model-weight-distribution/architecture.md)); not customer delivery |

Retention periods and day counts are placeholders. Set them from your policies; lifecycle deletes data. B2 lifecycle hides a file after `daysFromUploadingToHiding` and deletes hidden versions after `daysFromHidingToDeleting` ([lifecycle rules](https://www.backblaze.com/docs/cloud-storage-lifecycle-rules)). Rules match by file-name prefix, so keep expiring data under its own top-level prefix. `cors.json` allows any request header; narrow `allowedHeaders` to what your upload client sends once you have tested it.

```bash
# Bucket names are globally unique; prefix them with your org. Object Lock cannot be disabled once enabled.
b2 bucket create --file-lock-enabled "$ORG-imggen-corpus-raw" allPrivate
b2 bucket create "$ORG-imggen-corpus-work" allPrivate
b2 bucket create "$ORG-imggen-training" allPrivate
b2 bucket create --file-lock-enabled "$ORG-imggen-released-weights" allPrivate
b2 bucket create --file-lock-enabled "$ORG-imggen-models" allPrivate   # no default retention; CI sets per-file retention on releases
b2 bucket create "$ORG-imggen-outputs" allPrivate
b2 bucket create --file-lock-enabled "$ORG-imggen-audit" allPrivate
b2 bucket create "$ORG-imggen-uploads" allPrivate          # never Object Lock: per-subject purge must succeed
b2 bucket create "$ORG-imggen-gallery" allPrivate          # private origin behind the CDN

b2 bucket update --default-server-side-encryption SSE-B2 "$ORG-imggen-uploads"
b2 bucket update --cors-rules "$(cat cors.json)" "$ORG-imggen-uploads"
b2 bucket update --lifecycle-rules "$(cat lifecycle-uploads.json)" "$ORG-imggen-uploads"
b2 bucket update --lifecycle-rules "$(cat lifecycle-corpus-work.json)" "$ORG-imggen-corpus-work"
b2 bucket update --lifecycle-rules "$(cat lifecycle-training.json)" "$ORG-imggen-training"
b2 bucket update --lifecycle-rules "$(cat lifecycle-outputs.json)" "$ORG-imggen-outputs"
b2 bucket update --lifecycle-rules "$(cat lifecycle-gallery.json)" "$ORG-imggen-gallery"
for b in corpus-raw released-weights audit; do
  b2 bucket update --default-retention-mode governance --default-retention-period "365 days" "$ORG-imggen-$b"
done

# Replication: create the destination bucket in the second region first, with Object Lock enabled because the source has it.
b2 bucket update --replication "$(cat replication.json)" "$ORG-imggen-models"

# Event notifications use the native API b2_set_bucket_notification_rules
# (key needs writeBucketNotifications); the body is event-notifications.json.
```

## Scoped application keys

Each key below is restricted to one bucket and one file-name prefix.

```bash
b2 key create --bucket "$ORG-imggen-corpus-raw"  --name-prefix raw/         ingest-writer      listFiles,writeFiles
b2 key create --bucket "$ORG-imggen-corpus-work" --name-prefix filtered/    training-reader    listFiles,readFiles
b2 key create --bucket "$ORG-imggen-training"    --name-prefix "checkpoints/$RUN_ID/" "trainer-$RUN_ID" listFiles,readFiles,writeFiles
b2 key create --bucket "$ORG-imggen-training"    --name-prefix samples/     samples-writer     listFiles,writeFiles
b2 key create --bucket "$ORG-imggen-models"      --name-prefix models/      fleet-reader       listFiles,readFiles
b2 key create --bucket "$ORG-imggen-models"      --name-prefix models/      ci-publisher       listFiles,readFiles,writeFiles,writeFileRetentions
b2 key create --bucket "$ORG-imggen-outputs"     --name-prefix inputs/      input-writer       writeFiles
b2 key create --bucket "$ORG-imggen-outputs"     --name-prefix inputs/      input-signer       readFiles
b2 key create --bucket "$ORG-imggen-outputs"     --name-prefix runs/        generation-writer  listBuckets,listFiles,readFiles,writeFiles
b2 key create --bucket "$ORG-imggen-outputs"     --name-prefix runs/        promoter-source    readFiles
b2 key create --bucket "$ORG-imggen-audit"       --name-prefix manifests/   audit-writer       listFiles,writeFiles
b2 key create --bucket "$ORG-imggen-uploads"     --name-prefix uploads/     upload-signer      writeFiles
b2 key create --bucket "$ORG-imggen-uploads" purger listFiles,readFiles,writeFiles,deleteFiles
b2 key create --bucket "$ORG-imggen-uploads"     --name-prefix approved/    provider-signer    readFiles
b2 key create --bucket "$ORG-imggen-gallery"     --name-prefix public/      cdn-origin         readFiles
b2 key create --bucket "$ORG-imggen-gallery"     --name-prefix public/      promoter           writeFiles,deleteFiles
```

`b2 key create` prints the secret once; store it in a gitignored `0600` file or a secret manager, never in shell history or logs. Bucket, lifecycle, retention, notification and replication changes need an administrative key (or the master key), so run them once from provisioning and keep that key out of runtime services.

The generation writer is a trusted server-side service key. Use per-tenant `runs/<tenant>/` restrictions when issuing separate tenant keys. `listBuckets` permits the `HeadBucket` preflight used by the optional Genblaze backend; it does not grant object reads outside the key's prefix.

## Replication caveats

If the source bucket has Object Lock enabled, the destination must too, or replication fails. Deletes and hide markers are not replicated, and replicated files are not replicated again. See [Cloud Replication](https://www.backblaze.com/docs/cloud-storage-cloud-replication).

## LanceDB embedding tables

Use the [LanceDB connection profile](lancedb.md) for pinned dependencies, credential scope and single-writer commit requirements.
