import contextlib
from datetime import date, timedelta
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from sil import Ledger, main


class LoopTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.start = date(2026, 10, 5)
        self.loop = Ledger(self.root, self.start)
        self.loop.init()

    def call(self, name, *args, **kwargs):
        with self.loop.connect():
            self.loop.db.execute('BEGIN IMMEDIATE')
            return getattr(self.loop, name)(*args, **kwargs)

    def proposal(self, watch=()):
        occurrence = self.call('occurrence', 'Porta ocupada', 'log: bind falhou', None, None)
        return self.call('lesson', occurrence['id'], 'Abortar se porta ocupada', 'testes HTTP', watch)

    def adopt(self, watch=()):
        lesson = self.proposal(watch)
        return self.call('decision', lesson['id'], 'adopt', 'Pessoa', 'Decisão explícita')['rule']

    def test_full_cycle_and_history(self):
        rule = self.adopt()
        self.call('verify', rule, 'porta livre: 0', 'ocupada: 1', 'tests/port.log')
        self.call('cite', rule, 'bloqueio observado', 'teste')
        self.call('review', rule, 'revise', 'Pessoa', 'ampliar escopo', 'Validar a porta antes do servidor')
        data = self.call('export')
        self.assertIsNone(data['rules'][0]['verification'])
        self.assertEqual(data['events'][-1]['action'], 'review')
        self.assertIn('verification-reported', [e['action'] for e in data['events']])
        self.call('review', rule, 'retire', 'Pessoa', 'Servidor removido')
        self.assertEqual(self.call('get',rule)['status'], 'retired')
        self.assertEqual(len(self.call('rows','rule')), 1)

    def test_init_preserves_files_and_existing_state(self):
        (self.root/'AGENTS.md').write_text('instruções existentes')
        self.proposal()
        with self.assertRaises(ValueError): self.loop.init()
        self.assertEqual((self.root/'AGENTS.md').read_text(), 'instruções existentes')
        self.assertEqual(len(self.call('rows','lesson')),1)

    def test_days_threshold_is_inclusive_and_reminders_do_not_approve(self):
        self.proposal()
        self.loop.today = self.start + timedelta(days=6)
        self.assertFalse(self.call('status')['approval_due'])
        self.loop.today += timedelta(days=1)
        self.assertTrue(self.call('status')['approval_due'])
        self.assertTrue(self.call('request')['requested'])
        self.assertFalse(self.call('request')['requested'])
        self.assertEqual(self.call('rows','lesson')[0]['status'],'proposed')
        self.assertEqual(self.call('status')['overdue'],['L0001'])
        self.loop.today += timedelta(days=7)
        self.assertTrue(self.call('request')['requested'])

    def test_two_same_day_releases_count_and_incidents_do_not(self):
        self.proposal()
        self.call('occurrence','Outro erro','log',None,None)
        self.assertFalse(self.call('status')['approval_due'])
        for name in ('v1','v2'): self.call('release',name,'commit explícito')
        self.assertTrue(self.call('status')['approval_due'])
        with self.assertRaises(ValueError): self.call('release','v2','duplicado')
        self.assertEqual(self.call('release_count'),2)

    def test_batch_threshold_and_new_batch(self):
        for _ in range(4): self.proposal()
        self.assertFalse(self.call('status')['approval_due'])
        self.proposal()
        self.assertTrue(self.call('request')['requested'])
        self.assertFalse(self.call('request')['requested'])
        for _ in range(5): self.proposal()
        self.assertTrue(self.call('request')['requested'])

    def test_defer_due_today_and_trial_rejection(self):
        x=self.proposal()
        self.call('decision',x['id'],'defer','Pessoa','aguardar','2026-10-06')
        self.assertFalse(self.call('status')['approval_due'])
        self.loop.today=date(2026,10,6)
        self.assertTrue(self.call('status')['approval_due'])
        self.call('decision',x['id'],'trial','Pessoa','experimentar','2026-10-08','bloquear caso inválido')
        self.assertEqual(self.call('rows','rule')[0]['status'],'trial')
        self.loop.today=date(2026,10,8)
        self.assertIn(x['id'],self.call('status')['overdue'])
        self.call('decision',x['id'],'reject','Pessoa','teste não ajudou')
        self.assertEqual(self.call('rows','rule')[0]['status'],'retired')

    def test_trial_adopt_reuses_rule_and_history(self):
        x=self.proposal()
        self.call('decision',x['id'],'trial','Pessoa','experimentar','2026-10-08','critério')
        self.call('decision',x['id'],'adopt','Pessoa','evidência do teste')
        rules=self.call('rows','rule')
        self.assertEqual(len(rules),1)
        self.assertEqual(rules[0]['status'],'active')
        with self.assertRaises(ValueError): self.call('decision',x['id'],'adopt','Pessoa','outra')

    def test_trial_promotion_invalidates_changed_evidence(self):
        file=self.root/'config.txt'; file.write_text('before')
        x=self.proposal(['config.txt'])
        self.call('decision',x['id'],'trial','Pessoa','experimentar','2026-10-08','critério')
        self.call('verify','R0001','válido passou','inválido bloqueou','log')
        for n in range(5): self.call('release',str(n),'commit')
        file.write_text('after')
        self.call('decision',x['id'],'adopt','Pessoa','nova configuração avaliada')
        self.assertIsNone(self.call('get','R0001')['verification'])
        self.assertEqual(self.call('status')['reviews'],[])

    def test_bad_decisions_roll_back(self):
        x=self.proposal()
        for args in [('adopt','','motivo'),('defer','Pessoa','motivo'),
                     ('trial','Pessoa','motivo','2026-10-09'),
                     ('defer','Pessoa','motivo','2026-10-05'),
                     ('adopt','Pessoa','')]:
            with self.assertRaises(ValueError): self.call('decision',x['id'],*args)
        self.assertEqual(self.call('get',x['id'])['status'],'proposed')
        self.assertEqual(self.call('rows','rule'),[])

    def test_changed_file_and_missing_file_need_review(self):
        file=self.root/'settings.txt';file.write_text('old')
        rule=self.adopt(['settings.txt'])
        self.assertEqual(self.call('status')['reviews'],[])
        file.write_text('new')
        self.assertIn('arquivo alterado',self.call('status')['reviews'][0]['reasons'][0])
        self.call('review',rule,'keep','Pessoa','nova configuração validada')
        self.assertEqual(self.call('status')['reviews'],[])
        file.unlink()
        self.assertIn('indisponível',self.call('status')['reviews'][0]['reasons'][0])
        with self.assertRaises(ValueError): self.call('review',rule,'keep','Pessoa','sem arquivo')
        self.call('review',rule,'retire','Pessoa','arquivo removido')
        self.assertEqual(self.call('status')['reviews'],[])

    def test_no_citation_is_not_automatic_retirement(self):
        rule=self.adopt()
        for n in range(5): self.call('release',str(n),'commit')
        self.assertTrue(self.call('status')['reviews'])
        self.assertEqual(self.call('get',rule)['status'],'active')
        self.call('review',rule,'keep','Pessoa','proteção de erro raro e grave')
        self.assertEqual(self.call('status')['reviews'],[])

    def test_citation_does_not_reset_periodic_review(self):
        rule=self.adopt()
        self.loop.today=self.start+timedelta(days=30)
        self.call('cite',rule,'log','humano')
        self.assertTrue(self.call('status')['reviews'])

    def test_settings_and_missing_references(self):
        self.call('config',{'approval_days':2,'approval_batch':1})
        self.proposal()
        self.assertTrue(self.call('status')['approval_due'])
        for value in (0,-1,True,'2'):
            with self.assertRaises(ValueError): self.call('config',{'approval_days':value})
        with self.assertRaises(ValueError): self.call('lesson','O9999','x','y',[])
        with self.assertRaises(ValueError): self.call('lesson','L0001','x','y',[])

    def test_watch_path_escape_rejected(self):
        for path in ('../outside','/etc/passwd','.sil/state.sqlite3','missing'):
            with self.assertRaises(ValueError): self.proposal([path])
        (self.root/'escape').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError): self.proposal(['escape'])

    def test_check_cli_exit_codes_and_corrupt_status(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--project',str(self.root),'check']),0)
            self.assertEqual(main(['--project',str(self.root/'missing'),'check']),2)
        self.adopt()
        with self.loop.connect():
            x=self.loop.get('R0001');x['review_due']='2000-01-01';self.loop.put('rule',x)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--project',str(self.root),'check']),1)
        with self.loop.connect():
            x=self.loop.get('L0001');x['status']='inventado';self.loop.put('lesson',x)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--project',str(self.root),'check']),2)

    def test_parallel_capture_keeps_all_records(self):
        script=str(Path(__file__).resolve().parents[1]/'sil.py')
        jobs=[subprocess.Popen([sys.executable,script,'--project',str(self.root),
             'occurrence','--title',f'evento {n}','--evidence','log'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
             for n in range(8)]
        ids=[]
        for job in jobs:
            out,err=job.communicate(timeout=15)
            self.assertEqual(job.returncode,0,err)
            ids.append(json.loads(out)['id'])
        self.assertEqual(len(set(ids)),8)
        self.assertEqual(len(self.call('rows','occurrence')),8)


if __name__ == '__main__': unittest.main()
