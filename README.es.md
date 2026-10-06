# SIL Loop R

**[Português](README.md) · [English](README.en.md) · [Español](README.es.md)**

Framework local para transformar incidentes en aprendizajes revisables: registra evidencias, propone mejoras, decide en lote y controla la validez de las reglas.

[Guía de uso](https://inematds.github.io/sil-loop-r/guia/es/) · [Arquitectura y decisiones (en portugués)](docs/architecture.md) · [Skill (en portugués)](skills/sil-loop-r/SKILL.md)

## Qué está implementado

- CLI Python sin dependencias externas ni llamadas a APIs.
- Incidentes, propuestas, experimentos con plazo y reglas permanentes con decisión explícita.
- Solicitud de aprobación por frecuencia en días, releases o cantidad de propuestas.
- Revisión por antigüedad, ausencia de citas y cambios en archivos asociados.
- Promoción de las reglas vinculantes a un bloque delimitado en AGENTS.md (u otro archivo de instrucciones), vigilada por `check`; peldaño de protección y fuga conocida por regla (v1.1).
- Historial de decisiones y evidencias, almacenamiento SQLite transaccional y exportación JSON.
- Skill y plantillas distribuidas en el repositorio, sin instalación automática.

## Empezar

Requiere Python 3.10 o posterior y Git para clonar. No exige servidor, cuenta ni clave.

```bash
git clone https://github.com/inematds/sil-loop-r.git
cd sil-loop-r
python3 sil.py --help
python3 scripts/demo.py
python3 -m unittest discover -s tests -v
```

La demostración usa un directorio temporal y decisiones ficticias identificadas. No instala ni configura el framework en tus proyectos.

Para gestionar un proyecto que elijas:

```bash
python3 sil.py --project /caminho/do/projeto init
python3 sil.py --project /caminho/do/projeto occurrence \
  --title "La prueba accedió al servicio incorrecto" \
  --evidence "Registro local: el puerto ya estaba ocupado" \
  --cause "El servidor se inició sin validar el puerto"
python3 sil.py --project /caminho/do/projeto lesson \
  --occurrence O0001 --proposal "Abortar cuando el puerto esté ocupado" \
  --scope "Inicio del servidor de pruebas"
python3 sil.py --project /caminho/do/projeto status
```

Usa los IDs devueltos por la CLI; O0001 y L0001 son los primeros IDs de un proyecto vacío. Añade `--watch caminho/relativo` al crear una lección para supervisar archivos existentes. El framework detecta cambios de contenido, no interpreta automáticamente su significado.

## Aprobación y frecuencia

Valor predeterminado: solicitar una decisión después de **7 días, 2 releases o 5 propuestas nuevas**, lo que ocurra primero. `request` prepara el lote y registra el recordatorio; el agente presenta la pregunta al usuario. No hay notificaciones en segundo plano ni envío de mensajes.

```bash
python3 sil.py --project /caminho/do/projeto config \
  --approval-days 7 --approval-releases 2 --approval-batch 5 \
  --review-days 30 --uncited-releases 5
python3 sil.py --project /caminho/do/projeto request
```

Solo después de una aprobación explícita para la propuesta:

```bash
python3 sil.py --project /caminho/do/projeto decide L0001 adopt \
  --approved-by "Responsable" --reason "Aprobado tras revisar la evidencia"
```

Alternativas: `reject`, `defer --until AAAA-MM-DD` o `trial --until AAAA-MM-DD --criterion "criterio verificable"`. Las fechas deben ser futuras; el asunto pendiente vence el mismo día. Un experimento permanece identificado como provisional hasta su adopción o rechazo.

El nombre en `--approved-by` es una declaración registrada, no una autenticación. La skill debe respetar la decisión humana. Nunca aprobar por silencio. Registrar un recordatorio no resuelve el asunto pendiente ni hace que `check` pase.

## Evitar reglas obsoletas

Las reglas permanentes se señalan para revisión en **30 días**, después de **5 releases sin cita** o cuando un archivo asociado cambia o desaparece. La ausencia de uso no retira una regla automáticamente.

```bash
python3 sil.py --project /caminho/do/projeto context
python3 sil.py --project /caminho/do/projeto check
python3 sil.py --project /caminho/do/projeto review R0001 keep \
  --approved-by "Responsable" --reason "Aún protege un caso poco frecuente; prueba revisada"
```

`review` también acepta `revise --text "nueva regla"` y `retire`. Cada decisión conserva el historial. Una revisión renueva la fecha; modificar el texto o la huella de los archivos invalida el registro anterior de verificación. Los cambios de `review-days` se aplican en la siguiente adopción o revisión, sin reescribir fechas ya registradas.

`cite` registra una aplicación real de la regla. `verify` registra los resultados positivos y negativos de pruebas ya ejecutadas; no ejecuta comandos ni certifica que un relato sea verdadero. Consulta la ayuda de los subcomandos.

## Cómo participa el agente

Lee o instala voluntariamente [skills/sil-loop-r/SKILL.md (en portugués)](skills/sil-loop-r/SKILL.md) en tu asistente. Al inicio, consulta `context`; durante el trabajo, registra incidentes y propone lecciones; al finalizar, consulta `status` y presenta las aprobaciones vencidas. El framework no observa conversaciones por su cuenta ni entrena modelos.

Las reglas no modifican código, hooks ni CI. El archivo de instrucciones solo cambia cuando ejecutas `promote --write` (sección siguiente). Una regla nueva no puede sustituir las instrucciones de mayor prioridad del usuario.

## Promoción: la regla llega a la próxima sesión

Una regla guardada solo en la base de datos no la lee una sesión nueva. Para cada regla activa, pregunta: *¿romper esta regla en una sesión que nunca consulta SIL causa un daño real?* Si es así, márcala como vinculante. Registra también su peldaño de protección (`prose`, `checklist`, `test`, `probe`, `hook`, `server`) y cómo puede eludirse.

```bash
python3 sil.py --project /ruta/del/proyecto enforce R0001 \
  --binding yes --rung hook --leak "git push --no-verify" \
  --approved-by "Responsable" --reason "Un deploy equivocado rompe la app"
python3 sil.py --project /ruta/del/proyecto promote          # muestra el diff, no escribe
python3 sil.py --project /ruta/del/proyecto promote --write  # escribe el bloque en AGENTS.md
```

El bloque queda entre `<!-- sil-loop-r:begin … -->` y `<!-- sil-loop-r:end -->`; el resto del archivo se conserva. Usa `--file CLAUDE.md` (u otra ruta relativa) si prefieres; el último archivo escrito pasa a ser el predeterminado. En Claude Code, un `CLAUDE.md` cuya primera línea es `@AGENTS.md` carga el mismo bloque.

Desde la primera regla vinculante, `check` devuelve 1 mientras el bloque falte, esté desactualizado (regla revisada, retirada o desvinculada) o corrupto, y cuando el archivo no puede leerse. `status` enumera en `prose_binding` las reglas vinculantes que aún dependen solo de texto: candidatas a subir un peldaño.

Opcional, nunca se instala automáticamente: `context --brief` imprime un resumen corto para el hook de inicio de sesión de tu agente.

## Datos y límites

El estado se guarda en `.sil/state.sqlite3` dentro del proyecto elegido. Esta carpeta es privada por convención y debe ignorarse en el Git del proyecto que lo utiliza. El comando `init` no modifica tu `.gitignore`: compruébalo antes de publicar. Guarda solo evidencias apropiadas, nunca credenciales ni registros sensibles.

```bash
python3 sil.py --project /caminho/do/projeto export > historico-sil.json
```

Revisa la exportación antes de compartirla. Para una copia de seguridad restaurable, copia `.sil/state.sqlite3` con la CLI detenida. JSON es una exportación de auditoría; todavía no existe importación ni combinación de datos. SQLite serializa las escrituras locales, pero no ofrece sincronización entre máquinas ni autenticación multiusuario.

Salidas de `check`: **0** sin asuntos pendientes vencidos, revisiones señaladas ni promoción desactualizada; **1** requiere decisión, revisión o `promote --write`; **2** error de almacenamiento, entrada o configuración. La CLI no instala bloqueos de publicación. Las frecuencias se evalúan cuando alguien ejecuta los comandos; no existe un daemon ni una programación instalada.

## Licencia

Código y documentación originales bajo MIT. Los materiales privados utilizados como referencia no forman parte de la distribución.
