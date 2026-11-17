# LanceDB connection profile

Use this profile for embedding tables stored on B2. Provision the bucket using the [configuration examples](README.md) first. Run the commands from the repository root with Python 3.12. Keep these package versions together:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install 'lancedb==0.20.0' 'pylance==0.23.2' 'pyarrow==18.1.0'
```

The pinned [Lance S3 commit handler](https://github.com/lance-format/lance/blob/v0.23.2/rust/lance-table/src/io/commit.rs) writes manifests without an atomic create-only check. **Allow only one active writer per table.** Send mutations through one writer service and serialize appends, updates, index builds, compaction and cleanup. Separate producers submit work to that service; they must not open their own writable tables. Stop the old writer before activating a replacement. Read-only clients can run concurrently.

Set the non-secret configuration below. Supply `B2_APPLICATION_KEY_ID` and `B2_APPLICATION_KEY` as exported environment variables from your secrets manager or a gitignored `0600` environment file. The writer key needs `listBuckets,listFiles,readFiles,writeFiles`, restricted to this bucket and database prefix. Readers need `listFiles,readFiles`; add `deleteFiles` only to a controlled maintenance role that permanently removes obsolete versions.

```bash
: "${ORG:?Set ORG to your globally unique bucket prefix}"
: "${B2_REGION:?Set B2_REGION to the bucket region}"
export B2_REGION
export B2_BUCKET_NAME="$ORG-imggen-corpus-work"
export LANCE_DB_PREFIX="embeddings/curation-v1"

# Run during provisioning, then store the returned secret securely.
b2 key create --bucket "$B2_BUCKET_NAME" --name-prefix "$LANCE_DB_PREFIX/" \
  corpus-curation-lance-writer listBuckets,listFiles,readFiles,writeFiles
```

Use this connection in the writer service or a read-only client. This block lists tables without creating or changing one:

```python
import os
import lancedb

region = os.environ["B2_REGION"]
bucket = os.environ["B2_BUCKET_NAME"]
prefix = os.environ["LANCE_DB_PREFIX"].strip("/")
db = lancedb.connect(
    f"s3://{bucket}/{prefix}",
    storage_options={
        "endpoint": f"https://s3.{region}.backblazeb2.com",
        "region": region,
        "aws_access_key_id": os.environ["B2_APPLICATION_KEY_ID"],
        "aws_secret_access_key": os.environ["B2_APPLICATION_KEY"],
    },
)
print(db.table_names())
```

The URI identifies a database prefix; tables are created below it. Keep all credentials scoped to that prefix. A dependency upgrade can change the S3 commit protocol: preserve the single-writer behavior or adopt a commit coordinator supported by the selected Lance release and B2. Do not assume that AWS S3 conditional-write operations are available on another S3-compatible service.

[Back to configuration examples](README.md)

