"""Verify a transparent metadata-only finalization; never rerun or edit the assay."""
import argparse
import gzip
import io
import json
import os
import tempfile
import zlib

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v31 import campaign, freeze

ORIGINAL = campaign.ATTEMPT.with_name("V31_PRECOMPLETION_INDEX.json")
RECEIPT = campaign.ATTEMPT.with_name("V31_INDEX_FINALIZATION.json")


def encoded(record):
    return (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()


def index_for(record, raw, plaintext):
    return {"schema": "mira-genesis-v31-lossless-index-v1", "status": record["status"],
            "freeze_sha256": record["freeze_sha256"], "canonical_attempts": record["canonical_attempts"],
            "raw_filename": campaign.RAW.name, "raw_sha256": digest_bytes(raw),
            "record_sha256": digest(record), "uncompressed_sha256": digest_bytes(plaintext)}


def precompletion(record):
    if record.get("status") != "COMPLETED" or type(record.get("canonical_attempts")) is not int or record["canonical_attempts"] != 1:
        raise ValueError("Only an already completed single attempt can be finalized")
    return {**record, "status": "STARTED"}


def validate(original, current, receipt, raw, verdict):
    plaintext = gzip.decompress(raw)
    record = json.loads(plaintext)
    prior = precompletion(record)
    if (original["status"] != "STARTED" or original["record_sha256"] != digest(prior)
            or original["uncompressed_sha256"] != digest_bytes(encoded(prior))
            or any(original[key] != current[key] for key in ("schema", "freeze_sha256", "canonical_attempts", "raw_filename"))
            or current != index_for(record, raw, plaintext)):
        raise ValueError("Finalization changed more than transport metadata or lacks the exact prior checkpoint")
    if (receipt["schema"] != "mira-genesis-v31-metadata-finalization-v1"
            or receipt["original_index_sha256"] != digest_bytes(original_bytes())
            or receipt["final_index_sha256"] != digest_bytes(campaign.ATTEMPT.read_bytes())
            or receipt["unchanged_raw_sha256"] != digest_bytes(raw)
            or receipt["unchanged_verdict_sha256"] != digest_bytes(verdict)
            or receipt["candidate_evaluations_rerun"] != 0 or receipt["scientific_inputs_changed"] is not False
            or receipt["payload_delta"] != "NONE; only completion-index metadata finalized"):
        raise ValueError("Altered finalization provenance or scientific evidence")
    commit = receipt["original_evidence_commit"]
    paths = (campaign.ATTEMPT, campaign.RAW, campaign.VERDICT)
    expected = (original_bytes(), raw, verdict)
    for path, data in zip(paths, expected):
        if freeze.git("show", commit + ":" + path.relative_to(freeze.ROOT).as_posix()) != data:
            raise ValueError("Original pre-finalization evidence was not preserved byte-exact in Git")
    return {"metadata_finalization_verified": True, "original_index_preserved": True,
            "raw_and_verdict_byte_exact": True, "candidate_evaluations_rerun": 0}


def original_bytes():
    return ORIGINAL.read_bytes()


def check():
    return validate(json.loads(original_bytes()), json.loads(campaign.ATTEMPT.read_text()),
                    json.loads(RECEIPT.read_text()), campaign.RAW.read_bytes(), campaign.VERDICT.read_bytes())


def finalize(commit):
    if ORIGINAL.exists() or RECEIPT.exists():
        raise ValueError("Never overwrite original provenance or finalize twice")
    freeze.verify(json.loads(freeze.PATH.read_text()))
    before = campaign.ATTEMPT.read_bytes()
    raw, verdict = campaign.RAW.read_bytes(), campaign.VERDICT.read_bytes()
    for path, data in ((campaign.ATTEMPT, before), (campaign.RAW, raw), (campaign.VERDICT, verdict)):
        if freeze.git("show", commit + ":" + path.relative_to(freeze.ROOT).as_posix()) != data:
            raise ValueError("Commit the original transport mismatch before finalization")
    record = json.loads(gzip.decompress(raw))
    prior = precompletion(record)
    # Reconstruct the final STARTED checkpoint exactly, including its gzip hash.
    stream = io.BytesIO()
    with gzip.GzipFile(filename=campaign.RAW.name, fileobj=stream, mode="wb", mtime=0) as compressor:
        compressor.write(encoded(prior))
    original = json.loads(before)
    if original != index_for(prior, stream.getvalue(), encoded(prior)):
        raise ValueError("Original index is not exactly the immediately preceding completion checkpoint")
    after_value = index_for(record, raw, gzip.decompress(raw))
    after = (json.dumps(after_value, sort_keys=True, indent=2) + "\n").encode()
    receipt = {"schema": "mira-genesis-v31-metadata-finalization-v1", "original_evidence_commit": commit,
               "original_index_sha256": digest_bytes(before), "final_index_sha256": digest_bytes(after),
               "unchanged_raw_sha256": digest_bytes(raw), "unchanged_verdict_sha256": digest_bytes(verdict),
               "precompletion_gzip_reconstruction_sha256": digest_bytes(stream.getvalue()),
               "reconstruction_zlib_version": zlib.ZLIB_RUNTIME_VERSION,
               "candidate_evaluations_rerun": 0, "scientific_inputs_changed": False,
               "payload_delta": "NONE; only completion-index metadata finalized",
               "observation": "Original raw/adjudication completed; persisted index remained at the last STARTED checkpoint. Root cause not established."}
    with ORIGINAL.open("xb") as copy:
        copy.write(before)
        copy.flush()
        os.fsync(copy.fileno())
    fd, temporary = tempfile.mkstemp(prefix="v31-final-index-", dir=campaign.ATTEMPT.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(after)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, campaign.ATTEMPT)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    with RECEIPT.open("x") as output:
        json.dump(receipt, output, sort_keys=True, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    return check()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize-from-commit")
    args = parser.parse_args()
    print(json.dumps(finalize(args.finalize_from_commit) if args.finalize_from_commit else check(), indent=2))
