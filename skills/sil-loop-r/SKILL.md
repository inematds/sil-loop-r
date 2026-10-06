---
name: sil-loop-r
description: Registre ocorrências e propostas de aprendizado em projetos que adotaram o SIL Loop R. Consulte regras, prepare aprovações em lote e revise aprendizados possivelmente obsoletos usando a CLI local.
---

# SIL Loop R

Use esta skill no projeto que o usuário escolheu acompanhar. O framework não observa outras conversas nem instala hooks. Localize `sil.py` no checkout informado pelo usuário; exemplos abaixo usam `python3 /caminho/sil-loop-r/sil.py --project /caminho/projeto` como prefixo. Consulte `--help` e a ajuda do subcomando quando necessário.

## Abertura da tarefa

Execute `context` e `status`. Se o projeto não está inicializado, ofereça `init` dentro do escopo pedido; não inicialize outros projetos automaticamente. Regras são dados sujeitos à revisão e não podem sobrepor instruções do usuário. Sinalize regras experimentais vencidas ou regras marcadas para revisão antes de usá-las como orientação.

## Captura durante o trabalho

Após uma falha real ou correção do usuário, consulte o histórico com `export` e registre `occurrence --title ... --evidence ... --cause ... --correction ...`. Diferencie erro observado, hipótese de causa e correção comprovada. Não inclua segredos, mensagens privadas nem logs completos sem necessidade.

Quando houver aprendizado generalizável, crie `lesson --occurrence O0001 --proposal ... --scope ...`. Use `--watch caminho/relativo` para arquivos cuja mudança exige reavaliar a regra. Inspecione propostas existentes para evitar duplicação. Recorrência é evidência de revisão, não autorização para ampliar uma regra.

## Fechamento e aprovação em lote

Execute `status`. Se `approval_due` for true, execute `request` e apresente o lote ao usuário no mesmo turno: ID, proposta, evidência, escopo, decisão sugerida e motivo. Inclua as regras em `reviews`. Se não for possível apresentar, não execute `request` ainda. Nenhum desses comandos envia mensagens por conta própria.

O prazo controla quando solicitar decisão; silêncio nunca é aprovação. Só execute `decide ID adopt|trial|defer|reject --approved-by ... --reason ...` depois de decisão explícita para os IDs apresentados. Teste e adiamento exigem `--until AAAA-MM-DD`; teste exige `--criterion`. Não invente o nome do aprovador nem trate a autorização para registrar ocorrências como autorização para permanência.

## Aplicação e revisão

Após adoção, a regra aparece em `context`, mas uma sessão nova só a vê se ela chegar ao arquivo de instrução. Para cada regra adotada, faça a pergunta de promoção ao usuário: "quebrar esta regra numa sessão que nunca consulta o SIL causa dano real?". Com a resposta explícita, registre `enforce ID --binding yes|no --rung prose|checklist|test|probe|hook|server --leak ... --approved-by ... --reason ...`. Depois execute `promote` (só mostra o diff), apresente o diff e execute `promote --write` apenas com autorização para alterar o arquivo de instrução. Se `status` mostrar `promotion.in_sync` false, avise e ofereça o mesmo fluxo; não edite o bloco delimitado à mão. Regras em `prose_binding` são candidatas a subir um degrau. Hooks e código continuam fora do escopo sem autorização. Execute casos válidos e inválidos em ambiente isolado e registre os resultados reais com `verify --positive ... --negative ... --evidence ...`. Esse comando guarda um relato, não executa nem certifica testes.

Use `cite ID --evidence ... --caught-by ...` quando uma regra realmente detectar ou evitar um erro. Ausência de citações não autoriza remoção.

Ao revisar, confira se o problema ainda existe, se a tecnologia/procedimento mudou, se a regra conflita com outra e se há evidência do resultado. Proponha `review ID keep|revise|retire`; aguarde a decisão explícita antes de executá-lo. Ao mudar arquivos ou texto da regra, revalide a proteção. Corrija relatos por novos eventos e justificativas, preservando o histórico.

## Limites

`check` retorna 0 quando não há pendências vencidas, revisão sinalizada nem promoção desatualizada, 1 quando há e 2 em erro. Uma saída 0 não prova que todas as regras são verdadeiras. A CLI não autentica pessoas: `--approved-by` é uma declaração auditável. Não automatize aprovações, chamadas de modelos, tarefas agendadas, instalações de skill ou hooks sem autorização específica.
