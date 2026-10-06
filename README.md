# SIL Loop R

**[Português](README.md) · [English](README.en.md) · [Español](README.es.md)**

Framework local para transformar ocorrências em aprendizados revisáveis: registre evidências, proponha melhorias, decida em lote e acompanhe a validade das regras.

[Guia de uso](https://inematds.github.io/sil-loop-r/guia/) · [Arquitetura e decisões](docs/architecture.md) · [Skill](skills/sil-loop-r/SKILL.md)

## O que está implementado

- CLI Python sem dependências externas e sem chamadas de API.
- Ocorrências, propostas, experimentos com prazo e regras permanentes com decisão explícita.
- Solicitação de aprovação por frequência em dias, releases ou quantidade de propostas.
- Revisão por idade, ausência de citações e mudança de arquivos associados.
- Promoção das regras vinculantes para um bloco delimitado no AGENTS.md (ou outro arquivo de instrução), vigiada pelo `check`; degrau de proteção e vazamento conhecido por regra (v1.1).
- Histórico de decisões e evidências, armazenamento SQLite transacional e exportação JSON.
- Skill e templates distribuídos no repositório, sem instalação automática.

## Começar

Requer Python 3.10 ou mais recente e Git para clonar. Não exige servidor, conta ou chave.

```bash
git clone https://github.com/inematds/sil-loop-r.git
cd sil-loop-r
python3 sil.py --help
python3 scripts/demo.py
python3 -m unittest discover -s tests -v
```

A demonstração usa um diretório temporário e decisões fictícias identificadas. Não instala nem configura o framework em seus projetos.

Para acompanhar um projeto escolhido por você:

```bash
python3 sil.py --project /caminho/do/projeto init
python3 sil.py --project /caminho/do/projeto occurrence \
  --title "Teste acessou serviço incorreto" \
  --evidence "Log local: a porta já estava ocupada" \
  --cause "Servidor iniciou sem validar a porta"
python3 sil.py --project /caminho/do/projeto lesson \
  --occurrence O0001 --proposal "Abortar quando a porta estiver ocupada" \
  --scope "Inicialização do servidor de testes"
python3 sil.py --project /caminho/do/projeto status
```

Use os IDs retornados pela CLI; O0001 e L0001 são os primeiros IDs de um projeto vazio. Acrescente `--watch caminho/relativo` ao criar uma lição para monitorar arquivos existentes. O framework detecta mudança de conteúdo, não julga automaticamente seu significado.

## Aprovação e frequência

Padrão: solicitar decisão após **7 dias, 2 releases ou 5 novas propostas**, o que ocorrer primeiro. `request` prepara o lote e registra o lembrete; o agente apresenta a pergunta ao usuário. Não há notificações em segundo plano nem envio de mensagens.

```bash
python3 sil.py --project /caminho/do/projeto config \
  --approval-days 7 --approval-releases 2 --approval-batch 5 \
  --review-days 30 --uncited-releases 5
python3 sil.py --project /caminho/do/projeto request
```

Somente depois de aprovação explícita para a proposta:

```bash
python3 sil.py --project /caminho/do/projeto decide L0001 adopt \
  --approved-by "Responsável" --reason "Aprovado após revisar a evidência"
```

Alternativas: `reject`, `defer --until AAAA-MM-DD` ou `trial --until AAAA-MM-DD --criterion "critério verificável"`. Datas precisam ser futuras; a pendência vence no próprio dia. Um experimento permanece identificado como provisório até adoção ou rejeição.

O nome em `--approved-by` é uma declaração registrada, não autenticação. A skill deve respeitar a decisão humana. Nunca aprovar pelo silêncio. Registrar um lembrete não resolve a pendência nem faz `check` passar.

## Evitar regras obsoletas

Regras permanentes são sinalizadas para revisão em **30 dias**, após **5 releases sem citação** ou quando um arquivo associado muda/desaparece. A ausência de uso não retira uma regra automaticamente.

```bash
python3 sil.py --project /caminho/do/projeto context
python3 sil.py --project /caminho/do/projeto check
python3 sil.py --project /caminho/do/projeto review R0001 keep \
  --approved-by "Responsável" --reason "Ainda protege um caso raro; teste revisado"
```

`review` também aceita `revise --text "nova regra"` e `retire`. Cada decisão mantém o histórico. Uma revisão renova a data; alterar o texto ou a impressão dos arquivos invalida o registro anterior de verificação. Mudanças de `review-days` valem na próxima adoção/revisão, sem reescrever datas já registradas.

`cite` registra uma aplicação real da regra. `verify` registra os resultados positivos e negativos de testes já executados; não executa comandos nem certifica que um relato é verdadeiro. Consulte a ajuda dos subcomandos.

## Como o agente participa

Leia ou instale voluntariamente [skills/sil-loop-r/SKILL.md](skills/sil-loop-r/SKILL.md) no seu assistente. No começo, ele consulta `context`; durante o trabalho, registra ocorrências e propõe lições; no fechamento, consulta `status` e apresenta aprovações vencidas. O framework não observa conversas por conta própria nem treina modelos.

Regras não alteram código, hooks ou CI. O arquivo de instrução só muda quando você executa `promote --write` (próxima seção). Uma regra nova não pode substituir as instruções de maior prioridade do usuário.

## Promoção: a regra chega à próxima sessão

Uma regra guardada só no banco não é lida por uma sessão nova. Para cada regra ativa, responda: *quebrar esta regra numa sessão que nunca consulta o SIL causa dano real?* Se sim, marque-a como vinculante. Registre também o degrau de proteção (`prose`, `checklist`, `test`, `probe`, `hook`, `server`) e como ela pode ser contornada.

```bash
python3 sil.py --project /caminho/do/projeto enforce R0001 \
  --binding yes --rung hook --leak "git push --no-verify" \
  --approved-by "Responsável" --reason "Deploy errado derruba o app"
python3 sil.py --project /caminho/do/projeto promote          # mostra o diff, não grava
python3 sil.py --project /caminho/do/projeto promote --write  # grava o bloco no AGENTS.md
```

O bloco fica entre `<!-- sil-loop-r:begin … -->` e `<!-- sil-loop-r:end -->`; o resto do arquivo é preservado. Use `--file CLAUDE.md` (ou outro caminho relativo) se preferir; o último arquivo gravado passa a ser o padrão. No Claude Code, um `CLAUDE.md` cuja primeira linha é `@AGENTS.md` carrega o mesmo bloco.

Depois da primeira regra vinculante, `check` retorna 1 enquanto o bloco estiver ausente, desatualizado (regra revisada, retirada ou desvinculada) ou corrompido, e quando o arquivo não pode ser lido. `status` lista em `prose_binding` as regras vinculantes que ainda dependem só de texto: candidatas a subir um degrau.

Opcional, sem instalação automática: `context --brief` imprime um resumo curto para um hook de início de sessão do seu agente.

## Dados e limites

O estado fica em `.sil/state.sqlite3` dentro do projeto escolhido. Essa pasta é privada por convenção e deve ser ignorada no Git do projeto consumidor. O comando `init` não altera seu `.gitignore`: confira-o antes de publicar. Guarde apenas evidências apropriadas, nunca credenciais ou logs sensíveis.

```bash
python3 sil.py --project /caminho/do/projeto export > historico-sil.json
```

Revise a exportação antes de compartilhar. Para backup restaurável, copie `.sil/state.sqlite3` com a CLI parada. JSON é uma exportação de auditoria; importação/mesclagem ainda não existe. SQLite serializa gravações locais, mas não oferece sincronização entre máquinas ou autenticação multiusuário.

Saídas de `check`: **0** sem pendências vencidas, revisões sinalizadas ou promoção desatualizada; **1** requer decisão, revisão ou `promote --write`; **2** erro de armazenamento, entrada ou configuração. A CLI não instala bloqueios de publicação. Frequências são avaliadas quando alguém executa os comandos; não existe daemon ou agendamento instalado.

## Licença

Código e documentação autorais sob MIT. Materiais privados usados como referência não integram a distribuição.
