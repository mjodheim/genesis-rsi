import { pathToFileURL } from 'node:url'
import path from 'node:path'

const workspace = process.argv[2]
if (!workspace) {
  console.error('workspace path required')
  process.exit(2)
}

const url = pathToFileURL(path.join(workspace, 'src/services/excursionService.ts')).href
const { ExcursionService } = await import(url)
const service = new ExcursionService()
const found = service
  .search({ port: 'NAS', date: '2026-08-15' })
  .map((item: { id: string }) => item.id)
  .sort()

console.log(JSON.stringify({ tz: process.env.TZ ?? null, found }))
