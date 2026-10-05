# Instruções do sil-loop-r

Leia context/overview.md, context/current-state.md e tasks/current.md antes de trabalhar.

Respeite as instruções globais do usuário, especialmente a proibição de APIs sem autorização explícita e o uso de agentes pela assinatura.

Produto definido: framework local Python com CLI, templates e skill. Não instalar proteções em outros projetos sem solicitação. APIs não são necessárias.

Validação: `python3 -m unittest discover -s tests -v`. CLI: `python3 sil.py --help`. Manter versão consistente em sil.py e CHANGELOG.md. Não considerar uma proposta de aprendizado regra permanente sem decisão explícita do usuário. A captura de falhas e sugestões pode ser automática pelo agente.

Separe observações da referência, propostas de adaptação e funcionalidades implementadas. Só afirme que uma proteção funciona após teste positivo e negativo.

Referências privadas do usuário ficam fora deste repositório. Não copiar, publicar ou redistribuir arquivos, imagens, transcrições ou conteúdo extraído desse acervo. Usar apenas como referência para trabalho autoral.
