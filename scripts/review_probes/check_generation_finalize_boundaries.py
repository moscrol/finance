"""复现外层 finalize 绕过生成根拒绝的两种失败：告警写回代码、接收脚本外逃。

对干净固定检出运行真实 shell/launcher/notify，L2 与质检使用隔离替身。
所有运行产物写入 --output-dir，调用方必须保留原始失败收据并另建目录复验。
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

CASES = ('safe_external_alert', 'generation_rejected_alert', 'l2_failed_alert', 'receive_escape')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.output_dir.resolve()
    if out.is_relative_to(repo) or out.exists():
        parser.error('--output-dir must be a new directory outside the checked code tree')
    if subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True):
        parser.error('--repo must be a clean fixed checkout')
    out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('generation_fixture', repo / 'tests/test_generation_code_root.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    clean = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ}
    os.environ.clear()
    os.environ.update(clean)
    observations = []
    for case in CASES:
        with tempfile.TemporaryDirectory(prefix=case + '-', dir=out) as temporary:
            code, data, elsewhere, env = fixture.rig.__wrapped__(Path(temporary))
            script = code / 'skills/daily-full-review/scripts/nightly_full_review.sh'
            # The operational/L2 root is separate from the actual generation snapshot.
            ops = elsewhere / 'ops-code'
            (ops / 'scripts/moneyflow').mkdir(parents=True)
            shutil.copy2(code / 'scripts/notify_ops.py', ops / 'scripts/notify_ops.py')
            (ops / 'scripts/check_daily_review_data.py').write_text('')
            dispatcher = elsewhere / 'python-dispatch'
            dispatcher.write_text(f'''#!{sys.executable}
import os, sys
args = sys.argv[1:]
if any(a.endswith(('run_daily_generation.py', 'notify_ops.py')) for a in args):
    os.execv(sys.executable, [sys.executable, *args])
sys.exit(0)
''')
            dispatcher.chmod(0o755)
            l2 = ops / 'scripts/moneyflow/run_l2_pipeline.sh'
            l2.write_text('#!/bin/sh\nexit ' + ('3' if case == 'l2_failed_alert' else '0') + '\n')
            l2.chmod(0o755)
            desktop = elsewhere / 'osascript'
            desktop.write_text('#!/bin/sh\nexit 0\n')
            desktop.chmod(0o755)
            env.update(FINANCE_PYTHON=str(dispatcher), FINANCE_LOCK_DIR=str(data / 'locks'),
                       FINANCE_OPS_HEALTH_LOG=str(data / 'health.log'),
                       FINANCE_CODE_ROOT=str(ops), FINANCE_GENERATION_CODE_ROOT=str(code),
                       METHOD_STUDY_DIR=str(data / 'method'), TEST_GATE_RC='3',
                       PATH=str(elsewhere) + os.pathsep + env['PATH'])
            alert = Path(env['HOME']) / '.finance-runtime/alerts.log'
            if case in {'generation_rejected_alert', 'l2_failed_alert'}:
                alert.parent.mkdir(parents=True)
                alert.symlink_to(code / 'qc-outer-alert.log')
            marker = data / 'receiver-executed.marker'
            if case == 'receive_escape':
                poison = data / 'poison-receive.sh'
                poison.write_text("printf '%s\\n' 'QC_UNSAFE_RECEIVER_EXECUTED'\n: > " + shlex.quote(str(marker)) + '\n')
                receiver = code / 'skills/daily-full-review/scripts/receive_kb_ingest_queue.sh'
                receiver.symlink_to(poison)
            before_code = fixture.inventory(code)
            before_ops = fixture.inventory(ops)
            command = ['/bin/zsh', str(script), 'finalize', fixture.DAY]
            run = subprocess.run(command, cwd=elsewhere, env=env, text=True,
                                 capture_output=True, timeout=45)
            after_code, after_ops = fixture.inventory(code), fixture.inventory(ops)
            changed_code = sorted(p for p in before_code.keys() | after_code.keys() if before_code.get(p) != after_code.get(p))
            changed_ops = sorted(p for p in before_ops.keys() | after_ops.keys() if before_ops.get(p) != after_ops.get(p))
            (out / (case + '.stdout.log')).write_text(run.stdout)
            (out / (case + '.stderr.log')).write_text(run.stderr)
            safe_control = case != 'safe_external_alert' or (run.returncode == 1 and alert.exists())
            passed = run.returncode != 0 and not changed_code and not changed_ops and not marker.exists() and safe_control
            observations.append(dict(case=case, returncode=run.returncode,
                                     changed_generation_code_files=changed_code, changed_ops_code_files=changed_ops,
                                     launcher_root_diagnostic='generation code/data root invalid' in run.stderr,
                                     launcher_imported='generation_import=' in run.stderr,
                                     receiver_executed=marker.exists(), alert_written=alert.exists(),
                                     alert_text=alert.read_text() if alert.exists() else None,
                                     passed=passed, command=command))
    final_revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    result = dict(revision=revision, final_revision=final_revision,
                  target_status=subprocess.check_output(['git','-C',str(repo),'status','--porcelain=v1'],text=True),
                  cases=observations, passed=sum(case['passed'] for case in observations),
                  failed=sum(not case['passed'] for case in observations))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    (out / 'entry-boundaries.json').write_text(rendered)
    print(rendered)
    return 0 if not result['failed'] and not result['target_status'] and revision == final_revision else 1


if __name__ == '__main__':
    raise SystemExit(main())
