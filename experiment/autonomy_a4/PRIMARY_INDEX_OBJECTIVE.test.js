import GridState from './GridState.js'

test('getColumn uses the public one-based x coordinate', () => {
  const grid = new GridState(4, 3)
  grid.gridArray = [
    [11, 12, 13, 14],
    [21, 22, 23, 24],
    [31, 32, 33, 34],
  ]

  expect(grid.getColumn(1)).toEqual([11, 21, 31])
  expect(grid.getColumn(4)).toEqual([14, 24, 34])
})
