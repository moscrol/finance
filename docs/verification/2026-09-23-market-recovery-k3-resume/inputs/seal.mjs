import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const transport = path.join(path.dirname(root), 'independent-d3abd670');
const probe = path.join(transport, 'stream-tools-preflight-TVG2mG');
const dest = '/Users/a77/fwp-wt-market-recovery-qc-fix-0923/docs/verification/2026-09-23-market-recovery-k3-resume';
const revision = '45e752cfaf30929d15acbd0bcab0a667aef0e12e';
const digest = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const json = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const rows = file => fs.readFileSync(file, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const copy = (from, name) => {
  const to = path.join(dest, name);
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.copyFileSync(from, to, fs.constants.COPYFILE_EXCL);
  assert.equal(digest(from), digest(to));
};
fs.mkdirSync(dest, { recursive: false });
const gateway = json(path.join(probe, 'result.json'));
assert.equal(gateway.complete, true);
assert.equal(gateway.attempts.length, 2);
assert.equal(gateway.attempts[0].http_status, 200);
assert.equal(gateway.attempts[1].http_status, 504);
for (const name of ['result.json', 'request-admissions.jsonl']) copy(path.join(probe, name), 'transport/' + name);
for (const name of ['stream-tools-preflight.mjs', 'credential-bootstrap.mjs', 'provider-template.json']) copy(path.join(transport, name), 'transport/' + name);
const sessions = [];
for (const id of ['01', '01b']) {
  const dir = path.join(root, 'k3-session-' + id);
  const execution = json(path.join(dir, 'execution.json'));
  assert.equal(execution.complete, true);
  assert.equal(execution.revision, revision);
  assert.equal(execution.candidate_untouched, true);
  assert.equal(execution.inputs_unchanged, true);
  assert.equal(execution.admissions_valid, true);
  for (const [name, hash] of Object.entries(execution.sha256)) assert.equal(digest(path.join(dir, name)), hash, name);
  const admissions = rows(path.join(dir, 'request-admissions.jsonl'));
  assert.equal(admissions.length, execution.provider_request_admissions);
  const events = rows(path.join(dir, 'events.jsonl'));
  const audit = events.flatMap(event => {
    if (['session', 'tool_execution_start', 'tool_execution_end', 'turn_start', 'turn_end', 'agent_start', 'agent_settled'].includes(event.type)) {
      if (event.type === 'turn_end') return [{ type: event.type, turnIndex: event.turnIndex }];
      return [event];
    }
    if (event.type === 'message_end' && event.message?.role === 'assistant') {
      const m = event.message;
      return [{ type: 'assistant_end', provider: m.provider, model: m.model, stopReason: m.stopReason,
        errorMessage: m.errorMessage, usage: m.usage, content: (m.content || []).filter(c => c.type !== 'thinking') }];
    }
    return [];
  });
  const assistant = audit.filter(e => e.type === 'assistant_end');
  const calls = audit.filter(e => e.type === 'tool_execution_start');
  const workFiles = fs.readdirSync(path.join(dir, 'work')).filter(n => fs.statSync(path.join(dir, 'work', n)).isFile());
  assert.deepEqual(workFiles, ['preflight-write-check']);
  const result = {
    session: id, requests: admissions.length, http_200: rows(path.join(dir, 'http-responses.jsonl')).filter(e => e.status === 200).length,
    completed_assistant_messages: assistant.length, completed_tool_calls: audit.filter(e => e.type === 'tool_execution_end').length,
    tool_errors: audit.filter(e => e.type === 'tool_execution_end' && e.isError).length,
    model_write_calls: calls.filter(e => e.toolName === 'write').length,
    independent_probe_files: 0, positive_control_executed: false, reviewer_report: false,
    exit_code: execution.exit_code, elapsed_seconds: execution.elapsed_seconds,
    status: execution.model_errors.some(e => e.startsWith('504 ')) ? 'BLOCKED_PROVIDER_504' : 'BLOCKED_SESSION_DEADLINE',
    raw_events_sha256: digest(path.join(dir, 'events.jsonl')),
  };
  assert.equal(result.model_write_calls, 0);
  sessions.push(result);
  for (const name of ['execution.json', 'request-admissions.jsonl', 'http-responses.jsonl', 'preflight.log', 'stderr.log']) copy(path.join(dir, name), 'session-' + id + '/' + name.replace(/\.log$/, '.txt'));
  fs.writeFileSync(path.join(dest, 'session-' + id, 'events-audit.jsonl'), audit.map(e => JSON.stringify(e)).join('\n') + '\n', { flag: 'wx' });
}
for (const name of ['run.py', 'credential-bootstrap.mjs', 'provider-template.json', 'tools.mjs', 'tools-session-01.sb', 'tools.sb', 'source.diff', 'prompt-session-01.md', 'prompt-session-01b.md', 'prompt-session-02.md', 'seal.mjs']) copy(path.join(root, name), 'inputs/' + (name === 'run.py' ? 'run.py.txt' : name));
copy(path.join(root, 'pi-config/settings.json'), 'inputs/pi-settings.json');
const summary = {
  revision, baseline: 'bbd53487f4cefdae97eae90f7322394d36e65462', tree: '3ea686889344ebbaaddeee2b3866bce9bd9a3733',
  status: 'HOLD', controller_summary_not_reviewer_verdict: true,
  route: 'mirasim-kimi/kimi-k3', transport_requests: 2, reviewer_requests: sessions.reduce((n, s) => n + s.requests, 0),
  total_requests: 2 + sessions.reduce((n, s) => n + s.requests, 0),
  total_http_200: 1 + sessions.reduce((n, s) => n + s.http_200, 0), total_http_504: 2,
  independent_probe_count: 0, author_tests_run_this_turn: 0,
  execute_and_report_stages_started: false, prepared_execute_prompt_unused: true,
  claims: { F1: 'not_verified', F2: 'not_verified', F3: 'not_verified' }, sessions,
  caveats: ['HTTP 200 is not completed review', 'Pi exit 0 did not exclude a model HTTP 504 error', 'Last request of session 01b was interrupted; token usage is incomplete', 'No merge, push, deployment, staging, DB swap, or production write'],
};
assert.equal(summary.total_requests, 13);
assert.equal(summary.total_http_200, 11);
fs.writeFileSync(path.join(dest, 'summary.json'), JSON.stringify(summary, null, 2) + '\n', { flag: 'wx' });
const manifest = [];
const walk = dir => {
  for (const name of fs.readdirSync(dir).sort()) {
    const file = path.join(dir, name);
    if (fs.statSync(file).isDirectory()) walk(file);
    else manifest.push({ path: path.relative(dest, file), sha256: digest(file), bytes: fs.statSync(file).size });
  }
};
walk(dest);
fs.writeFileSync(path.join(dest, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ dest, files: manifest.length, summary }, null, 2));
