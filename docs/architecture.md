# Arquitetura e decisões do SIL Loop R

## Objetivo consolidado

Projeto independente e compartilhável, composto por framework local e skill. O usuário do projeto captura ocorrências com ajuda de um agente e decide quando uma proposta merece virar orientação permanente. A permanência exige revisões: não significa validade eterna.

O projeto não instala integrações no ambiente de quem o desenvolveu. O repositório contém apenas implementação e documentação próprias. Referências privadas não fazem parte da distribuição.

## Divisão de responsabilidades

- Agente: observa o trabalho autorizado, separa fatos de hipóteses, registra evidências e propõe melhorias.
- CLI: valida entradas, preserva estados e histórico, calcula vencimentos e gera a lista de decisões.
- Pessoa responsável: aceita, rejeita, experimenta ou adia propostas; revisa regras permanentes.
- Testes do projeto consumidor: demonstram o comportamento de uma proteção. O framework registra o relato da execução.

Uma ocorrência não é uma lição automática. Uma lição não é uma regra automática. Uma regra escrita não é uma proteção comprovada.

## Modelo de dados

IDs de ocorrência O, lição L, regra R e release V são sequenciais por projeto e nunca reutilizados pela CLI. Lição referencia ocorrência; regra referencia lição. Releases têm nomes únicos, sem depender de datas para ordenação: dois releases no mesmo dia contam separadamente.

Estados de lição: proposed, deferred, trial, adopted, rejected. Estados de regra: trial, active, retired. Testes só terminam com adoção ou rejeição. Regras retiradas permanecem no histórico.

SQLite foi escolhido em lugar de arquivos JSON editados diretamente para garantir transações e serializar gravações simultâneas. A exportação JSON oferece portabilidade de leitura e revisão; não é uma importação automática. Nenhuma dependência externa ou rede é usada pelo núcleo.

## Frequências

Uma fila nova solicita aprovação por dias, quantidade de releases ou lote de propostas. O relógio começa na primeira proposta pendente. `request` registra quando o lote foi preparado e evita repetições no mesmo intervalo; novos lotes, novos vencimentos e novas regras pendentes de revisão podem antecipar outro pedido.

Datas são locais ao computador e vencem inclusive no dia indicado. Um lembrete apresentado não altera o estado de aprovação. `check` continua retornando 1 enquanto houver pendência vencida.

Revisão periódica, ausência de citações e alterações nos arquivos associados são sinais de possível obsolescência. Não provam que uma regra está errada. Uma revisão humana pode manter uma proteção contra um evento raro e grave, com justificativa.

## Limites de confiança

O histórico é transacional, não inviolável: alguém com acesso ao banco pode editá-lo. A CLI registra a identidade declarada; não autentica o aprovador. A skill exige uma decisão explícita na conversa antes de gravar adoção ou revisão.

Evidências são referências textuais fornecidas pelo operador. `verify` não executa comandos, evitando transformar texto armazenado em código. As impressões SHA-256 dos arquivos associados detectam mudança, não validade semântica. Mudança de bibliotecas não associadas a arquivos, novas políticas e alterações externas exigem revisão humana.

Não há interface administrativa, sincronização em nuvem, notificações, chamadas de modelos ou daemon. Hooks e CI podem chamar `check` quando o consumidor decidir integrar; nenhuma integração é instalada pelo projeto.

## Validação

A suíte cobre ciclo completo, decisões inválidas com rollback, prazos inclusivos, lembretes sem aprovação implícita, lotes, releases no mesmo dia, testes temporários, arquivos ausentes/alterados, regras raras, referências inválidas, armazenamento corrompido e captura concorrente. A demonstração executa comandos reais em um diretório temporário.
