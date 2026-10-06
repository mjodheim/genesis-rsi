const fs = require('fs')
const path = require('path')
const vm = require('vm')
const ts = require('/home/anthony/experiments/a6v2-c015/node_modules/typescript')

const workspace = process.argv[2]
if (!workspace) process.exit(2)
const sourcePath = path.join(workspace, 'lib/DateTimeUtils.ts')
const source = fs.readFileSync(sourcePath, 'utf8')
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText

const sandbox = {
  exports: {},
  module: { exports: {} },
  require,
  console,
  Date,
  isNaN,
}
sandbox.exports = sandbox.module.exports
vm.runInNewContext(transpiled, sandbox, { filename: sourcePath, timeout: 1000 })
const DateTimeUtils = sandbox.module.exports.DateTimeUtils || sandbox.exports.DateTimeUtils

const cases = [
  ['01000000', 0, '00:00:00'],
  ['01123045', 45045, '12:30:45'],
  ['15100000', 1245600, 'YYYY-MM-15T10:00:00'],
  ['31100000', 2628000, 'YYYY-MM-31T10:00:00'],
]

const results = cases.map(([input, expectedSeconds, expectedRendered]) => {
  const seconds = DateTimeUtils.convertDayTimeToTod(input)
  const rendered = DateTimeUtils.timestampToString(seconds)
  return {
    input,
    expectedSeconds,
    seconds,
    expectedRendered,
    rendered,
    ok: seconds === expectedSeconds && rendered === expectedRendered,
  }
})

const payload = {
  schema: 'mira-genesis-a6-task011-evaluator-v1',
  objective_ok: results.every((item) => item.ok),
  results,
  external_model_calls: 0,
}
console.log(JSON.stringify(payload))
process.exit(payload.objective_ok ? 0 : 1)
