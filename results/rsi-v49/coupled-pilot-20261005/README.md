# V49 pilot original evidence

All original regular-file bytes, including journals and gzip episode evidence, are in RAW_EVIDENCE.tar.gz. RAW_PACKAGE.json records their SHA-256 and byte-for-byte archive verification. The full original campaign replay passed before packaging.

Extract only into a new empty directory after verifying the package hash and inspecting members; never overwrite original results. Run `python -m experiment.rsi_v49.campaign check --output-dir <extracted-directory>` with the recorded runtime and preserved apparatus ancestry. Replay is read-only and is not another scientific attempt.
