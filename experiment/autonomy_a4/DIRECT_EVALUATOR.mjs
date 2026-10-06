import fs from 'node:fs'
import vm from 'node:vm'

const sourcePath = process.argv[2]
if (!sourcePath) {
  console.error('GridState source path required')
  process.exit(2)
}

let source = fs.readFileSync(sourcePath, 'utf8')
source = source
  .replace(/^import\s+cloneDeep\s+from\s+["']lodash\/cloneDeep["'];?\s*$/m, '')
  .replace('export default class GridState', 'class GridState')
source += '\n;globalThis.__GenesisGridState = GridState;\n'

const context = {
  cloneDeep: (value) => JSON.parse(JSON.stringify(value)),
  console,
}
vm.createContext(context)

try {
  vm.runInContext(source, context, { filename: sourcePath, timeout: 1000 })
} catch (error) {
  console.log(JSON.stringify({
    parse_or_load_ok: false,
    error: String(error?.stack || error),
    objective_ok: false,
    regression_ok: false,
    overall_ok: false,
  }))
  process.exit(1)
}

const GridState = context.__GenesisGridState
const checks = []

function record(name, actual, expected) {
  const actualJson = JSON.stringify(actual)
  const expectedJson = JSON.stringify(expected)
  checks.push({ name, actual, expected, ok: actualJson === expectedJson })
}

const grid = new GridState(4, 3)
grid.gridArray = [
  [11, 12, 13, 14],
  [21, 22, 23, 24],
  [31, 32, 33, 34],
]

record('objective-column-1', grid.getColumn(1), [11, 21, 31])
record('objective-column-4', grid.getColumn(4), [14, 24, 34])
record('regression-row-1', grid.getRow(1), [11, 12, 13, 14])
record('regression-square-2-2', grid.getSquareVal(2, 2), 22)
record('regression-coordinate-low', grid.coordinateExists(0, 1), false)
record('regression-coordinate-high', grid.coordinateExists(5, 1), false)
record('regression-coordinate-valid', grid.coordinateExists(4, 3), true)

grid.setSquareVal(2, 2, 99)
record('regression-set-square', grid.getSquareVal(2, 2), 99)

const grid3 = new GridState(3, 3)
const visible = [
  ['a', 'b', 'c'],
  ['d', 'e', 'f'],
  ['g', 'h', 'i'],
]
grid3.setGridData(visible)
record('regression-grid-roundtrip', grid3.getGridData(), visible)

const objectiveChecks = checks.filter((item) => item.name.startsWith('objective-'))
const regressionChecks = checks.filter((item) => item.name.startsWith('regression-'))
const objectiveOk = objectiveChecks.every((item) => item.ok)
const regressionOk = regressionChecks.every((item) => item.ok)
const output = {
  parse_or_load_ok: true,
  objective_ok: objectiveOk,
  regression_ok: regressionOk,
  overall_ok: objectiveOk && regressionOk,
  checks,
}
console.log(JSON.stringify(output))
process.exit(output.overall_ok ? 0 : 1)
