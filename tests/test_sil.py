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


class Base(unittest.TestCase):
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


class LoopTest(Base):

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


class PromotionTest(Base):
    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(['--project', str(self.root), *args])
        return code, out.getvalue()

    def bound(self):
        rule = self.adopt()
        self.call('enforce', rule, 'Pessoa', 'quebrar sem o playbook causa dano', 'hook',
                  'git push --no-verify', True)
        return rule

    def test_no_binding_rule_needs_no_promotion(self):
        self.adopt()
        self.assertTrue(self.call('status')['promotion']['in_sync'])
        self.assertEqual(self.cli('check')[0], 0)
        self.assertFalse((self.root/'AGENTS.md').exists())

    def test_binding_rule_blocks_check_until_promoted(self):
        rule = self.bound()
        self.assertEqual(self.cli('check')[0], 1)
        dry = self.call('promote')
        self.assertTrue(dry['changed'])
        self.assertIn(rule, dry['diff'])
        self.assertFalse((self.root/'AGENTS.md').exists())
        self.call('promote', None, True)
        text = (self.root/'AGENTS.md').read_text()
        self.assertIn(f'{rule}; escopo: testes HTTP; proteção: hook; vazamento: git push --no-verify', text)
        self.assertEqual(self.cli('check')[0], 0)
        self.assertFalse(self.call('promote', None, True)['changed'])

    def test_promote_preserves_existing_instructions(self):
        (self.root/'AGENTS.md').write_text('# Projeto\n\nInstrução existente.\n')
        self.bound()
        self.call('promote', None, True)
        text = (self.root/'AGENTS.md').read_text()
        self.assertTrue(text.startswith('# Projeto\n\nInstrução existente.\n\n'))
        self.call('review', 'R0001', 'revise', 'Pessoa', 'texto melhor', 'Validar a porta antes do servidor')
        self.assertFalse(self.call('status')['promotion']['in_sync'])
        self.call('promote', None, True)
        text = (self.root/'AGENTS.md').read_text()
        self.assertIn('Validar a porta antes do servidor', text)
        self.assertNotIn('Abortar se porta ocupada', text)
        self.assertEqual(text.count('sil-loop-r:begin'), 1)
        self.assertIn('Instrução existente.', text)

    def test_mutation_edited_or_broken_block_fails_closed(self):
        self.bound()
        self.call('promote', None, True)
        path = self.root/'AGENTS.md'
        good = path.read_text()
        path.write_text(good.replace('proteção: hook', 'proteção: prose'))
        self.assertEqual(self.cli('check')[0], 1)
        path.write_text(good.replace('<!-- sil-loop-r:end -->', ''))
        self.assertIn('corrompido', self.call('status')['promotion']['problem'])
        self.assertEqual(self.cli('check')[0], 1)
        with self.assertRaises(ValueError): self.call('promote', None, True)
        path.unlink()
        self.assertEqual(self.cli('check')[0], 1)
        path.write_text(good)
        self.assertEqual(self.cli('check')[0], 0)

    def test_retired_and_unbound_rules_leave_block(self):
        rule = self.bound()
        self.call('promote', None, True)
        self.call('enforce', rule, 'Pessoa', 'não precisa estar em toda sessão', None, None, False)
        self.assertFalse(self.call('status')['promotion']['in_sync'])
        self.call('promote', None, True)
        text = (self.root/'AGENTS.md').read_text()
        self.assertIn('Nenhuma regra vinculante ativa', text)
        self.assertEqual(self.cli('check')[0], 0)

    def test_custom_file_is_remembered_and_paths_are_confined(self):
        self.bound()
        self.call('promote', 'docs/AGENTS.md', True)
        self.assertTrue((self.root/'docs/AGENTS.md').is_file())
        self.assertEqual(self.call('status')['promotion']['file'], 'docs/AGENTS.md')
        self.assertEqual(self.cli('check')[0], 0)
        for bad in ('../fora.md', '/tmp/x.md', '.sil/x.md'):
            with self.assertRaises(ValueError): self.call('promote', bad, True)

    def test_enforce_validation_and_prose_warning(self):
        rule = self.adopt()
        with self.assertRaises(ValueError): self.call('enforce', rule, 'Pessoa', 'motivo')
        with self.assertRaises(ValueError): self.call('enforce', rule, 'Pessoa', 'motivo', 'magia')
        with self.assertRaises(ValueError): self.call('enforce', rule, '', 'motivo', 'hook')
        self.call('enforce', rule, 'Pessoa', 'vincula', None, None, True)
        self.assertEqual(self.call('status')['prose_binding'], [rule])
        self.call('enforce', rule, 'Pessoa', 'subiu um degrau', 'probe')
        self.assertEqual(self.call('status')['prose_binding'], [])
        self.call('review', rule, 'retire', 'Pessoa', 'removido')
        with self.assertRaises(ValueError): self.call('enforce', rule, 'Pessoa', 'motivo', 'hook')
        self.assertIn('enforcement', [e['action'] for e in self.call('export')['events']])

    def test_brief_context_for_session_hook(self):
        self.bound()
        code, out = self.cli('context', '--brief')
        self.assertEqual(code, 0)
        self.assertIn('R0001 [ativa] Abortar se porta ocupada', out)
        self.assertIn('Promoção: bloco ausente', out)

    def test_v10_storage_without_new_fields_still_works(self):
        rule = self.adopt()
        with self.loop.connect():
            x = self.loop.get(rule)
            for key in ('rung', 'leak', 'binding'): x.pop(key, None)
            self.loop.put('rule', x)
        self.assertEqual(self.cli('check')[0], 0)
        self.assertEqual(self.call('status')['prose_binding'], [])


if __name__ == '__main__': unittest.main()
