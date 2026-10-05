# Validação da versão 1.0.0

Verificada em 2026-10-05, Python 3.12.3.

- `python3 -m unittest discover -s tests -v`: 16 testes passaram.
- `python3 scripts/demo.py`: PASS, 12 eventos em projeto temporário.
- `python3 scripts/check_site.py`: PT/EN/ES com estrutura e links internos válidos.
- Validador de skill: skill válida.
- Navegador Chromium: PT/EN/ES em 360 e 1366 pixels; nenhum erro JavaScript ou transbordamento horizontal. Tema alterna e persiste; links de idiomas respondem; simulador reage a limite e fila vazia.
- Revisão independente do guia PT: sem bloqueadores materiais.

Limites: a suíte não certifica afirmações registradas como evidência por operadores, nem autentica aprovação humana. Não foi instalado hook, skill ou agendamento no ambiente do autor. Publicação remota depende da criação do repositório e configuração de Pages.
