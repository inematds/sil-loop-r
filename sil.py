#!/usr/bin/env python3
"""SIL Loop R: local learning ledger, with explicit decisions and review dates."""
import argparse
import contextlib
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

VERSION = '1.0.0'
DEFAULTS = dict(approval_days=7, approval_releases=2, approval_batch=5,
                review_days=30, uncited_releases=5)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def day(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('Data deve estar em AAAA-MM-DD.')
    return parsed


def required(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} não pode estar vazio.')
    return value.strip()


class Ledger:
    def __init__(self, root, today=None):
        self.root = Path(root).resolve()
        self.today = today or date.today()
        self.path = self.root / '.sil' / 'state.sqlite3'
        self.db = None

    @contextlib.contextmanager
    def connect(self, create=False):
        if not create and not self.path.is_file():
            raise ValueError('Projeto não inicializado. Execute init.')
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        try:
            with self.db:
                if not create:
                    version = self.db.execute('PRAGMA user_version').fetchone()[0]
                    if version != 1:
                        raise ValueError('Versão de armazenamento não suportada.')
                yield self
        finally:
            self.db.close()
            self.db = None

    def init(self):
        if self.path.exists():
            raise ValueError('Já inicializado; nenhum dado foi substituído.')
        with self.connect(create=True):
            self.db.executescript('''
                CREATE TABLE objects(id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL,
                                    action TEXT NOT NULL, object_id TEXT, payload TEXT NOT NULL);
                CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                PRAGMA user_version=1;
            ''')
            self.setmeta('config', DEFAULTS)
            self.setmeta('created', self.today.isoformat())
            self.event('init', None, {'version': VERSION})
        return {'initialized': str(self.root), 'version': VERSION}

    def meta(self, key, default=None):
        row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def setmeta(self, key, value):
        self.db.execute('INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                        (key, encode(value)))

    def event(self, action, object_id, data):
        self.db.execute('INSERT INTO events(day,action,object_id,payload) VALUES (?,?,?,?)',
                        (self.today.isoformat(), action, object_id, encode(data)))

    def rows(self, kind):
        return [json.loads(r[0]) for r in self.db.execute(
            'SELECT payload FROM objects WHERE kind=? ORDER BY rowid', (kind,))]

    def get(self, ident, kind=None):
        row = self.db.execute('SELECT kind,payload FROM objects WHERE id=?', (ident,)).fetchone()
        if not row or (kind and row['kind'] != kind):
            raise ValueError(f'Referência inexistente ou de tipo incorreto: {ident}')
        return json.loads(row['payload'])

    def put(self, kind, obj):
        self.db.execute('INSERT INTO objects VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                        (obj['id'], kind, encode(obj)))

    def new(self, kind, prefix, fields):
        self.db.execute('BEGIN IMMEDIATE') if not self.db.in_transaction else None
        number = len(self.rows(kind)) + 1
        obj = dict(id=f'{prefix}{number:04}', created=self.today.isoformat(), **fields)
        self.put(kind, obj)
        return obj

    def release_count(self):
        return len(self.rows('release'))

    def config(self, updates):
        settings = self.meta('config')
        for key, value in updates.items():
            if key not in DEFAULTS or type(value) is not int or value < 1:
                raise ValueError('Configuração exige inteiros positivos e chaves conhecidas.')
            settings[key] = value
        if updates:
            self.setmeta('config', settings)
            self.event('configure', None, updates)
        return settings

    def snapshot_files(self, paths):
        result = {}
        for name in paths:
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or '.sil' in path.parts:
                raise ValueError('Arquivo associado deve ser relativo ao projeto e fora de .sil.')
            full = (self.root / path).resolve()
            if not full.is_relative_to(self.root) or not full.is_file():
                raise ValueError(f'Arquivo ausente ou fora do projeto: {name}')
            result[path.as_posix()] = hashlib.sha256(full.read_bytes()).hexdigest()
        return result

    def occurrence(self, title, evidence, cause, correction):
        obj = self.new('occurrence', 'O', dict(title=required(title, 'Título'),
            evidence=required(evidence, 'Evidência'), cause=cause or 'A investigar',
            correction=correction or 'Não aplicada'))
        self.event('occurrence', obj['id'], obj)
        return obj

    def lesson(self, occurrence, proposal, scope, watch):
        self.get(occurrence, 'occurrence')
        obj = self.new('lesson', 'L', dict(occurrence=occurrence,
            proposal=required(proposal, 'Proposta'), scope=required(scope, 'Escopo'),
            files=self.snapshot_files(watch), status='proposed',
            release=self.release_count(), due=None, rule=None))
        self.event('lesson', obj['id'], obj)
        return obj

    def decision(self, ident, action, actor, reason, until=None, criterion=None):
        obj = self.get(ident, 'lesson')
        if obj['status'] not in ('proposed', 'deferred', 'trial'):
            raise ValueError('Lição já decidida; revise a regra ou registre uma nova proposta.')
        actor = required(actor, 'Responsável pela decisão')
        reason = required(reason, 'Justificativa')
        if action in ('trial', 'defer'):
            if not until or day(until) <= self.today:
                raise ValueError('Teste e adiamento exigem data futura.')
        elif until:
            raise ValueError('Data só se aplica a teste ou adiamento.')
        if action == 'trial':
            required(criterion, 'Critério para avaliar o teste')
        if action not in ('adopt', 'reject', 'trial', 'defer'):
            raise ValueError('Decisão desconhecida.')
        if obj['status'] == 'trial' and action in ('trial', 'defer'):
            raise ValueError('Conclua o teste adotando ou rejeitando, com evidências na justificativa.')
        if action in ('adopt', 'trial'):
            files = self.snapshot_files(obj['files'])
            if obj['rule']:
                rule = self.get(obj['rule'], 'rule')
                if files != rule['files']:
                    rule['verification'] = None
                rule.update(status='active', reviewed=self.today.isoformat(), files=files,
                            review_release=self.release_count(),
                            review_due=(self.today + timedelta(days=self.meta('config')['review_days'])).isoformat())
                self.put('rule', rule)
            else:
                rule = self.new('rule', 'R', dict(lesson=ident, text=obj['proposal'],
                    scope=obj['scope'], status='trial' if action == 'trial' else 'active',
                    files=files, reviewed=self.today.isoformat(), review_release=self.release_count(),
                    review_due=until if action == 'trial' else
                    (self.today + timedelta(days=self.meta('config')['review_days'])).isoformat(),
                    citation_release=self.release_count(), citations=[], verification=None))
                obj['rule'] = rule['id']
        elif action == 'reject' and obj['rule']:
            rule = self.get(obj['rule'], 'rule')
            rule['status'] = 'retired'
            self.put('rule', rule)
        obj.update(status={'adopt':'adopted','reject':'rejected','trial':'trial','defer':'deferred'}[action],
                   due=until, decision_by=actor, reason=reason, criterion=criterion)
        self.put('lesson', obj)
        self.event('decision', ident, dict(action=action, actor=actor, reason=reason,
                                          until=until, criterion=criterion, rule=obj['rule']))
        return obj

    def release(self, name, evidence):
        name = required(name, 'Identificador do release')
        if any(r['name'] == name for r in self.rows('release')):
            raise ValueError('Release já registrado.')
        obj = self.new('release', 'V', dict(name=name, evidence=required(evidence, 'Evidência')))
        self.event('release', obj['id'], obj)
        return obj

    def cite(self, ident, evidence, caught_by):
        obj = self.get(ident, 'rule')
        if obj['status'] == 'retired':
            raise ValueError('Regra retirada não recebe novas citações.')
        citation = dict(day=self.today.isoformat(), evidence=required(evidence, 'Evidência'),
                        caught_by=required(caught_by, 'Quem detectou'), release=self.release_count())
        obj['citations'].append(citation)
        obj['citation_release'] = self.release_count()
        self.put('rule', obj)
        self.event('citation', ident, citation)
        return obj

    def review(self, ident, action, actor, reason, text=None):
        obj = self.get(ident, 'rule')
        if obj['status'] != 'active':
            raise ValueError('Revisão exige regra permanente ativa; testes são decididos em decide.')
        actor = required(actor, 'Responsável pela decisão')
        reason = required(reason, 'Justificativa e evidência da revisão')
        if action not in ('keep', 'revise', 'retire'):
            raise ValueError('Ação de revisão desconhecida.')
        if action == 'revise':
            obj['text'] = required(text, 'Novo texto')
            obj['verification'] = None
        elif text:
            raise ValueError('Texto só pode ser alterado com revise.')
        if action == 'retire':
            obj['status'] = 'retired'
        else:
            files = self.snapshot_files(obj['files'])
            if files != obj['files']:
                obj['verification'] = None
            obj['files'] = files
        obj.update(reviewed=self.today.isoformat(), review_release=self.release_count(),
            review_due=(self.today + timedelta(days=self.meta('config')['review_days'])).isoformat())
        self.put('rule', obj)
        self.event('review', ident, dict(action=action, actor=actor, reason=reason, text=text))
        return obj

    def verify(self, ident, positive, negative, evidence):
        obj = self.get(ident, 'rule')
        if obj['status'] == 'retired':
            raise ValueError('Regra retirada.')
        obj['verification'] = dict(day=self.today.isoformat(),
            positive=required(positive, 'Caso válido e resultado observado'),
            negative=required(negative, 'Caso inválido e resultado observado'),
            evidence=required(evidence, 'Evidência'), files=self.snapshot_files(obj['files']))
        self.put('rule', obj)
        self.event('verification-reported', ident, obj['verification'])
        return obj

    def status(self):
        config = self.meta('config')
        pending = [x for x in self.rows('lesson') if x['status'] in ('proposed','trial','deferred')]
        last = self.meta('request', {})
        expired = [x['id'] for x in pending if x['due'] and day(x['due']) <= self.today]
        proposed = [x for x in pending if x['status'] == 'proposed']
        oldest = min((x['created'] for x in proposed), default=self.today.isoformat())
        baseline = max(oldest, last.get('day', oldest))
        release_base = max(min((x['release'] for x in proposed), default=self.release_count()),
                           last.get('release', 0))
        unseen = [x['id'] for x in proposed if x['id'] not in last.get('ids', [])]
        reasons = []
        if expired:
            reasons.append('prazo de teste/adiamento atingido')
        if proposed and (self.today - day(baseline)).days >= config['approval_days']:
            reasons.append('intervalo em dias')
        if proposed and self.release_count() - release_base >= config['approval_releases']:
            reasons.append('intervalo em releases')
        if len(unseen) >= config['approval_batch']:
            reasons.append('lote de novas propostas')
        overdue = [x['id'] for x in proposed if
            (self.today-day(x['created'])).days >= config['approval_days'] or
            self.release_count()-x['release'] >= config['approval_releases']]
        reviews = []
        for rule in self.rows('rule'):
            if rule['status'] != 'active':
                continue
            why = []
            if day(rule['review_due']) <= self.today:
                why.append('revisão periódica vencida')
            if self.release_count() - max(rule['citation_release'],rule['review_release']) >= config['uncited_releases']:
                why.append('sem citação na janela de releases')
            for filename, fingerprint in rule['files'].items():
                try:
                    current = self.snapshot_files([filename])[filename]
                    if current != fingerprint:
                        why.append(f'arquivo alterado: {filename}')
                except (ValueError, OSError):
                    why.append(f'arquivo indisponível: {filename}')
            if why:
                reviews.append(dict(id=rule['id'], reasons=why))
        review_ids = [r['id'] for r in reviews]
        new_expired = set(expired) - set(last.get('expired', []))
        new_reviews = set(review_ids) - set(last.get('reviews', []))
        reminder_allowed = not last or (self.today-day(last['day'])).days >= config['approval_days']
        request_due = bool(reasons or reviews) and bool(
            reminder_allowed or unseen and len(unseen) >= config['approval_batch'] or
            self.release_count()-last.get('release', 0) >= config['approval_releases'] or
            new_expired or new_reviews)
        return dict(approval_due=request_due, approval_reasons=reasons,
                    pending=pending, overdue=sorted(set(expired + overdue)),
                    reviews=reviews, release_count=self.release_count(), config=config)

    def request(self):
        result = self.status()
        if not result['approval_due']:
            return dict(requested=False, **result)
        self.setmeta('request', dict(day=self.today.isoformat(), release=self.release_count(),
            ids=[x['id'] for x in result['pending']], reviews=[r['id'] for r in result['reviews']],
            expired=[x['id'] for x in result['pending'] if x['due'] and day(x['due']) <= self.today]))
        self.event('approval-request-prepared', None, result)
        return dict(requested=True, **result)

    def integrity(self):
        if self.db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Banco inconsistente.')
        settings = self.meta('config')
        if not isinstance(settings, dict) or set(settings) != set(DEFAULTS):
            raise ValueError('Configuração incompleta.')
        for value in settings.values():
            if type(value) is not int or value < 1:
                raise ValueError('Configuração inválida.')
        for x in self.rows('lesson'):
            self.get(x['occurrence'], 'occurrence')
            if x['status'] not in ('proposed','adopted','rejected','trial','deferred'):
                raise ValueError(f"Status desconhecido: {x['id']}")
            if x['status'] in ('trial','deferred'):
                day(x['due'])
            if x['status'] in ('trial','adopted') and not x['rule']:
                raise ValueError('Lição aplicada sem regra.')
            if x['rule']:
                r = self.get(x['rule'], 'rule')
                if r['lesson'] != x['id']:
                    raise ValueError('Vínculo entre lição e regra inconsistente.')
        for x in self.rows('rule'):
            self.get(x['lesson'], 'lesson')
            if x['status'] not in ('active','trial','retired'):
                raise ValueError('Status de regra desconhecido.')
            day(x['review_due'])
        return True

    def export(self):
        return dict(version=VERSION, config=self.meta('config'),
            occurrences=self.rows('occurrence'), lessons=self.rows('lesson'),
            rules=self.rows('rule'), releases=self.rows('release'),
            events=[dict(r, payload=json.loads(r['payload'])) for r in
                    self.db.execute('SELECT * FROM events ORDER BY seq')])


def parser():
    p = argparse.ArgumentParser(description='SIL Loop R — aprendizado local com decisões rastreáveis')
    p.add_argument('--version', action='version', version=VERSION)
    p.add_argument('--project', default='.', help='Raiz do projeto (padrão: diretório atual)')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init', help='Inicializar armazenamento; preserva instruções existentes')
    c = sub.add_parser('config', help='Consultar ou alterar frequências')
    for key in DEFAULTS:
        c.add_argument('--'+key.replace('_','-'), type=int)
    c = sub.add_parser('occurrence', help='Registrar fato observado e evidência')
    c.add_argument('--title', required=True); c.add_argument('--evidence', required=True)
    c.add_argument('--cause'); c.add_argument('--correction')
    c = sub.add_parser('lesson', help='Propor aprendizado ligado a uma ocorrência')
    c.add_argument('--occurrence', required=True); c.add_argument('--proposal', required=True)
    c.add_argument('--scope', required=True); c.add_argument('--watch', action='append', default=[])
    c = sub.add_parser('decide', help='Registrar decisão humana explícita')
    c.add_argument('id'); c.add_argument('action', choices=['adopt','reject','trial','defer'])
    c.add_argument('--approved-by', required=True); c.add_argument('--reason', required=True)
    c.add_argument('--until'); c.add_argument('--criterion')
    c = sub.add_parser('release', help='Registrar um release real, com identificador único')
    c.add_argument('name'); c.add_argument('--evidence', required=True)
    c = sub.add_parser('cite', help='Registrar quando a regra ajudou')
    c.add_argument('id'); c.add_argument('--evidence', required=True); c.add_argument('--caught-by', required=True)
    c = sub.add_parser('review', help='Manter, revisar ou retirar regra permanente')
    c.add_argument('id'); c.add_argument('action', choices=['keep','revise','retire'])
    c.add_argument('--approved-by', required=True); c.add_argument('--reason', required=True); c.add_argument('--text')
    c = sub.add_parser('verify', help='Registrar evidências de testes executados; não executa comandos')
    c.add_argument('id'); c.add_argument('--positive', required=True)
    c.add_argument('--negative', required=True); c.add_argument('--evidence', required=True)
    for name, help_text in [('status','Consultar pendências e revisões'),
        ('request','Preparar lote de aprovação e registrar lembrete'),
        ('check','Sair com 1 se houver pendências vencidas ou revisões; 2 em erro'),
        ('context','Consultar regras ativas e experimentais para a sessão'),
        ('export','Exportar todos os dados e histórico em JSON')]:
        sub.add_parser(name, help=help_text)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    ledger = Ledger(args.project)
    try:
        if args.cmd == 'init':
            result = ledger.init()
        else:
            with ledger.connect():
                # All reads/writes observe one consistent transaction; writers are serialized.
                ledger.db.execute('BEGIN IMMEDIATE')
                ledger.integrity()
                if args.cmd == 'config':
                    result = ledger.config({k:getattr(args,k) for k in DEFAULTS if getattr(args,k) is not None})
                elif args.cmd == 'occurrence':
                    result = ledger.occurrence(args.title,args.evidence,args.cause,args.correction)
                elif args.cmd == 'lesson':
                    result = ledger.lesson(args.occurrence,args.proposal,args.scope,args.watch)
                elif args.cmd == 'decide':
                    result = ledger.decision(args.id,args.action,args.approved_by,args.reason,args.until,args.criterion)
                elif args.cmd == 'release':
                    result = ledger.release(args.name,args.evidence)
                elif args.cmd == 'cite':
                    result = ledger.cite(args.id,args.evidence,args.caught_by)
                elif args.cmd == 'review':
                    result = ledger.review(args.id,args.action,args.approved_by,args.reason,args.text)
                elif args.cmd == 'verify':
                    result = ledger.verify(args.id,args.positive,args.negative,args.evidence)
                elif args.cmd == 'request':
                    result = ledger.request()
                elif args.cmd == 'context':
                    status = ledger.status()
                    result = dict(rules=[x for x in ledger.rows('rule') if x['status'] != 'retired'],
                                  reviews=status['reviews'], overdue=status['overdue'])
                elif args.cmd == 'export':
                    result = ledger.export()
                else:
                    result = ledger.status()
                if args.cmd == 'check':
                    print(encode(result))
                    return 1 if result['overdue'] or result['reviews'] else 0
        print(encode(result))
        return 0
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError) as exc:
        print(encode({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
