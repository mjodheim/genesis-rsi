from __future__ import annotations
import hashlib, json
from pathlib import Path

G10="ccbc75ac2de8bbf821dc6912b32d2d08fbbf5f284d51775bcedbfd5a2f8d80f2"
DOMAIN="GENESIS-ER1-J11|"
j10=json.loads(Path("experiment/er1_j10/SELECTION.json").read_text())
attempted={12,20,21,43,46,50,52,54,56,65}
eligible=[int(x) for x in j10["eligible_ids"] if int(x) not in attempted]
selector=hashlib.sha256((DOMAIN+G10).encode()).hexdigest()
index=int(selector,16)%len(eligible)
payload={
  "schema":"genesis-er1-j11-selection-v1",
  "project":"Lang",
  "dataset_revision":j10["dataset_revision"],
  "active_bug_list_sha256":j10["active_bug_list_sha256"],
  "g10_chain_result_digest":G10,
  "selector_domain":DOMAIN,
  "selector_sha256":selector,
  "excluded_prior_cases":sorted(attempted),
  "eligible_count":len(eligible),
  "eligible_ids":eligible,
  "selected_index":index,
  "selected_bug_id":eligible[index],
  "machinery_freeze_commit":"44d062fc778c05ffe7448b923aa3f96e65f783d9",
  "machinery_freeze_tag":"provenance/er2-v2-repair-planner-freeze-20261007"
}
Path("experiment/er1_j11/SELECTION.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
print(json.dumps(payload,indent=2,sort_keys=True))
