# Changelog

## 1.1.0 — 2026-10-05

- `enforce`: registra se a regra é vinculante, o degrau de proteção (prose, checklist, test, probe, hook, server) e o vazamento conhecido, com decisão explícita.
- `promote` / `promote --write`: bloco delimitado com as regras vinculantes ativas no AGENTS.md (ou outro arquivo de instrução), preservando o restante.
- `check` retorna 1 quando o bloco promovido falta, está desatualizado, corrompido ou ilegível.
- `status` mostra `promotion` e `prose_binding`; `context --brief` para hooks de início de sessão.
- Compatível com bancos da 1.0.0; 25 testes (9 novos, incluindo mutação do bloco).

## 1.0.0 — 2026-10-05

- Framework local Python com armazenamento SQLite transacional e exportação JSON.
- Ocorrências, propostas, decisões humanas, experimentos com prazo e regras rastreáveis.
- Solicitações em lote por dias, releases ou volume; revisão por idade, ausência de uso e alteração de arquivos.
- Histórico de decisões, citações e evidências de testes; sem execução automática de comandos armazenados.
- Skill distribuída no repositório, templates e guia de uso.
