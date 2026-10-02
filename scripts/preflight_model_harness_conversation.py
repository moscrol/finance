#!/usr/bin/env python3
"""Offline full-conversation entry probe, never a model-quality/F4 completion run.

Run in a fresh subprocess. Real product routing and stores are used, but every
model transport is stopped before I/O. Socket access and non-read-only-git
subprocesses are denied as a second guard. No real API credential is needed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument('--case-json', required=True, type=Path)
    parser.add_argument('--model', required=True, choices=['glm-5.3-flash', 'glm-5.3'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    data = args.data_root.resolve()
    db = data / 'db/market_feature_store.duckdb'
    if not db.is_file() or db.stat().st_mode & 0o222:
        raise ValueError('preflight requires an existing read-only frozen market database')
    question = json.loads(args.case_json.read_text())['question']
    if not isinstance(question, str) or not question.strip():
        raise ValueError('question missing')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'empty-wiki').mkdir()
    (output / 'empty-index').mkdir()
    for key in list(os.environ):
        if key.endswith('API_KEY') or key.startswith((
            'LLM_JUDGE_', 'LLM_WRITER_', 'WORKBENCH_AUTH_',
            'WORKBENCH_CREDITS_', 'WORKBENCH_QUOTA_',
        )):
            os.environ.pop(key)
    os.environ.update({
        'WORKBENCH_REPO_ROOT': str(root), 'FINANCE_WS': str(data), 'FINANCE_ROOT': str(data),
        'MARKET_FEATURE_STORE_DB': str(db), 'WORKBENCH_KNOWLEDGE_WIKI': str(output / 'empty-wiki'),
        'VECTOR_INDEX_DIR': str(output / 'empty-index'), 'RAG_WORKER_ENABLED': '0',
        'FINANCE_NEWS_FETCH': '0', 'FINANCE_WEB_SEARCH': '0', 'FORESIGHT_LLM_KEYCHAIN': '0',
        'FORESIGHT_USER': 'f4-preflight', 'FORESIGHT_USERS_DIR': str(output / 'users'),
        'FORESIGHT_EPISODE_STORE': str(output / 'episodes'), 'SUBCONSCIOUS_VAULT': str(output / 'vault'),
        'FINANCE_REJUDGE_PENDING_INDEX': str(output / 'queue/index.jsonl'),
        'FINANCE_DEPLOY_LEDGER': str(output / 'deploy.jsonl'), 'FINANCE_SITE': str(output / 'site'),
        'AGENT_RUNTIME_BACKEND': 'continuous_glm', 'ASK_CONTINUOUS_RUNTIME': 'on',
        'WORKBENCH_TEST_RUN_DELAY_MS': '0', 'GIT_OPTIONAL_LOCKS': '0',
    })
    sys.path.insert(0, str(root))
    requests: list[dict] = []
    blocked: list[dict] = []
    lock = threading.Lock()
    old_connect = socket.socket.connect
    old_connect_ex = socket.socket.connect_ex
    old_popen = subprocess.Popen

    def deny_connect(_socket, address):
        with lock:
            blocked.append({'kind': 'socket', 'address': str(address)})
        raise OSError('offline preflight: all socket connections denied')

    def guarded_popen(command, *a, **kw):
        if isinstance(command, (list, tuple)) and command:
            words = [str(x) for x in command]
            safe = {'rev-parse', 'status', 'diff', 'show', 'log', 'ls-files', 'cat-file'}
            if Path(words[0]).name == 'git' and any(w in safe for w in words[1:]) and not kw.get('shell'):
                return old_popen(command, *a, **kw)
        with lock:
            blocked.append({'kind': 'subprocess', 'executable': str(command[0]) if isinstance(command, (list, tuple)) and command else 'shell'})
        raise OSError('offline preflight: subprocess denied')

    socket.socket.connect = deny_connect
    socket.socket.connect_ex = deny_connect
    subprocess.Popen = guarded_popen
    result: dict = {'scope': 'offline_full_conversation_entry_not_F4', 'physical_model_requests': 0}
    try:
        from intelligence.services import llm_http_transport
        from intelligence.services.llm_settings import SessionLLMSettings

        def stop_transport(request, *a, **kw):
            body = json.loads(request.data.decode())
            with lock:
                number = len(requests) + 1
                record = {'number': number, 'requested_model': body.get('model'),
                          'stream': body.get('stream', False), 'transmitted': False}
                requests.append(record)
                with (output / f'blocked-model-request-{number:02}.json').open('x') as handle:
                    json.dump({'record': record, 'body': body}, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
            raise urllib.error.URLError('offline preflight: model request captured, not sent')

        llm_http_transport.urlopen = stop_transport
        settings = SessionLLMSettings(credential_store=None)
        settings.configure_byok('f4-preflight', provider_id='zhipu', api_key='offline-placeholder-not-a-credential',
                                base_url='https://offline.invalid/v1', model=args.model, persist=False)
        from intelligence.api.app import create_app
        from fastapi.testclient import TestClient
        app = create_app(repo_root=root, llm_settings=settings, run_timeout_sec=25)
        with TestClient(app) as client:
            response = client.post('/api/conversations', json={'user': 'f4-preflight'})
            response.raise_for_status()
            conversation_id = response.json()['conversation_id']
            response = client.post(f'/api/conversations/{conversation_id}/messages',
                                   json={'user': 'f4-preflight', 'content': question,
                                         'skill_mode': 'hybrid', 'selected_skill_ids': []})
            response.raise_for_status()
            result['conversation_id'] = conversation_id
            result['post'] = response.json()
            end = time.monotonic() + 30
            while True:
                response = client.get(f'/api/conversations/{conversation_id}/messages', params={'user': 'f4-preflight'})
                response.raise_for_status()
                messages = response.json()
                assistants = [m for m in messages if m['role'] == 'assistant']
                if assistants and assistants[-1]['status'] in {'completed', 'failed', 'cancelled'}:
                    result['assistant_status'] = assistants[-1]['status']
                    (output / 'messages.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2))
                    break
                if time.monotonic() >= end:
                    raise TimeoutError('conversation preflight did not settle')
                time.sleep(0.05)
        result['expected_model'] = args.model
        result['all_requests_match'] = bool(requests) and all(r['requested_model'] == args.model for r in requests)
        result['entry_preflight_passed'] = result['all_requests_match'] and not blocked
        # A terminal message after deliberately blocked transport is not a successful model answer.
        result['model_task_completion_verified'] = False
        return 0 if result['entry_preflight_passed'] else 1
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        if getattr(exc, 'response', None) is not None:
            result['error_response'] = exc.response.text
        raise
    finally:
        result['blocked_model_requests'] = requests
        result['other_io_blocked'] = blocked
        (output / 'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        socket.socket.connect = old_connect
        socket.socket.connect_ex = old_connect_ex
        subprocess.Popen = old_popen
        print(json.dumps({k: result.get(k) for k in ['scope', 'physical_model_requests', 'expected_model', 'all_requests_match', 'entry_preflight_passed', 'assistant_status', 'error']}, ensure_ascii=False))


if __name__ == '__main__':
    raise SystemExit(main())
