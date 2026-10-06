import { pathToFileURL } from 'node:url'
import path from 'node:path'

const root = process.argv[2]
if (!root) {
  console.error('workspace path required')
  process.exit(2)
}

const moduleUrl = pathToFileURL(path.join(root, 'frontend/src/utils/format.js')).href
const { seatsLabel } = await import(moduleUrl)

const cases = [
  {
    name: 'empty-capacity-30',
    input: { seats_left: 30, capacity: 30, rsvp_count: 0 },
    expected: '30 of 30 seats left',
  },
  {
    name: 'single-seat-left',
    input: { seats_left: 1, capacity: 30, rsvp_count: 29 },
    expected: '1 of 30 seats left',
  },
  {
    name: 'full',
    input: { seats_left: 0, capacity: 30, rsvp_count: 30 },
    expected: 'Full',
  },
  {
    name: 'unlimited',
    input: { seats_left: null, capacity: null, rsvp_count: 4 },
    expected: '4 going',
  },
]

let failed = 0
for (const item of cases) {
  const actual = seatsLabel(item.input)
  const ok = actual === item.expected
  console.log(JSON.stringify({ name: item.name, expected: item.expected, actual, ok }))
  if (!ok) failed += 1
}

process.exit(failed === 0 ? 0 : 1)
