#!/usr/bin/env python3
"""Exercise the CLI in a disposable project. Does not touch user repositories."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

cli = Path(__file__).resolve().parents[1] / 'sil.py'
with tempfile.TemporaryDirectory(prefix='sil-demo-') as folder:
    def run(*args, expected=0):
        proc = subprocess.run([sys.executable, str(cli), '--project', folder, *args],
                              text=True, capture_output=True, timeout=15)
        if proc.returncode != expected:
            raise RuntimeError(proc.stderr or proc.stdout)
        return json.loads(proc.stdout)
    run('init')
    run('config','--approval-batch','1')
    occurrence=run('occurrence','--title','Port already occupied',
                   '--evidence','Illustrative example: isolated test failed to bind')
    lesson=run('lesson','--occurrence',occurrence['id'],'--proposal','Abort on occupied port',
               '--scope','Example HTTP tests')
    assert run('request')['requested'] is True
    assert run('request')['requested'] is False
    decision=run('decide',lesson['id'],'adopt','--approved-by','Demo fictional reviewer',
                 '--reason','Illustrative decision in a disposable fixture')
    rule=decision['rule']
    run('check')
    run('enforce',rule,'--rung','hook','--leak','git push --no-verify','--binding','yes',
        '--approved-by','Demo fictional reviewer','--reason','Breaking it without the playbook causes harm')
    assert run('check',expected=1)['promotion']['in_sync'] is False
    assert run('promote')['written'] is False
    assert run('promote','--write')['written'] is True
    assert rule in (Path(folder)/'AGENTS.md').read_text(encoding='utf-8')
    run('check')
    for name in ['v1','v2','v3','v4','v5']:
        run('release',name,'--evidence','Fictional release for demonstration')
    result=run('check',expected=1)
    assert result['reviews'][0]['id']==rule
    run('review',rule,'retire','--approved-by','Demo fictional reviewer',
        '--reason','Example component removed')
    run('check',expected=1)
    run('promote','--write')
    run('check')
    data=run('export')
    assert data['rules'][0]['status']=='retired'
    print(json.dumps({'demo':'PASS','events':len(data['events']),
                      'isolation':'temporary project removed on exit'},ensure_ascii=False))
