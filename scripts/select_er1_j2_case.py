from __future__ import annotations
import hashlib, json
from pathlib import Path

G10 = "ccbc75ac2de8bbf821dc6912b32d2d08fbbf5f284d51775bcedbfd5a2f8d80f2"
DOMAIN = "GENESIS-ER1-J2|"

def main() -> int:
    source = Path("experiment/er1_j1/SELECTION.json")
    j1 = json.loads(source.read_text(encoding="utf-8"))
    attempted = {int(j1["selected_bug_id"])}
    eligible = [int(x) for x in j1["eligible_ids"] if int(x) not in attempted]
    selector = hashlib.sha256((DOMAIN + G10).encode()).hexdigest()
    index = int(selector, 16) % len(eligible)
    payload = {
        "schema": "genesis-er1-j2-selection-v1",
        "project": "Lang",
        "dataset_revision": j1["dataset_revision"],
        "active_bug_list_sha256": j1["active_bug_list_sha256"],
        "g10_chain_result_digest": G10,
        "selector_domain": DOMAIN,
        "selector_sha256": selector,
        "excluded_prior_cases": sorted(attempted),
        "eligible_count": len(eligible),
        "eligible_ids": eligible,
        "selected_index": index,
        "selected_bug_id": eligible[index],
    }
    out = Path("experiment/er1_j2/SELECTION.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
