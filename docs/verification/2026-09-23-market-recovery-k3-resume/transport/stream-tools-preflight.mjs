import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes, createHash } from 'node:crypto';
import { bootstrap } from './credential-bootstrap.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const out = fs.mkdtempSync(path.join(root, 'stream-tools-preflight-'));
process.env.REVIEW_OUTPUT_DIR = out;
const record = { output: out, complete: false, usable: false, route: 'mirasim-kimi/kimi-k3', attempts: [], timeout_per_request_ms: 180000, retries: 0 };
const save = () => fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify(record, null, 2) + '\n');
const started = Date.now();
save();
console.log(JSON.stringify({ output: out }));
try {
  let provider;
  const hooks = new Map();
  bootstrap({ registerProvider: (_name, value) => { provider = value; }, on: (name, handler) => hooks.set(name, handler) });
  const challenge = randomBytes(12).toString('hex');
  const tools = [{ type: 'function', function: { name: 'read_probe', description: 'Return the locally computed digest for the supplied challenge.', parameters: { type: 'object', properties: { challenge: { type: 'string' } }, required: ['challenge'], additionalProperties: false } } }];
  const messages = [{ role: 'system', content: 'This is a tool transport check, not a code review. First call read_probe exactly once. After its result reply with the returned digest only.' }, { role: 'user', content: 'Call read_probe with challenge ' + challenge + ', then return its digest.' }];
  for (let step = 0; step < 2; step++) {
    const item = { step: step + 1, started_at: new Date().toISOString(), has_temperature: false, stream: true, tool_count: tools.length, reasoning_effort: 'xhigh' };
    record.attempts.push(item);
    const payload = { model: 'kimi-k3', messages, tools, max_tokens: 16384, reasoning_effort: 'xhigh', stream: true, stream_options: { include_usage: true } };
    hooks.get('before_provider_request')({ payload }, { model: { provider: 'mirasim-kimi', id: 'kimi-k3' } });
    save();
    const at = Date.now();
    const response = await fetch(provider.baseUrl + '/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + provider.apiKey }, body: JSON.stringify(payload), signal: AbortSignal.timeout(180000) });
    item.http_status = response.status;
    item.headers_ms = Date.now() - at;
    save();
    if (!response.ok) { item.error_body_sha256 = createHash('sha256').update(await response.text()).digest('hex'); throw new Error('HTTP_' + response.status); }
    let pending = '', content = '', reasoning = '';
    const calls = new Map();
    const decoder = new TextDecoder();
    for await (const chunk of response.body) {
      if (item.first_data_ms === undefined) { item.first_data_ms = Date.now() - at; save(); }
      pending += decoder.decode(chunk, { stream: true });
      let pos;
      while ((pos = pending.indexOf('\n')) >= 0) {
        const line = pending.slice(0, pos).trim(); pending = pending.slice(pos + 1);
        if (!line.startsWith('data:') || line === 'data: [DONE]') continue;
        const data = JSON.parse(line.slice(5).trim());
        if (data.error) throw new Error('STREAM_ERROR');
        if (data.usage) item.usage = data.usage;
        for (const choice of data.choices || []) {
          if (choice.finish_reason) item.finish_reason = choice.finish_reason;
          content += choice.delta?.content || '';
          reasoning += choice.delta?.reasoning_content || '';
          for (const part of choice.delta?.tool_calls || []) {
            const call = calls.get(part.index) || { id: '', type: 'function', function: { name: '', arguments: '' } };
            if (part.id) call.id = part.id;
            call.function.name += part.function?.name || '';
            call.function.arguments += part.function?.arguments || '';
            calls.set(part.index, call);
          }
        }
      }
    }
    item.elapsed_ms = Date.now() - at;
    item.tool_calls = calls.size;
    item.text_length = content.length;
    save();
    if (step === 0) {
      if (calls.size !== 1) throw new Error('EXPECTED_ONE_TOOL_CALL');
      const call = [...calls.values()][0];
      if (call.function.name !== 'read_probe' || JSON.parse(call.function.arguments).challenge !== challenge) throw new Error('INVALID_TOOL_CALL');
      const digest = createHash('sha256').update(challenge).digest('hex');
      messages.push({ role: 'assistant', content: content || null, reasoning_content: reasoning, tool_calls: [call] });
      messages.push({ role: 'tool', tool_call_id: call.id, name: 'read_probe', content: JSON.stringify({ digest }) });
      record.tool_executed = true;
      record.expected_digest = digest;
    } else {
      record.final_digest_matches = content.trim() === record.expected_digest;
      record.usable = record.tool_executed && record.final_digest_matches && calls.size === 0;
    }
    save();
  }
} catch (error) {
  record.error_type = error.name;
  record.error_code = /^HTTP_\d+$|^STREAM_ERROR$|^EXPECTED_ONE_TOOL_CALL$|^INVALID_TOOL_CALL$/.test(error.message) ? error.message : null;
} finally {
  record.complete = true;
  record.elapsed_ms = Date.now() - started;
  save();
}
console.log(JSON.stringify(record));
process.exitCode = record.usable ? 0 : 2;
