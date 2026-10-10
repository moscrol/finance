"""Evaluation-only tool bridge and audited model transport for the Pi-native finance arm.

派生自 2026-10-09 同模型对照用的 ``eval-kit/pi_bridge.py``。``/configure`` 直接从载荷取截止日、
tier 与日期，不依赖产品臂的 episode。模型只收到公开证据、范围、缺口和领域状态；完整审计单独落盘，
尤其不能把 ``temporal_withheld`` 中的未来材料再次发给模型。共享注册表、绝对截止、调用帽、脱敏传输
和模型身份核对保持。这是验证入口，不改产品文件、不写记忆。

环境变量：
- ``FINANCE_PI_ROOT``          产物根目录（请求/响应/工具日志都落在这里）
- ``WORKBENCH_REPO_ROOT``      被验证的代码树（工具注册表从这里加载）
- ``FINANCE_PI_RAG_BINDINGS``  受管 RAG 代际绑定 JSON；``off`` 时跳过代际核对（只用于离线自测）
- ``FINANCE_PI_BRIDGE_PORT``   监听端口，默认 18886
- ``LLM_*`` / ``FORESIGHT_BUILTIN_LLM_*``  由 runner 注入，``llm_refine.detect_provider`` 读取
"""
import dataclasses
from datetime import date
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping

ROOT = Path(os.environ['FINANCE_PI_ROOT'])
CODE = Path(os.environ['WORKBENCH_REPO_ROOT'])
PORT = int(os.environ.get('FINANCE_PI_BRIDGE_PORT', '18886'))
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_binding import initialize, effective  # noqa: E402

_RAG_BINDINGS = os.environ.get('FINANCE_PI_RAG_BINDINGS', '')
if _RAG_BINDINGS and _RAG_BINDINGS != 'off':
    RAG_CFG = initialize(_RAG_BINDINGS, CODE)
    RAG_EFFECTIVE = effective(RAG_CFG)
else:
    os.environ.setdefault('PYTHONPATH', str(CODE))
    RAG_EFFECTIVE = {'binding': 'off'}

from intelligence.services import llm_refine  # noqa: E402
from intelligence.services.episode_factory import DEFAULT_RESEARCH_CAPABILITIES, build_episode_context  # noqa: E402
from intelligence.services.episode_tools import build_episode_registry  # noqa: E402
from intelligence.services.research_contract import InformationCutoff  # noqa: E402
from intelligence.services.task_frame import TaskFrame  # noqa: E402
from intelligence.paths import default_paths  # noqa: E402
from model_view import model_observation  # noqa: E402


def safe(x):
    if dataclasses.is_dataclass(x):
        return {f.name: safe(getattr(x, f.name)) for f in dataclasses.fields(x)}
    if isinstance(x, Mapping):
        return {str(k): safe(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [safe(v) for v in x]
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if hasattr(x, 'to_dict'):
        return safe(x.to_dict())
    return str(x)


provider = llm_refine.detect_provider()
EXPECTED_MODEL = os.environ.get('FINANCE_PI_MODEL') or (provider.model if provider else '')
if provider is None or provider.model != EXPECTED_MODEL:
    raise RuntimeError('model admission failed')
lock = threading.Lock()
tool_lock = threading.Lock()
state: dict = {}


def log(name, row):
    with (ROOT / name).open('a') as f:
        f.write(json.dumps(safe(row), ensure_ascii=False) + '\n')


def configure(payload):
    """Freeze one research run contract from the request payload alone.

    The thin Pi arm owns interpretation and expression. It receives the shared tool
    schemas and the information cutoff, not any product-derived output contract.
    """
    global state
    if state:
        raise RuntimeError('bridge is already configured; research permissions cannot be reset')
    mode = payload.get('mode', 'research')
    if mode not in ('research', 'delivery'):
        raise ValueError('unknown Pi run mode')
    question = payload['question']
    as_of = payload['expected_as_of']
    tier = payload.get('research_tier', 'max')
    frame = TaskFrame(
        raw_question=question, question_type='general_finance_qa', user_goal=question,
        subject=None, subject_kind='unknown', market_scope='A股', confidence=0.0,
        required_outputs=('direct_assessment', 'evidence_boundary'), required_output_additions=(),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy='general_finance_evidence', timeframe=as_of,
        material_contract=None, conversation_materials=None, history_intent=None,
    )
    cut = InformationCutoff(date.fromisoformat(as_of), 'requested')
    batch_deadline = float(payload['absolute_deadline_epoch'])
    remaining = batch_deadline - time.time()
    if remaining <= 0:
        raise RuntimeError('batch deadline already expired')
    ctx = build_episode_context(
        frame, task_id='pi-native:' + payload['case'],
        capabilities=DEFAULT_RESEARCH_CAPABILITIES, tier=tier,
        timeout=min(600.0, remaining), synthesis_reserve=min(48.0, remaining / 4),
        today=payload.get('today') or date.today().isoformat(),
        latest_data_date=payload.get('latest_data_date') or as_of,
        information_cutoff=cut,
    )
    registry = None
    if mode == 'research':
        paths = default_paths()
        registry = build_episode_registry(
            frame, ctx, finance_root=paths.finance_root, knowledge_wiki=paths.knowledge_wiki,
            memory_user=payload['user'], memory_users_root=Path(payload['users_root']) / payload['user'],
        )
    state = {
        'case': payload['case'], 'context': ctx, 'registry': registry, 'data_tools_enabled': mode == 'research',
        'expires': min(batch_deadline, time.time() + min(600, ctx.policy.total_seconds)),
        'calls': 0, 'tool_calls': 0,
        'call_cap': int(payload.get('call_cap') or (120 if ctx.contract.research_tier == 'max' else 40)),
        'tool_cap': int(payload.get('tool_cap', 60)) if mode == 'research' else 0,
    }
    specs = registry.authorized_specs(ctx.contract.allowed_capabilities) if registry is not None else ()
    return {
        'case': payload['case'], 'as_of': safe(ctx.information_cutoff),
        'research_tier': ctx.contract.research_tier,
        'authorized_tools': [{'name': s.name, 'description': s.description,
                              'contract': s.contract, 'parameters': safe(s.parameters)} for s in specs],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    @staticmethod
    def redact_body(body, key, *, truncated=False):
        if not key:
            return body
        body = body.replace(key, b'[REDACTED]')
        if truncated:
            # The bounded read can end inside an echoed key. Remove the longest
            # known prefix at that boundary before limiting the file.
            for length in range(min(len(key) - 1, len(body)), 0, -1):
                if body.endswith(key[:length]):
                    body = body[:-length] + b'[REDACTED]'
                    break
        return body

    def reply(self, code, obj):
        data = json.dumps(safe(obj), ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/health':
            self.reply(200, {'case': state.get('case'), 'calls': state.get('calls', 0),
                             'tool_calls': state.get('tool_calls', 0), 'model': EXPECTED_MODEL,
                             'data_tools_enabled': state.get('data_tools_enabled', False)})
            return
        self.reply(404, {'error': 'unknown evaluation route'})

    def do_POST(self):
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
            if self.path == '/configure':
                with lock:
                    out = configure(payload)
                self.reply(200, out)
                return
            if self.path == '/tool':
                with lock:
                    if not state.get('data_tools_enabled', False):
                        self.reply(403, {'error': 'data_tools_disabled', 'detail': 'frozen-evidence delivery cannot retrieve new data'})
                        return
                    if time.time() >= state['expires'] or state['tool_calls'] >= state['tool_cap']:
                        raise RuntimeError('Pi absolute tool budget exhausted')
                    state['tool_calls'] += 1
                    index = state['tool_calls']
                with tool_lock:
                    started = time.monotonic()
                    # Tool-internal author/judge calls pass through the same transport
                    # reservation; no per-tool reset of the root cap.
                    proxy = dataclasses.replace(provider, base_url='http://127.0.0.1:%d/case/%s/v1' % (PORT, state['case']),
                                                api_key='evaluation-local')
                    with llm_refine.provider_override(proxy):
                        obs = state['registry'].execute(payload['tool'], payload.get('args', {}),
                                                        context=state['context'], step_id=f'pi-{index}')
                    facing = safe(model_observation(obs))
                    log('pi-tools.jsonl', {
                        'case': state['case'], 'tool': payload['tool'], 'arguments': payload.get('args', {}),
                        'seconds': time.monotonic() - started, 'observation': safe(obs),
                        'model_observation': facing,
                    })
                self.reply(200, {'tool': payload['tool'], 'arguments': payload.get('args', {}),
                                 'observation': facing})
                return
            if self.path == '/v1/chat/completions' or self.path.startswith('/case/'):
                with lock:
                    requested_case = (self.path.split('/')[2] if self.path.startswith('/case/')
                                      else self.headers.get('X-Eval-Case'))
                    if requested_case != state.get('case'):
                        raise RuntimeError('stale or mismatched evaluation case identity')
                    if time.time() >= state.get('expires', 0) or state.get('calls', 120) >= state.get('call_cap', 40):
                        raise RuntimeError('Pi absolute model budget exhausted')
                    if payload.get('model') != provider.model:
                        raise RuntimeError('requested model mismatch')
                    state['calls'] += 1
                    index = state['calls']
                    case = state['case']
                    expires = state['expires']
                    timeout = expires - time.time()
                    if timeout <= 0:
                        raise RuntimeError('Pi absolute model deadline before transport')
                llm_refine._apply_agent_turn_max_tokens(payload, model=provider.model)
                llm_refine._apply_thinking_controls(payload, disable_thinking=True)
                payload['temperature'] = 0.0
                llm_refine._apply_compat_payload(payload, model=provider.model)
                # Enforce the native Pi compatibility declaration after shared helpers,
                # which may insert effort from the production environment.
                for unsupported in ('reasoning_effort', 'store', 'max_completion_tokens'):
                    payload.pop(unsupported, None)
                for message in payload.get('messages', []):
                    content = message.get('content')
                    if isinstance(content, list) and all(
                        part.get('type') == 'text' and isinstance(part.get('text'), str) for part in content
                    ):
                        message['content'] = '\n'.join(part['text'] for part in content)
                log('pi-model-requests.jsonl', {'case': case, 'index': index, 'payload': payload})
                request = urllib.request.Request(provider.base_url.rstrip('/') + '/chat/completions',
                                                 data=json.dumps(payload).encode(),
                                                 headers=llm_refine._llm_request_headers(provider))
                started = time.monotonic()
                models, usage, raw, error_body_read = [], [], [], {}
                try:
                    with urllib.request.urlopen(request, timeout=timeout) as response:
                        content_type = response.headers.get('Content-Type', 'application/json')
                        self.send_response(response.status)
                        self.send_header('Content-Type', content_type)
                        self.send_header('Connection', 'close')
                        self.end_headers()
                        self.close_connection = True
                        if 'event-stream' in content_type:
                            for line in response:
                                if time.time() >= expires:
                                    raise TimeoutError('absolute Pi model deadline')
                                self.wfile.write(line)
                                self.wfile.flush()
                                raw.append(line)
                                if line.startswith(b'data:'):
                                    try:
                                        item = json.loads(line[5:].strip())
                                    except ValueError:
                                        continue
                                    if item.get('model'):
                                        models.append(item['model'])
                                    if item.get('usage'):
                                        usage.append(item['usage'])
                        else:
                            body = response.read()
                            self.wfile.write(body)
                            raw.append(body)
                            item = json.loads(body)
                            if item.get('model'):
                                models.append(item['model'])
                            if item.get('usage'):
                                usage.append(item['usage'])
                except urllib.error.HTTPError as error:
                    read_limit = 1024 * 1024
                    error_body = error.read(read_limit + 1)
                    error_body_read = {'truncated': len(error_body) > read_limit,
                                       'read_limit': read_limit, 'read_bytes': len(error_body)}
                    raw.append(error_body)
                    log('pi-http-errors.jsonl', {'case': case, 'index': index, 'status': error.code,
                                                 'response_request_id': error.headers.get('X-Request-ID'),
                                                 **error_body_read})
                    raise
                finally:
                    body = b''.join(raw)
                    # Provider authentication is never copied to evidence artifacts.
                    body = self.redact_body(body, provider.api_key.encode(),
                                            truncated=error_body_read.get('truncated', False))
                    if error_body_read:
                        body = body[:error_body_read['read_limit']]
                    (ROOT / f'pi-{case}-model-{index}.response').write_bytes(body)
                    log('pi-model-responses.jsonl', {
                        'case': case, 'index': index, 'response_models': sorted(set(models)), 'usage': usage,
                        'seconds': time.monotonic() - started, 'bytes': len(body),
                        'sha256': hashlib.sha256(body).hexdigest(),
                        'upstream_endpoint_id': llm_refine.provider_endpoint_id(provider), **error_body_read})
                return
            self.reply(404, {'error': 'unknown evaluation route'})
        except Exception as error:
            message = str(error).replace(provider.api_key, '[REDACTED]')
            log('pi-errors.jsonl', {'type': type(error).__name__, 'message': message, 'case': state.get('case')})
            code = error.code if isinstance(error, urllib.error.HTTPError) else 500
            try:
                self.reply(code, {'error': type(error).__name__, 'detail': message[:1000]})
            except (BrokenPipeError, ConnectionResetError):
                pass


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'pi-provider.json').write_text(json.dumps({
        'expected_model': provider.model, 'endpoint_id': llm_refine.provider_endpoint_id(provider),
        'code_root': str(CODE), 'rag': RAG_EFFECTIVE, 'port': PORT}, indent=2))
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
