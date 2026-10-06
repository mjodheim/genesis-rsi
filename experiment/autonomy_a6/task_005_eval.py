from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

VITEST = "/home/anthony/a6-tooling-vitest/node_modules/.bin/vitest"

TEST_SOURCE = r"""vi.mock('../../shared/azure-client.js', () => ({
  azureChatComplete: vi.fn(async () => JSON.stringify({
    extracted_verdicts: [{
      index: 0,
      verdict: 'matches_gold',
      matched_gold_index: 4,
      type_correct: true,
      reason: 'the matched_gold_index is corrected to the actual gold atom index 3',
    }],
    unmatched_gold_indices: [0, 1, 2, 3],
  })),
}))

import { judgeFixture } from './judge.js'

test('out-of-range confirmed match is recovered instead of silently becoming a recall miss', async () => {
  const cfg = {
    endpoint: 'http://unused.invalid',
    apiVersion: 'test',
    answererDeployment: 'test',
    key: 'unused',
  }
  const gold = [
    { type: 'fact', text: 'g0' },
    { type: 'fact', text: 'g1' },
    { type: 'fact', text: 'g2' },
    { type: 'fact', text: 'g3' },
  ]
  const extracted = [{ type: 'fact', text: 'matched g3' }]
  const score = await judgeFixture(cfg, 'fx-a6', gold, extracted, 'low')

  expect(score.recall).toBe(0.25)
  expect(score.judge.unmatched_gold_indices).not.toContain(3)
  const match = score.judge.extracted_verdicts.find(v => v.verdict === 'matches_gold')
  expect(match).toBeTruthy()
  expect(match.matched_gold_index).toBe(3)
})
"""


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    test_path = root / "scripts/eval/extraction-bench/lib/__genesis_a6_task005.test.ts"
    test_path.write_text(TEST_SOURCE, encoding="utf-8")
    proc = subprocess.run(
        [
            VITEST,
            "run",
            str(test_path.relative_to(root)),
            "--root",
            str(root),
            "--globals",
            "--reporter=basic",
        ],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=False,
    )
    result = {
        "schema": "mira-genesis-a6-task005-evaluator-v1",
        "objective_ok": proc.returncode == 0,
        "exit_code": int(proc.returncode),
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "external_model_calls": 0,
    }
    print(json.dumps(result))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
