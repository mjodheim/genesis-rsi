import path from 'node:path'
import { createRequire } from 'node:module'

const root = process.argv[2]
if (!root) process.exit(2)
const require = createRequire(import.meta.url)
const mod = require(path.join(root, 'utils.js'))

const cases = [
  ['hello', 3, 'hel'],
  ['abcdef', 1, 'a'],
  ['abcdef', 6, 'abcdef'],
  ['', 0, ''],
]

const results = cases.map(([value, maxLen, expected]) => {
  const actual = mod.truncate(value, maxLen)
  return { value, maxLen, expected, actual, ok: actual === expected }
})
const objective_ok = results.every(x => x.ok)
console.log(JSON.stringify({schema:'mira-genesis-a6-task002-evaluator-v1', objective_ok, results, external_model_calls:0}))
process.exit(objective_ok ? 0 : 1)
