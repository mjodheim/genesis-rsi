const fs = require('fs')
const os = require('os')
const path = require('path')
const crypto = require('crypto')
const { execFileSync } = require('child_process')

const workspace = path.resolve(process.argv[2])
if (!workspace) process.exit(2)

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'genesis-a6-t12-'))
const repoDir = path.join(root, 'repo')
const claudeRoot = path.join(root, 'claude')
const projectDir = path.join(claudeRoot, 'project')
const piEmpty = path.join(root, 'pi-empty')
const extraEmpty = path.join(root, 'extra-empty')
fs.mkdirSync(repoDir)
fs.mkdirSync(claudeRoot)
fs.mkdirSync(projectDir)
fs.mkdirSync(piEmpty)
fs.mkdirSync(extraEmpty)

function git(args, env = {}) {
  return execFileSync('git', args, {
    cwd: repoDir,
    env: { ...process.env, ...env },
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim()
}

function commitAt(iso, file, message) {
  fs.writeFileSync(path.join(repoDir, file), message + '\n')
  git(['add', '.'])
  git(['commit', '-m', message], {
    GIT_AUTHOR_DATE: iso,
    GIT_COMMITTER_DATE: iso,
  })
  return git(['rev-parse', 'HEAD'])
}

try {
  git(['init'])
  git(['config', 'user.email', 'genesis@example.invalid'])
  git(['config', 'user.name', 'Genesis Evaluator'])

  const oldest = commitAt('2026-10-05T10:00:00Z', 'oldest.txt', 'oldest')
  const middle = commitAt('2026-10-05T11:00:00Z', 'middle.txt', 'middle')
  const newest = commitAt('2026-10-05T12:00:00Z', 'newest.txt', 'newest')

  const sessionId = crypto.randomUUID()
  const sessionFile = path.join(projectDir, sessionId + '.jsonl')
  fs.writeFileSync(sessionFile, JSON.stringify({
    type: 'assistant',
    message: {
      model: 'claude-sonnet-5',
      usage: { input_tokens: 100, output_tokens: 50 },
    },
    timestamp: '2026-10-05T11:30:00Z',
  }) + '\n')

  process.env.CLAUDE_PROJECTS_DIR = claudeRoot
  process.env.PI_SESSION_DIRS = piEmpty
  process.env.EXTRA_SESSION_DIRS = extraEmpty

  const modulePath = path.join(workspace, 'lib', 'git-blame.js')
  delete require.cache[require.resolve(modulePath)]
  const gitBlame = require(modulePath)

  const report = gitBlame.generateGitBlameReport(30, repoDir)
  const attributed = report.find((item) => item.tokens > 0) || null

  const newestDetails = gitBlame.getCommitSessionDetails(newest, repoDir, 30)
  const middleDetails = gitBlame.getCommitSessionDetails(middle, repoDir, 30)
  const fileCosts = gitBlame.getCostByFile(30, repoDir)
  const newestFileCost = fileCosts.find((item) => item.file === 'newest.txt') || null
  const middleFileCost = fileCosts.find((item) => item.file === 'middle.txt') || null

  const checks = {
    report_attributes_to_newest:
      !!attributed && newest.startsWith(attributed.hash) && attributed.tokens === 150,
    newest_details_include_session:
      !!newestDetails && newestDetails.summary.totalTokens === 150 && newestDetails.sessions.length === 1,
    middle_details_exclude_session:
      !!middleDetails && middleDetails.summary.totalTokens === 0 && middleDetails.sessions.length === 0,
    file_cost_attributes_to_newest:
      !!newestFileCost && newestFileCost.cost > 0 && !middleFileCost,
  }

  const payload = {
    schema: 'mira-genesis-a6-task012-evaluator-v1',
    objective_ok: Object.values(checks).every(Boolean),
    checks,
    hashes: { oldest, middle, newest },
    attributed_hash: attributed?.hash ?? null,
    report: report.map((item) => ({ hash: item.hash, tokens: item.tokens, files: item.files })),
    file_costs: fileCosts,
    external_model_calls: 0,
  }
  console.log(JSON.stringify(payload))
  process.exit(payload.objective_ok ? 0 : 1)
} finally {
  fs.rmSync(root, { recursive: true, force: true })
}
