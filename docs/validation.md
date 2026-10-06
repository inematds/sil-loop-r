# Validação da versão 1.1.0

Verificada em 2026-10-05, Python 3.12.3.

- `python3 -m unittest discover -s tests -v`: 25 testes passaram (16 da 1.0.0 + 9 de promoção).
- Mutação: remover a condição de promoção do `check` derruba 2 testes; ignorar divergência do bloco derruba 3.
- `python3 scripts/demo.py`: PASS, 15 eventos em projeto temporário (inclui enforce, promote e check acusando bloco desatualizado após retirada).
- `python3 scripts/check_site.py`: PT/EN/ES com estrutura e links internos válidos.
- Validador de skill: skill válida.
- Navegador Chromium (servidor HTTP local): PT/EN/ES em 360 e 1366 pixels, sem erro JavaScript nem transbordamento horizontal; fluxo mostra a etapa Promoção.

## Validação da versão 1.0.0

Verificada em 2026-10-05, Python 3.12.3.

- `python3 -m unittest discover -s tests -v`: 16 testes passaram.
- `python3 scripts/demo.py`: PASS, 12 eventos em projeto temporário.
- `python3 scripts/check_site.py`: PT/EN/ES com estrutura e links internos válidos.
- Validador de skill: skill válida.
- Navegador Chromium: PT/EN/ES em 360 e 1366 pixels; nenhum erro JavaScript ou transbordamento horizontal. Tema alterna e persiste; links de idiomas respondem; simulador reage a limite e fila vazia.
- Revisão independente do guia PT: sem bloqueadores materiais.

Limites: a suíte não certifica afirmações registradas como evidência por operadores, nem autentica aprovação humana. Não foi instalado hook, skill ou agendamento no ambiente do autor. Repositório público criado e GitHub Pages configurado via Actions; guias PT/EN/ES responderam HTTP 200. Cadastro enviado aos remotos do portal, buscas e PRO.
