import fs from 'node:fs';
import path from 'node:path';

const names = payload => (payload.tools || []).map(t => t.function?.name).sort();
const same = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());
const text = content => content.filter(c => c.type === 'text').map(c => c.text).join('');
const save = (out, name, data) => fs.writeFileSync(path.join(out, name), JSON.stringify(data, null, 2) + '\n');

// Check the actual CLI allowlist before any provider request, not just registration.
export function installStageGuard(pi, { out, stage, tools, terminate = code => process.exit(code) }) {
  let failed = false;
  pi.on('session_start', () => {
    const actual = pi.getActiveTools();
    const expected = tools[stage];
    const ok = Array.isArray(expected) && same(actual, expected);
    save(out, 'tool-menu.json', { stage, expected, actual, status: ok ? 'PASS' : 'BLOCKED_TOOL_MENU' });
    if (!ok) {
      failed = true;
      terminate(75);
      throw new Error('CLI tool allowlist mismatch');
    }
  });
  pi.on('message_end', event => {
    if (event.message.role !== 'assistant') return;
    const calls = event.message.content.filter(c => c.type === 'toolCall');
    if (calls.some(c => c.name === 'deliver_stage') && calls.length !== 1) {
      failed = true;
      save(out, 'delivery-blocked.json', { reason: 'delivery_must_be_standalone' });
    }
  });
  pi.on('tool_call', event => {
    if (failed || !tools[stage]?.includes(event.toolName)) {
      return { block: true, terminate: true, reason: 'Tool menu or standalone delivery violation.' };
    }
  });
}

// A successful tool result advances the menu for the NEXT provider response only.
export function installGateway(pi, { out, tree, terminate = code => process.exit(code) }) {
  const fixture = path.resolve(out, '../work/gateway-fixture.txt');
  const echo = path.resolve(out, '../work/gateway-echo.txt');
  let phase = 'read';
  let issuedPhase;
  let expected;
  let callId;
  let consumed = false;
  let requests = 0;
  const history = [];
  const record = (event, reason) => {
    history.push({ event, phase, request: requests, ...(reason ? { reason } : {}) });
    save(out, 'gateway-state.json', { phase, requests, history });
  };
  const fail = reason => {
    phase = 'failed';
    pi.setActiveTools([]);
    record('blocked', reason);
    return { block: true, terminate: true, reason };
  };
  pi.on('session_start', () => {
    if (fs.existsSync(echo)) {
      fail('echo_already_exists');
      terminate(75);
      throw new Error('gateway requires a fresh echo path');
    }
    pi.setActiveTools(['read']);
    record('start');
  });
  pi.on('before_provider_request', event => {
    if (['failed', 'complete'].includes(phase) || requests >= 3 || issuedPhase === phase) {
      fail('request_out_of_sequence');
      terminate(75);
      throw new Error('gateway admission denied');
    }
    const allowed = phase === 'final' ? [] : [phase];
    if (!same(names(event.payload), allowed)) {
      fail('provider_tool_menu_mismatch');
      terminate(75);
      throw new Error('gateway tool menu mismatch');
    }
    requests++;
    issuedPhase = phase;
    consumed = false;
    callId = undefined;
    record('request');
    return {
      ...event.payload,
      parallel_tool_calls: false,
      tool_choice: phase === 'final' ? 'none' : { type: 'function', function: { name: phase } },
    };
  });
  pi.on('message_end', event => {
    const m = event.message;
    if (m.role !== 'assistant' || phase === 'failed') return;
    const calls = m.content.filter(c => c.type === 'toolCall');
    if (!['stop', 'toolUse'].includes(m.stopReason)) {
      fail('incomplete_assistant_response');
    } else if (issuedPhase === 'final' && phase === 'final') {
      if (calls.length || text(m.content).trimEnd() !== expected.trimEnd()) {
        fail('final_echo_mismatch');
      } else {
        phase = 'complete';
        record('complete');
      }
    } else if (phase !== issuedPhase || calls.length !== 1 || calls[0].name !== issuedPhase) {
      fail('one_expected_tool_per_response_required');
    } else {
      callId = calls[0].id;
    }
  });
  pi.on('tool_call', event => {
    if (phase === 'failed') return { block: true, terminate: true, reason: 'Gateway already failed.' };
    if (consumed || event.toolCallId !== callId || event.toolName !== issuedPhase || phase !== issuedPhase) {
      return fail('tool_not_admitted_in_this_response');
    }
    const params = event.input;
    const target = typeof params.path === 'string' ? path.resolve(tree, params.path.replace(/^@/, '')) : '';
    if (phase === 'read') {
      if (target !== fixture || (params.offset ?? 1) !== 1 || (params.limit ?? 1) !== 1) {
        return fail('fixture_read_required');
      }
    } else if (phase === 'write') {
      if (target !== echo || params.content !== expected || fs.existsSync(echo)) {
        return fail('exact_copy_to_fresh_echo_required');
      }
    } else {
      return fail('tool_after_write');
    }
    consumed = true;
  });
  pi.on('tool_result', event => {
    if (phase === 'failed') return;
    if (!consumed || event.toolCallId !== callId || event.toolName !== issuedPhase || event.isError) {
      fail('tool_result_failed_or_unmatched');
      return;
    }
    try {
      if (phase === 'read') {
        expected = text(event.content);
        if (!expected || expected !== fs.readFileSync(fixture, 'utf8')) {
          fail('read_result_mismatch');
          return;
        }
        phase = 'write';
        pi.setActiveTools(['write']);
      } else if (phase === 'write') {
        if (fs.readFileSync(echo, 'utf8') !== expected) {
          fail('written_copy_mismatch');
          return;
        }
        phase = 'final';
        pi.setActiveTools([]);
      } else {
        fail('unexpected_tool_result');
        return;
      }
      record('tool_result');
    } catch {
      fail('fixture_or_echo_unreadable');
    }
  });
}
