import hashlib, pathlib
root=pathlib.Path(__file__).parent/"host_snapshot/brewstead"
manifest=(pathlib.Path(__file__).parent/"host_snapshot/BREWSTEAD_GIT_BLOB_MANIFEST.sha1").read_text().splitlines()
for line in manifest:
    expected,path=line.split("  ",1)
    data=(root/path).read_bytes()
    header=b"blob "+str(len(data)).encode()+bytes([0])
    got=hashlib.sha1(header+data).hexdigest()
    if got != expected:
        raise SystemExit(f"snapshot identity mismatch: {path}: expected {expected}, got {got}")
print(f"verified {len(manifest)} exact Git blobs from frozen Brewstead commit 84f6c246")
