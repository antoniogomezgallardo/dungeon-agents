# Plan de Pruebas — Dungeon Agents (M1-M6)

> **Documento:** Plan de pruebas funcional y exploratorio  
> **Alcance:** Milestones M1 a M6 (completados a fecha 2026-07-12)  
> **Proyecto:** Dungeon Agents — consola RPG en Python para aprender patrones de
> agentes de IA; puente a QA/TestOps AI  
> **Autor:** Antonio Gomez Gallardo

---

## Tabla de contenidos

1. [Introduccion y alcance](#1-introduccion-y-alcance)
2. [Entorno y precondiciones](#2-entorno-y-precondiciones)
3. [Estrategia de pruebas](#3-estrategia-de-pruebas)
4. [Casos de prueba](#4-casos-de-prueba)
   - 4.1 [Arranque y configuracion](#41-arranque-y-configuracion)
   - 4.2 [Meta-comandos deterministicos](#42-meta-comandos-deterministicos)
   - 4.3 [Persistencia y sesion](#43-persistencia-y-sesion)
   - 4.4 [Reglas de dominio — inventario y recursos](#44-reglas-de-dominio--inventario-y-recursos)
   - 4.5 [Mecanica de dados y skill_check](#45-mecanica-de-dados-y-skill_check)
   - 4.6 [Coordinacion multi-agente](#46-coordinacion-multi-agente)
   - 4.7 [Fin de partida](#47-fin-de-partida)
   - 4.8 [Robustez y casos limite](#48-robustez-y-casos-limite)
   - 4.9 [Portabilidad Windows](#49-portabilidad-windows)
5. [Matriz de trazabilidad](#5-matriz-de-trazabilidad)
6. [Notas sobre no-determinismo](#6-notas-sobre-no-determinismo)
7. [Registro de resultados](#7-registro-de-resultados)

---

## 1. Introduccion y alcance

### Que se prueba

Este plan cubre la totalidad de la aplicacion **Dungeon Agents** hasta la version
actual, correspondiente a los Milestones M1 a M6 inclusive:

| Milestone | Funcionalidad |
|-----------|---------------|
| M1 | Loop de juego, agente Game Master, salida por consola |
| M2 | Herramientas deterministicas: dados, guardado/carga de estado |
| M3 | Modelos Pydantic validados (Player, Quest, GameState, ActionResult) |
| M4 | Reglas de dominio: inventario, oro, HP, condiciones de victoria/derrota |
| M5 | Gestion de sesion: persistencia unificada, meta-comandos, modo debug, UX |
| M6 | Arquitectura multi-agente: Rules Referee, Lore Keeper, Critic, pipeline de revision |

### Que NO se prueba (fuera de alcance)

- M7 (guardrails y restricciones de seguridad): no implementado.
- M8 (evaluacion automatizada con LLM-as-a-judge): no implementado.
- M9 (puente a QA/TestOps AI): no implementado.
- Comportamiento de los modelos LLM de forma aislada: el proyecto no intenta
  testear a Anthropic ni a OpenAI; solo prueba que la aplicacion se comporta
  correctamente dadas las respuestas del modelo.
- Rendimiento bajo carga o uso concurrente: fuera de alcance para un juego de
  consola de un solo jugador.

### Objetivo del plan

Garantizar que un colaborador nuevo o el propio autor pueda validar la
aplicacion de principio a fin con criterios claros, distinguiendo que se puede
verificar de forma automatica (sin API key) de lo que requiere ejecucion manual
con el modelo real.

---

## 2. Entorno y precondiciones

### 2.1 Instalacion del entorno

```powershell
# Desde la raiz del repositorio
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell (requiere RemoteSigned)
pip install -e ".[dev]"
```

`.venv/` esta en `.gitignore` y nunca se commitea. `pytest` viene incluido en el
extra `[dev]`.

### 2.2 Variables de entorno

Copia `.env.example` a `.env` (en la raiz del repo) y rellena segun el
proveedor que vayas a usar:

```
# Para Anthropic (proveedor por defecto)
ANTHROPIC_API_KEY=sk-ant-...

# Para OpenAI
OPENAI_API_KEY=sk-...
```

Variables adicionales (todas opcionales):

| Variable | Valores validos | Efecto |
|---|---|---|
| `DUNGEON_PROVIDER` | `anthropic` (defecto), `openai` | Selecciona el proveedor LLM |
| `DUNGEON_MODEL` | cualquier ID de modelo | Anula el modelo por defecto del proveedor |
| `DUNGEON_DEBUG` | `1`, `true`, `yes`, `on` | Arranca el juego en modo debug |

Si `DUNGEON_PROVIDER` tiene un valor desconocido, la aplicacion lo ignora y
usa el proveedor por defecto (`anthropic`) sin lanzar error
(`config.py:80-81`).

### 2.3 Modelos por defecto

- Anthropic: `claude-haiku-4-5` (`config.py:36`)
- OpenAI: `gpt-4o-mini` (`config.py:37`)

### 2.4 Modos de operacion

**Modo sin API key** (tests deterministicos):
- `python -m pytest -m "not llm"` ejecuta los 119 tests existentes sin
  necesitar ninguna API key ni acceso a red.
- El propio juego (`dungeon-agents`) muestra un mensaje de error claro y sale
  sin colgarse si falta la key.

**Modo con API key** (juego completo):
- Arranca con `dungeon-agents` (o `python -m dungeon_agents`).
- Requiere la API key del proveedor seleccionado.
- El primer arranque tarda ~20 s en cargar el SDK (se muestra un spinner).

### 2.5 Estado inicial limpio

Para algunos casos de prueba conviene arrancar sin guardado previo. El estado
se guarda en `data/game_state.json` (carpeta ignorada por git). Para borrar:

```powershell
Remove-Item "data\game_state.json" -ErrorAction SilentlyContinue
```

O bien usar el comando `new` dentro del juego.

### 2.6 Activar modo debug

Dos formas equivalentes:
- `DUNGEON_DEBUG=1 dungeon-agents` (antes de arrancar)
- Escribir `debug` dentro del juego (toggle en caliente)

---

## 3. Estrategia de pruebas

La aplicacion implementa conscientemente dos capas de prueba con propiedades
muy distintas:

### 3.1 Capa A — Pruebas automaticas deterministicas (sin API key)

**Como ejecutar:**
```powershell
python -m pytest -m "not llm"          # suite completa determinista
python -m pytest tests/test_dice.py    # un modulo concreto
python -m pytest -v                    # verboso
```

**Que valida:**
- Toda la capa `domain/` (dice, rules, models, state): funciones puras, sin
  dependencias externas.
- Los contratos de instrucciones de los agentes (el texto de los prompts
  en constantes de modulo, sin llamar al modelo).
- La logica del loop principal donde es inyectable (p. ej. `_check_end_of_game`
  acepta un `GameState` directamente; los tests lo usan sin tocar disco ni modelo).

**Oraculo:** fuerte. Dado un input concreto, el resultado esperado es exacto y
determinista. Estas pruebas pueden fallar solo si el codigo cambia.

**Cobertura actual:** 119 tests, todos pasando sin API key.

| Modulo | Tests | Archivo |
|--------|-------|---------|
| Humo / configuracion | 10 | `test_smoke.py` |
| Dados y skill_check | 12 | `test_dice.py` |
| Persistencia | 9 | `test_state.py` |
| Modelos Pydantic | 21 | `test_models.py` |
| Reglas de dominio | 29 | `test_rules.py` |
| Contrato Rules Referee | 7 | `test_rules_referee.py` |
| Contrato Lore Keeper | 5 | `test_lore_keeper.py` |
| Contrato Critic | 6 | `test_critic.py` |
| Fin de partida | 5 | `test_end_of_game.py` |

### 3.2 Capa B — Pruebas manuales del comportamiento de agentes (con API key)

**Como ejecutar:** lanzar el juego (`dungeon-agents`) y jugar sesiones
dirigidas siguiendo los casos de esta seccion.

**Que valida:**
- Que el Game Master, el Rules Referee, el Lore Keeper y el Critic se coordinan
  correctamente en tiempo de ejecucion.
- Que los meta-comandos deterministicos muestran los datos correctos despues de
  que los agentes han modificado el estado.
- Que el pipeline Critic (generar -> revisar -> regenerar) funciona de extremo a
  extremo.
- Comportamientos emergentes que solo existen con respuestas reales del modelo.

**Oraculo:** debil (vease seccion 6). No se verifica igualdad exacta de texto;
se verifican *propiedades*: el estado persitido es correcto, el meta-comando
muestra el valor exacto guardado, la regla aplicada es la que corresponde.

### 3.3 Por que esta distincion importa

El problema del oraculo en sistemas con LLM: no existe un unico "texto correcto"
que el modelo deba producir. Lo que si existe son *hechos verificables*: el HP
guardado en `data/game_state.json` tras un combate, el contenido del inventario,
si el juego termino o continuo. La estrategia de pruebas de este proyecto separa
intencionadamente:

- Lo que **DEBE** ocurrir (resultado de reglas, persistencia, meta-comandos)
  -> codigo determinista, tests automaticos, oraculo fuerte.
- Lo que **PROBABLEMENTE** ocurra (narracion coherente, uso correcto de tools
  por el modelo, seguimiento de instrucciones) -> pruebas manuales, oraculo
  debil, medicion de tasa de cumplimiento.

Esta separacion es la misma que necesitara TestOps AI: las reglas de negocio se
verifican con tests, los comportamientos emergentes se evaluan con LLM-as-judge
(M8).

---

## 4. Casos de prueba

Convencion de IDs:
- `DA-CFG-xx` — Configuracion y arranque
- `DA-CMD-xx` — Meta-comandos
- `DA-PER-xx` — Persistencia y sesion
- `DA-REG-xx` — Reglas de dominio
- `DA-DAD-xx` — Dados y skill_check
- `DA-MAG-xx` — Coordinacion multi-agente
- `DA-FIN-xx` — Fin de partida
- `DA-ROB-xx` — Robustez y casos limite
- `DA-WIN-xx` — Portabilidad Windows

Tipo:
- **[AUTO]** — ejecutable sin API key con `pytest`
- **[MANUAL]** — requiere juego en vivo con API key

---

### 4.1 Arranque y configuracion

#### DA-CFG-01 — Arranque sin API key muestra mensaje claro y sale [AUTO]

**Objetivo:** verificar que la ausencia de API key no cuelga la aplicacion.  
**Precondicion:** eliminar/dejar vacia la variable del proveedor activo.  
**Pasos:**
1. `monkeypatch.delenv("ANTHROPIC_API_KEY")` (o dejarlo sin fichero `.env`).
2. Instanciar `load_settings()` y comprobar `settings.has_api_key is False`.
3. Ejecutar el juego manualmente sin `.env`.

**Resultado esperado:**  
- `settings.has_api_key` devuelve `False` (verificado en `test_smoke.py`).
- El juego imprime `No ANTHROPIC_API_KEY found.` (o la variable del proveedor
  activo) junto con instrucciones para crear `.env`, y retorna sin colgarse
  (`main.py:367-374`).

**Referencia:** `src/dungeon_agents/config.py:61-63`, `src/dungeon_agents/main.py:367-374`

---

#### DA-CFG-02 — Proveedor por defecto es Anthropic con modelo claude-haiku-4-5 [AUTO]

**Objetivo:** verificar defaults correctos cuando no se define `DUNGEON_PROVIDER`.  
**Pasos:** ejecutar `python -m pytest tests/test_smoke.py::test_default_provider_and_model`.  
**Resultado esperado:** `settings.provider == "anthropic"` y `settings.model == "claude-haiku-4-5"`.

---

#### DA-CFG-03 — Proveedor OpenAI selecciona OPENAI_API_KEY y gpt-4o-mini [AUTO]

**Objetivo:** verificar que la seleccion del proveedor cambia la key y el modelo.  
**Pasos:** `DUNGEON_PROVIDER=openai OPENAI_API_KEY=sk-test` + `load_settings()`.  
**Resultado esperado:** `provider == "openai"`, `model == "gpt-4o-mini"`, `api_key == "sk-test"`.

**Referencia:** `src/dungeon_agents/config.py:35-44`

---

#### DA-CFG-04 — Proveedor desconocido cae al defecto sin crash [AUTO]

**Objetivo:** robustez ante valores invalidos en `DUNGEON_PROVIDER`.  
**Pasos:** `DUNGEON_PROVIDER=banana` + `load_settings()`.  
**Resultado esperado:** `provider == "anthropic"` (sin excepcion).

---

#### DA-CFG-05 — DUNGEON_MODEL anula el modelo por defecto [AUTO]

**Objetivo:** el override de modelo funciona independientemente del proveedor.  
**Pasos:** `DUNGEON_PROVIDER=anthropic DUNGEON_MODEL=claude-sonnet-4-6` + `load_settings()`.  
**Resultado esperado:** `settings.model == "claude-sonnet-4-6"`.

---

#### DA-CFG-06 — DUNGEON_DEBUG activa el modo debug [AUTO]

**Objetivo:** verificar que los valores truthy de `DUNGEON_DEBUG` lo activan y los demas no.  
**Pasos:** ejecutar `python -m pytest tests/test_smoke.py::test_debug_flag_reads_truthy_env`.  
**Resultado esperado:** `DUNGEON_DEBUG=1` -> `debug is True`; `DUNGEON_DEBUG=off` -> `debug is False`.

**Referencia:** `src/dungeon_agents/config.py:48`, constantes `_TRUTHY = {"1", "true", "yes", "on"}`.

---

#### DA-CFG-07 — Banner de arranque muestra proveedor, modelo y estado de debug [MANUAL]

**Objetivo:** confirmar que el panel de bienvenida refleja la configuracion real.  
**Precondicion:** API key presente.  
**Pasos:**
1. `DUNGEON_DEBUG=1 dungeon-agents`.
2. Observar el panel verde de bienvenida.

**Resultado esperado:** El panel muestra `anthropic - claude-haiku-4-5  |  debug ON`
(o el proveedor/modelo configurados). Si debug esta apagado, la parte `| debug ON`
no aparece (`main.py:390-399`).

---

#### DA-CFG-08 — Spinner durante la carga del SDK [MANUAL]

**Objetivo:** verificar que el arranque no parece colgarse en el primer import del SDK.  
**Pasos:** borrar la cache de Python (`.pyc`) y arrancar el juego con API key por primera vez.  
**Resultado esperado:** aparece el mensaje de estado `Loading the game engine (first run can take a moment)` durante los ~20 s de carga inicial, antes del banner (`main.py:380`).

---

### 4.2 Meta-comandos deterministicos

Todos los meta-comandos leen directamente el `GameState` guardado en disco;
nunca preguntan al modelo. El resultado es exacto y repetible.

**Precondicion comun:** tener una sesion activa con estado guardado (haberse
comunicado con el GM al menos una vez, o haber lanzado `new`).

---

#### DA-CMD-01 — Comando `stats` muestra HP, gold, location y quest desde el estado [MANUAL]

**Objetivo:** verificar que `stats` es determinista y no improvisado.  
**Pasos:**
1. Jugar hasta que el GM haya asignado una location y quest (observar en debug
   que el Lore Keeper llamo a `set_location` y `set_quest`).
2. Escribir `stats`.

**Resultado esperado:** panel azul "Stats" con el nombre del personaje,
`HP: X/100`, `Gold: Y`, `Where: <location>`, `Quest: <quest>` — valores identicos
a los almacenados en `data/game_state.json`. Si la location aun no se ha
establecido, aparece `not set yet` (comportamiento correcto, no un fallo).

**Resultado inesperado (fallo):** los valores difieren del JSON, o el panel muestra
valores que el GM invento sin llamar al tool.

**Referencia:** `src/dungeon_agents/main.py:105-138`, `src/dungeon_agents/domain/state.py:91-109`

---

#### DA-CMD-02 — Alias `status` es equivalente a `stats` [MANUAL]

**Pasos:** escribir `status` en lugar de `stats`.  
**Resultado esperado:** identico a DA-CMD-01.

**Referencia:** `src/dungeon_agents/main.py:27` (`STATS_WORDS = {"stats", "status", "/stats"}`)

---

#### DA-CMD-03 — Comando `inventory` muestra solo el inventario [MANUAL]

**Objetivo:** `inventory` llama a `_print_status(inventory_only=True)` — sin panel de stats.  
**Precondicion:** haber adquirido algun objeto durante la sesion.  
**Pasos:** escribir `inventory` (o `inv`).  
**Resultado esperado:** panel azul "Inventory" con los objetos y cantidades
exactas del estado guardado. Sin panel "Stats" de HP/gold.

**Referencia:** `src/dungeon_agents/main.py:138`, `src/dungeon_agents/domain/rules.py:34-43`

---

#### DA-CMD-04 — Comando `summary` muestra la narracion acumulada (o placeholder) [MANUAL]

**Pasos:** escribir `summary` (o `recap`).  
**Resultado esperado:** panel cyan "Story so far" con el texto de `session_summary`
del estado guardado. Si aun no hay resumen, muestra `Nothing notable has happened
yet.` — nunca un texto inventado en tiempo real.

**Referencia:** `src/dungeon_agents/main.py:140-153`

---

#### DA-CMD-05 — Meta-comandos re-muestran la ultima escena tras ejecutarse [MANUAL]

**Objetivo:** verificar que tras cualquier meta-comando (salvo `exit`) el jugador
recupera su contexto sin perder el lugar.  
**Pasos:**
1. Recibir una escena del GM.
2. Escribir `stats`, luego `inventory`, luego `summary`, luego `help`.

**Resultado esperado:** despues de cada meta-comando se reimprime la ultima escena
del GM. El jugador puede continuar jugando desde el mismo punto (`main.py:476-500`).

---

#### DA-CMD-06 — Comando `help` muestra el panel de ayuda y los comandos existentes [MANUAL]

**Pasos:** escribir `help` (o `?`).  
**Resultado esperado:** panel amarillo "Help" con los comandos `stats`, `inventory`,
`summary`, `help`, `save`, `new`, `debug`, `exit` listados con sus alias (`main.py:49-95`).
No consume un turno de juego.

---

#### DA-CMD-07 — Comando `debug` alterna el modo debug en caliente [MANUAL]

**Pasos:**
1. Arrancar sin `DUNGEON_DEBUG`.
2. Escribir `debug` -> aparece `Debug mode ON.`
3. Jugar un turno -> se ven mensajes `[debug] agent ... is working` y tiempos de tool.
4. Escribir `debug` -> aparece `Debug mode OFF.`
5. Jugar otro turno -> sin mensajes de debug.

**Resultado esperado:** el toggle funciona en caliente sin reiniciar el juego;
los hooks existentes leen el estado mutable `DebugState` sin necesidad de
reconstruir el agente (`main.py:310-319`, `main.py:504-510`).

---

#### DA-CMD-08 — Comando `exit` termina el juego inmediatamente [MANUAL]

**Pasos:** escribir `exit` (o `quit`).  
**Resultado esperado:** mensaje `Farewell, adventurer.` y retorno al shell sin
spinner de carga ni errores. El estado guardado se conserva en disco.

---

#### DA-CMD-09 — Entrada vacia no consume turno [MANUAL]

**Pasos:** pulsar Enter sin escribir nada.  
**Resultado esperado:** la aplicacion vuelve al prompt de input sin enviar nada
al GM y sin mostrar ninguna escena nueva (`main.py:511-512`).

---

### 4.3 Persistencia y sesion

#### DA-PER-01 — Guardado round-trip: estado guardado carga identico [AUTO]

**Objetivo:** save + load devuelve el mismo `GameState` por valor.  
**Pasos:** ejecutar `python -m pytest tests/test_state.py::test_save_state_then_load_state_roundtrips`.  
**Resultado esperado:** los modelos Pydantic son iguales por valor.

**Referencia:** `src/dungeon_agents/domain/state.py:51-65`

---

#### DA-PER-02 — Archivo de estado se crea en el directorio `data/` [AUTO]

**Pasos:** `python -m pytest tests/test_state.py::test_save_creates_the_file_in_the_data_dir`.  
**Resultado esperado:** el fichero `game_state.json` existe en la carpeta indicada.

---

#### DA-PER-03 — Carga sin fichero devuelve None (no crash) [AUTO]

**Pasos:** `python -m pytest tests/test_state.py::test_load_state_with_no_save_returns_none`.  
**Resultado esperado:** `load_state()` devuelve `None`.

---

#### DA-PER-04 — Estado incompatible se descarta con gracia por `load_state_or_none` [AUTO]

**Objetivo:** un guardado del formato antiguo (pre-M5) no crashea el tool; se
descarta silenciosamente y se trata como "sin guardado".  
**Pasos:** `python -m pytest tests/test_state.py::test_load_state_or_none_discards_incompatible_save`.  
**Resultado esperado:** `load_state_or_none()` devuelve `None` sin `StateError`.

**Referencia:** `src/dungeon_agents/domain/state.py:91-109`

---

#### DA-PER-05 — `clear_state` borra el fichero; segunda llamada es no-op [AUTO]

**Pasos:** `python -m pytest tests/test_state.py::test_clear_state_removes_the_save tests/test_state.py::test_clear_state_is_safe_when_no_save`.  
**Resultado esperado:** ambas pasan sin excepcion.

---

#### DA-PER-06 — Resume de sesion: banner de recap y ultima escena verbatim [MANUAL]

**Objetivo:** al reanudar, el juego muestra el resumen de sesion y la ultima
escena exacta que el jugador vio — sin improvisar.  
**Precondicion:** haber jugado al menos un turno (estado guardado con `last_scene`).  
**Pasos:**
1. Jugar un turno. Anotar el texto exacto de la ultima escena del GM.
2. Salir con `exit`.
3. Arrancar de nuevo.

**Resultado esperado:**
- Panel cyan "Recap" con nombre/location/HP/gold/quest y `session_summary`.
- A continuacion, la ultima escena del GM *verbatim* (texto identico al anotado).
- El GM continua la aventura sin reiniciarla (porque recibe `RESUME_PROMPT`,
  `main.py:34-35`).

**Referencia:** `src/dungeon_agents/main.py:288-302`, `main.py:409-417`

---

#### DA-PER-07 — Comando `new` descarta el guardado y comienza partida fresca [MANUAL]

**Objetivo:** `new` borra el estado actual y siembra uno nuevo desde cero.  
**Pasos:**
1. Jugar varios turnos con oro, inventario y HP modificados.
2. Escribir `new`.
3. Escribir `stats`.

**Resultado esperado:**
- Mensaje `Starting a new adventure...`
- El panel Stats muestra el heroe `Adventurer` con HP 100/100, gold 0 e
  inventario vacio (el estado inicial que genera `new_game_state()`, `game_tools.py:24-32`).
- El historial de conversacion se resetea; el GM introduce una nueva apertura.

---

#### DA-PER-08 — HP y oro se conservan tras recargar la sesion [MANUAL]

**Objetivo:** los cambios de recursos persisten entre sesiones (el fix de M6
que garantiza que `change_hp`/`earn_gold`/`spend_gold` siempre persisten antes
de que el Critic revise la escena).  
**Pasos:**
1. En una sesion, provocar que el GM aplique dano o recompensa de oro
   (p.ej. "I get attacked by a goblin"; verificar en debug que el Referee
   llamo a `change_hp`).
2. Anotar HP y oro del comando `stats`.
3. Salir con `exit`.
4. Reiniciar el juego y usar `stats`.

**Resultado esperado:** los valores de HP y oro son exactamente los mismos en
ambas sesiones.

---

#### DA-PER-09 — Estado esquema invalido es rechazado por `load_state` con `StateError` [AUTO]

**Pasos:** `python -m pytest tests/test_state.py::test_load_state_rejects_schema_mismatch`.  
**Resultado esperado:** un JSON con `hp: -50` lanza `StateError`.

---

### 4.4 Reglas de dominio — inventario y recursos

Todos los casos de esta seccion tienen contraparte automatica en `test_rules.py`.
Los casos marcados `[MANUAL]` verifican que el agente aplica correctamente las
reglas en el contexto del juego real.

#### DA-REG-01 — Inventario vacio muestra texto descriptivo [AUTO]

**Pasos:** `python -m pytest tests/test_rules.py::test_get_inventory_empty`.  
**Resultado esperado:** `"The inventory is empty."`

---

#### DA-REG-02 — Anadir item actualiza la cantidad correctamente [AUTO]

**Pasos:** `python -m pytest tests/test_rules.py::test_add_item_to_empty_inventory tests/test_rules.py::test_add_item_stacks_existing`.  
**Resultado esperado:** el item aparece con la cantidad correcta; si ya existe,
se apila (case-insensitive).

---

#### DA-REG-03 — Las reglas son funciones puras: el estado de entrada no muta [AUTO]

**Pasos:** `python -m pytest tests/test_rules.py::test_add_item_does_not_mutate_input_state tests/test_rules.py::test_remove_item_does_not_mutate_input_state tests/test_rules.py::test_spend_gold_does_not_mutate_input_state tests/test_rules.py::test_change_hp_does_not_mutate_input_state`.  
**Resultado esperado:** los cuatro tests pasan; el estado original permanece intacto.

---

#### DA-REG-04 — No se puede quitar un item que no se tiene [AUTO]

**Objetivo:** la regla de inventario falla de forma segura con mensaje amigable.  
**Pasos:** `python -m pytest tests/test_rules.py::test_cannot_remove_item_you_dont_have`.  
**Resultado esperado:** `result.success is False`, `"don't have"` en el mensaje,
`result.new_state is None`.

---

#### DA-REG-05 — No se puede quitar mas cantidad de la que se lleva [AUTO]

**Pasos:** `python -m pytest tests/test_rules.py::test_cannot_remove_more_than_you_carry`.  
**Resultado esperado:** `success is False`, mensaje contiene `"only have 2"`.

---

#### DA-REG-06 — El GM no puede quitar items que el jugador no tiene [MANUAL]

**Objetivo:** la regla `remove_item` deniega incluso cuando el modelo intenta
hacer que el jugador use algo que no tiene.  
**Pasos:**
1. No recoger ninguna antorcha.
2. Decir al GM: "I use my torch to light the way."

**Resultado esperado:** el GM narra que el jugador no tiene antorcha (porque el
tool `remove_item` devolvio `"You don't have any Torch to remove."` y el GM
debe narrar esa restriccion).

---

#### DA-REG-07 — No se puede gastar mas oro del que se tiene [AUTO + MANUAL]

**[AUTO]:** `python -m pytest tests/test_rules.py::test_cannot_spend_more_gold_than_you_have`.  
**Resultado esperado:** `success is False`, `"only have 3 gold"` en el mensaje.

**[MANUAL]:** en el juego, intentar comprar algo que cuesta mas que el oro disponible.  
**Resultado esperado:** el GM narra que el jugador no puede permitirse la compra
(el Referee llamo a `check_can_afford` y recibio la negacion del codigo).

---

#### DA-REG-08 — El HP se clampea: no puede ser negativo ni superar el maximo [AUTO]

**Pasos:** `python -m pytest tests/test_rules.py::test_hp_cannot_go_below_zero tests/test_rules.py::test_hp_cannot_exceed_max`.  
**Resultado esperado:**
- Dano de 999 en HP=10 deja HP=0 y el mensaje incluye `"fallen"`.
- Curacion de 999 en HP=95 deja HP=100 (MAX_HP).

**Referencia:** `src/dungeon_agents/domain/rules.py:226-245` (`max(0, min(player.hp + delta, player.max_hp))`)

---

#### DA-REG-09 — `check_can_afford` es read-only: no muta el estado [AUTO]

**Pasos:** `python -m pytest tests/test_rules.py::test_can_afford_does_not_mutate_state`.  
**Resultado esperado:** tras llamar a `can_afford`, el oro e inventario son identicos a antes.

---

#### DA-REG-10 — Stack de item se elimina cuando llega a cero [AUTO]

**Pasos:** `python -m pytest tests/test_rules.py::test_remove_item_drops_stack_at_zero`.  
**Resultado esperado:** la lista de inventario queda vacia; no queda un item con `quantity=0`.

---

### 4.5 Mecanica de dados y skill_check

#### DA-DAD-01 — El resultado de `roll_dice` esta siempre en [1, sides] [AUTO]

**Pasos:** `python -m pytest tests/test_dice.py::test_roll_is_within_bounds`.  
**Resultado esperado:** 1000 tiradas de d20; todas en [1, 20].

---

#### DA-DAD-02 — `roll_dice` con RNG inyectado es reproducible [AUTO]

**Pasos:** `python -m pytest tests/test_dice.py::test_roll_is_reproducible_with_seeded_rng`.  
**Resultado esperado:** dos tiradas con `random.Random(42)` producen el mismo valor.

---

#### DA-DAD-03 — Valores fuera de rango ([2, 100]) lanzan `InvalidDiceError` [AUTO]

**Pasos:** `python -m pytest tests/test_dice.py::test_out_of_range_sides_are_rejected`.  
**Resultado esperado:** `sides` en {1, 0, -5, 101, 1000} lanzan `InvalidDiceError`.

**Referencia:** `src/dungeon_agents/domain/dice.py:19-23` (`MIN_SIDES=2, MAX_SIDES=100`)

---

#### DA-DAD-04 — Tipos no enteros (float, str, bool, None) son rechazados [AUTO]

**Pasos:** `python -m pytest tests/test_dice.py::test_non_integer_sides_are_rejected`.  
**Resultado esperado:** todos lanzan `InvalidDiceError` (incluido `True`, que es
subclase de `int` pero se rechaza explicitamente, `dice.py:41-42`).

---

#### DA-DAD-05 — `resolve_check` decide exito en codigo: roll >= threshold [AUTO]

**Pasos:** `python -m pytest tests/test_dice.py::test_check_succeeds_when_roll_meets_threshold tests/test_dice.py::test_check_fails_when_roll_below_threshold tests/test_dice.py::test_check_success_is_meet_or_exceed`.  
**Resultado esperado:** exito cuando roll >= threshold (>=, no >); fallo cuando roll < threshold.

**Referencia:** `src/dungeon_agents/domain/dice.py:67-73` (umbrales: trivial=3, easy=5, moderate=10, hard=15, very_hard=18)

---

#### DA-DAD-06 — Dificultad desconocida en `resolve_check` lanza `InvalidDifficultyError` [AUTO]

**Pasos:** `python -m pytest tests/test_dice.py::test_check_rejects_unknown_difficulty`.  
**Resultado esperado:** `resolve_check("impossible")` lanza `InvalidDifficultyError`.

---

#### DA-DAD-07 — Los nombres de dificultad son case-insensitive [AUTO]

**Pasos:** `python -m pytest tests/test_dice.py::test_check_difficulty_is_case_insensitive`.  
**Resultado esperado:** `resolve_check("MODERATE")` funciona y normaliza a `"moderate"`.

---

#### DA-DAD-08 — El Referee no inventa el resultado de una tirada [MANUAL]

**Objetivo:** verificar que en una accion incierta el Referee llama a `skill_check`
y el resultado viene del codigo, no de la narracion del modelo.  
**Precondicion:** modo debug activo.  
**Pasos:**
1. Intentar una accion incierta ("I try to pick the lock").
2. Observar los mensajes de debug.

**Resultado esperado:** aparece una linea `[debug] Rules Referee -> tool skill_check...`
seguida de `[debug] skill_check -> SUCCESS/FAILURE: rolled X on 1d20 vs moderate (needs 10+).`
El narrador describe el resultado que el tool devolvio, no uno inventado.

---

#### DA-DAD-09 — El tool `skill_check` expuesto al Referee devuelve formato legible [AUTO indirecto]

**Objetivo:** verificar el formato de respuesta del tool wrapper.  
**Pasos (indirectos):** leer `src/dungeon_agents/tools/game_tools.py:219-241` y
ejecutar `python -m pytest tests/test_dice.py` para confirmar que la logica
subyacente es correcta.  
**Resultado esperado:** la cadena devuelta tiene el formato
`"SUCCESS: rolled 14 on 1d20 vs moderate (needs 10+)."` o `"FAILURE: ..."`.

---

### 4.6 Coordinacion multi-agente

#### DA-MAG-01 — El GM tiene `rules_referee` y `lore_keeper` en su lista de tools [AUTO]

**Objetivo:** verificar el contrato de instrucciones del Game Master.  
**Pasos:** `python -m pytest tests/test_rules_referee.py::test_game_master_consults_the_referee tests/test_lore_keeper.py::test_game_master_delegates_world_sync_to_lore_keeper`.  
**Resultado esperado:** ambos tests pasan; las instrucciones del GM mencionan
`rules_referee` y `lore_keeper` como tools a consultar.

---

#### DA-MAG-02 — El Referee no narra ni tiene herramientas narrativas [AUTO]

**Pasos:** `python -m pytest tests/test_rules_referee.py::test_referee_is_an_arbiter_not_a_narrator`.  
**Resultado esperado:** las instrucciones del Referee contienen `"do not narrate"` (o equivalente).

---

#### DA-MAG-03 — El Lore Keeper no tira dados ni toca recursos [AUTO]

**Pasos:** `python -m pytest tests/test_lore_keeper.py::test_lore_keeper_does_not_narrate_or_arbitrate`.  
**Resultado esperado:** instrucciones contienen `"do not narrate"` y `"do not roll dice"`.

---

#### DA-MAG-04 — El Critic da un veredicto estructurado (OK o PROBLEM:) [AUTO]

**Pasos:** `python -m pytest tests/test_critic.py::test_critic_verdict_is_structured`.  
**Resultado esperado:** `CRITIC_OK` y `CRITIC_PROBLEM_PREFIX` aparecen en
`CRITIC_INSTRUCTIONS`; el loop (`main.py`) parsea estas cadenas, no un modelo.

**Referencia:** `src/dungeon_agents/agents/critic.py:35-36`

---

#### DA-MAG-05 — El tope de reintentos del Critic es un entero >= 0 [AUTO]

**Pasos:** `python -m pytest tests/test_critic.py::test_retry_cap_is_bounded`.  
**Resultado esperado:** `MAX_SCENE_RETRIES` es un entero (`main.py:43`, actualmente `1`).

---

#### DA-MAG-06 — El Critic revisa cada escena antes de que el jugador la vea [MANUAL]

**Objetivo:** confirmar el pipeline generar -> revisar -> mostrar.  
**Precondicion:** modo debug activo.  
**Pasos:**
1. Jugar cualquier turno.
2. Observar los mensajes de debug.

**Resultado esperado:** aparece `[debug] Critic verdict: OK` (o un mensaje de
regeneracion si el Critic encontro una contradiccion). El Critic siempre actua;
su ejecucion es parte del codigo del loop, no dependiente del modelo
(`main.py:424-447`).

---

#### DA-MAG-07 — El Critic detecta una contradiccion y el GM regenera la escena [MANUAL]

**Objetivo:** verificar el mecanismo de auto-reparacion.  
**Nota:** este caso es dificil de provocar de forma controlada. La contradiccion
mas facil de inducir es que la narracion diga que el jugador tiene objetos que
no tiene.  
**Pasos (intentar):**
1. Modo debug activo.
2. Jugar hasta tener inventario definido.
3. Decir al GM algo como "I use the magic sword" cuando no hay espada en el
   inventario.
4. Observar si el Critic detecta contradiccion.

**Resultado esperado (si el Critic falla):** mensaje `[debug] Critic verdict: PROBLEM: ...`
seguido de `[debug] regenerating scene (Critic: ...)`, y una nueva escena coherente
con el estado real. Si el Critic da OK, la escena se muestra sin regenerar.

**Resultado esperado (si MAX_SCENE_RETRIES se alcanza):** la escena se muestra
de todas formas (el tope anti-bucle actua; `main.py:425-444`).

---

#### DA-MAG-08 — El Lore Keeper actualiza location y quest en la escena inicial [MANUAL]

**Objetivo:** verificar que al abrir el juego, el Lore Keeper sincroniza el
estado narrativo.  
**Precondicion:** borrar guardado previo para forzar partida nueva.  
**Pasos:**
1. Iniciar el juego (`new`).
2. Esperar la escena de apertura del GM.
3. Escribir `stats`.

**Resultado esperado:** `Where` y `Quest` muestran valores reales (no "not set yet"),
lo que significa que el GM consulto al Lore Keeper y este llamo a `set_location`
y `set_quest`. Si muestran "not set yet", es el comportamiento honesto del gap
(no un bug del codigo; vease seccion 6).

---

#### DA-MAG-09 — El Referee persiste los cambios de HP y oro en disco [MANUAL]

**Objetivo:** los cambios de recursos no solo existen en la narracion; se
guardan y sobreviven a un reinicio.  
**Pasos:** ver DA-PER-08 (este caso es la verificacion de agente del mismo comportamiento).

---

### 4.7 Fin de partida

#### DA-FIN-01 — El juego continua si hay HP > 0 y quest no completada [AUTO]

**Pasos:** `python -m pytest tests/test_end_of_game.py::test_game_continues_when_alive_and_quest_unfinished`.  
**Resultado esperado:** `_check_end_of_game(state)` devuelve `None`.

---

#### DA-FIN-02 — HP = 0 produce `"lost"` [AUTO]

**Pasos:** `python -m pytest tests/test_end_of_game.py::test_defeat_when_hp_zero`.  
**Resultado esperado:** `_check_end_of_game(state_con_hp_0) == "lost"`.

---

#### DA-FIN-03 — Quest completada produce `"won"` [AUTO]

**Pasos:** `python -m pytest tests/test_end_of_game.py::test_victory_when_quest_completed`.  
**Resultado esperado:** `_check_end_of_game(state_con_quest_completada) == "won"`.

---

#### DA-FIN-04 — Derrota tiene precedencia sobre victoria [AUTO]

**Objetivo:** si el heroe tiene HP=0 Y la quest esta completada, el resultado
es "lost", no "won".  
**Pasos:** `python -m pytest tests/test_end_of_game.py::test_defeat_takes_precedence_over_victory`.  
**Resultado esperado:** `"lost"` (el codigo evalua `is_game_over` primero; `main.py:205-208`).

---

#### DA-FIN-05 — Heroe nuevo sin quest no esta ganando ni perdiendo [AUTO]

**Pasos:** `python -m pytest tests/test_end_of_game.py::test_full_hp_no_quest_continues`.  
**Resultado esperado:** `None`.

---

#### DA-FIN-06 — Victoria muestra panel verde "The End" y detiene el juego [MANUAL]

**Objetivo:** verificar el panel de victoria y que el loop termina.  
**Nota:** requiere que el Referee llame a `complete_quest` (via regla de dominio).
Puede provocarse diciendole al GM "I have completed my quest" en un juego donde
el Lore Keeper haya establecido una quest.  
**Pasos:**
1. Jugar hasta que el GM declare completada la quest (observar en debug que el
   Referee llamo a `complete_quest` o que el estado tenga `completed: true`).
2. Verificar en `data/game_state.json` que `active_quest.completed` es `true`.

**Resultado esperado:**
- Panel verde con titulo "The End" y texto de victoria (`main.py:212-218`).
- Mensaje `Type new next time to begin a fresh adventure.`
- El loop termina; el juego no sigue pidiendo input.

---

#### DA-FIN-07 — Derrota muestra panel rojo "Game Over" y detiene el juego [MANUAL]

**Objetivo:** verificar el panel de derrota.  
**Pasos:**
1. En modo debug, provocar dano sucesivo hasta HP=0 (decir "I get hit hard").
2. Verificar que el Referee llamo a `change_hp` con un delta negativo suficiente.
3. Verificar en `data/game_state.json` que `player.hp` es `0`.

**Resultado esperado:**
- Panel rojo con titulo "Game Over" y texto de derrota (`main.py:219-224`).
- Mensaje `Type new next time to begin a fresh adventure.`
- El loop termina.

---

#### DA-FIN-08 — `is_game_won` y `is_game_over` son deterministicos sobre el estado [AUTO]

**Pasos:** `python -m pytest tests/test_rules.py::test_complete_quest_wins_the_game tests/test_rules.py::test_is_game_over_when_hp_zero`.  
**Resultado esperado:** ambas funciones devuelven el booleano correcto basandose
exclusivamente en el `GameState`, sin consultar al modelo.

---

### 4.8 Robustez y casos limite

#### DA-ROB-01 — Datos de quest invalidos (titulo vacio) son rechazados por Pydantic [AUTO]

**Pasos:** `python -m pytest tests/test_models.py::test_quest_title_cannot_be_empty`.  
**Resultado esperado:** `ValidationError`.

---

#### DA-ROB-02 — Guardado con HP negativo es rechazado por `load_state` [AUTO]

**Pasos:** `python -m pytest tests/test_state.py::test_load_state_rejects_schema_mismatch`.  
**Resultado esperado:** `StateError`.

---

#### DA-ROB-03 — Item con cantidad 0 en el inventario es rechazado por Pydantic [AUTO]

**Pasos:** `python -m pytest tests/test_models.py::test_game_state_rejects_invalid_nested_item`.  
**Resultado esperado:** `ValidationError` al construir el `GameState`.

---

#### DA-ROB-04 — Ctrl+C durante input termina limpiamente [MANUAL]

**Pasos:** pulsar Ctrl+C en el prompt de input del jugador.  
**Resultado esperado:** mensaje `Farewell, adventurer.` y salida limpia sin
traceback. El estado guardado en disco no se corrompe (`main.py:465-467`,
captura `KeyboardInterrupt`).

---

#### DA-ROB-05 — EOF durante input (pipe o redireccion) termina limpiamente [MANUAL]

**Pasos:** redirigir un fichero vacio como stdin: `echo "" | dungeon-agents`.  
**Resultado esperado:** igual que DA-ROB-04 (captura `EOFError`).

---

#### DA-ROB-06 — Dificultad invalida en `skill_check` devuelve mensaje de error, no crash [MANUAL/INDIRECTO]

**Objetivo:** si el modelo pasa una dificultad desconocida, el tool wrapper
(`game_tools.py:219-241`) captura `InvalidDifficultyError` y devuelve un string
de error al modelo en lugar de propagar la excepcion.  
**Pasos:**
- Lectura del codigo: `game_tools.py:232-234` captura la excepcion y devuelve
  `f"Invalid difficulty: {exc}"`.
- No es necesario test adicional; la logica de la excepcion esta cubierta por `test_dice.py`.

**Resultado esperado:** el Referee recibe una cadena de error descriptiva y
puede adaptar su respuesta; el juego no se detiene.

---

#### DA-ROB-07 — Dados fuera de rango devuelven mensaje de error, no crash [MANUAL/INDIRECTO]

**Objetivo:** igual que DA-ROB-06 pero para `roll_dice`.  
**Referencia:** `game_tools.py:69-73` captura `InvalidDiceError`.

---

#### DA-ROB-08 — `set_location` con nombre vacio devuelve mensaje de error [AUTO indirecto]

**Pasos:** leer `game_tools.py:275-276`: `if not location: return "A location needs a name."`.  
**Resultado esperado:** el tool no muta el estado; el modelo recibe una razon y puede solicitar un nombre valido.

---

#### DA-ROB-09 — `set_quest` con titulo vacio devuelve mensaje de error [AUTO indirecto]

**Referencia:** `game_tools.py:294-295`: `if not title: return "A quest needs a title."`.

---

### 4.9 Portabilidad Windows

#### DA-WIN-01 — Toda la salida de consola usa solo caracteres ASCII [MANUAL]

**Objetivo:** la consola de Windows con encoding cp1252 no puede renderizar
emojis, comillas tipograficas, guiones em ni flechas. Un `UnicodeEncodeError`
dentro de un hook aborta la llamada al tool.  
**Pasos:**
1. Ejecutar el juego en una terminal de Windows sin cambiar el encoding.
2. Jugar varios turnos con debug activo.

**Resultado esperado:** ninguna salida del propio codigo de la aplicacion (paneles,
mensajes de debug, mensajes de meta-comandos) provoca `UnicodeEncodeError`. El
texto del modelo puede contener caracteres no-ASCII; lo que importa es que el
codigo de la aplicacion no los inyecta (`main.py:339-342`).

---

#### DA-WIN-02 — El fichero de estado se escribe y lee como UTF-8 [AUTO indirecto]

**Referencia:** `state.py:64` usa `encoding="utf-8"` en la escritura y `state.py:83`
en la lectura. Los modelos Pydantic pueden contener unicode si el modelo lo
genera; la capa de persistencia no lo corrompe.

---

## 5. Matriz de trazabilidad

| Funcionalidad | Milestone | Casos de prueba |
|---|---|---|
| Loop de consola, salida por `exit`/`quit`/Ctrl+C | M1 | DA-CMD-08, DA-ROB-04, DA-ROB-05 |
| Banner de bienvenida, texto de ayuda | M1 | DA-CFG-07, DA-CMD-06 |
| Contrato del Game Master (2-3 opciones, in-character) | M1 | `test_smoke.py` (DA-CFG-02 a DA-CFG-08) |
| `roll_dice` con limites y RNG inyectable | M2 | DA-DAD-01 a DA-DAD-04 |
| Guardado/carga de estado en disco | M2 | DA-PER-01 a DA-PER-05 |
| Portabilidad ASCII/cp1252 | M2 | DA-WIN-01, DA-WIN-02 |
| Modelos Pydantic validados (Player, InventoryItem, Quest, GameState, ActionResult) | M3 | DA-ROB-01 a DA-ROB-03, `test_models.py` |
| Reglas de inventario (add, remove, limites) | M4 | DA-REG-01 a DA-REG-06 |
| Reglas de recursos (gold, HP clamp, win/lose) | M4 | DA-REG-07 a DA-REG-10, DA-FIN-01 a DA-FIN-05, DA-FIN-08 |
| Persistencia unificada (load_state_or_none, clear_state) | M5 | DA-PER-04, DA-PER-05 |
| Meta-comandos deterministicos (stats, inventory, summary, help, debug, new) | M5 | DA-CMD-01 a DA-CMD-09 |
| Resume con recap + ultima escena verbatim | M5 | DA-PER-06 |
| Modo debug (DUNGEON_DEBUG, toggle en caliente, hooks) | M5 | DA-CFG-06, DA-CMD-07, DA-MAG-06 |
| Nuevo juego siembra estado inicial (stats desde turno 0) | M5 | DA-PER-07 |
| Arquitectura multi-agente (GM + Referee + Lore Keeper + Critic) | M6 | DA-MAG-01 a DA-MAG-09 |
| `skill_check`: dado + decision en codigo | M6 | DA-DAD-05 a DA-DAD-09 |
| `check_can_afford` como pre-check deterministico | M6 | DA-REG-09, `test_rules.py` can_afford |
| Pipeline Critic (generar -> revisar -> regenerar, MAX_SCENE_RETRIES) | M6 | DA-MAG-04 a DA-MAG-07 |
| Fin de partida detectado por codigo (victoria/derrota/precedencia) | M6 | DA-FIN-01 a DA-FIN-08 |
| HP y oro persisten entre sesiones (fix M6) | M6 | DA-PER-08, DA-MAG-09 |

---

## 6. Notas sobre no-determinismo

### El oraculo debil en sistemas con LLM

Los casos manuales de agentes son **no deterministicos por naturaleza**: dos
ejecuciones identicas del mismo turno pueden producir narraciones distintas. Esto
no es un defecto de la aplicacion; es la naturaleza del muestreo de modelos de
lenguaje.

Lo que si es determinista — y lo que este plan verifica — son las *propiedades*:

- El HP guardado en disco despues del combate.
- Si el juego detecto victoria o derrota.
- El texto exacto de la ultima escena al reanudar.
- El resultado de un meta-comando.

### Como interpretar resultados en pruebas manuales

**No exigir 100% de cumplimiento en comportamientos de agentes.** Si en 10
ejecuciones el Lore Keeper actualiza la location correctamente en 8, la tasa es
80%. Un 80% puede ser aceptable (documentarlo); un 20% indica que el prompt
necesita revision o que hay que mover esa responsabilidad a codigo determinista.

**"not set yet" es correcto, no un fallo.** Si `stats` muestra `Where: not set
yet`, significa que el Lore Keeper no llamo a `set_location` en ese turno. Eso
es el *comportamiento honesto del gap* — una eleccion de diseno explicita de M5.
Un valor inventado sin haber llamado al tool seria un fallo mucho mas grave.

**La leccion central del proyecto (M5):** un prompt empuja probabilidades, no
garantias. Lo que DEBE ocurrir va en codigo determinista y se verifica con tests
automaticos. Lo que depende del modelo debe fallar de forma visible (gap honesto),
nunca de forma silenciosa (valor fabricado). Este principio es exactamente lo que
aplicara TestOps AI cuando evalua si un criterio de aceptacion se cumple.

### Cuando escalar a codigo determinista

Si un comportamiento esperado de agente falla frecuentemente, la respuesta no es
"prompt mas largo" sino evaluar si ese comportamiento debe pasar a ser
determinista. Ejemplo real del proyecto: `complete_quest` solo se puede llamar si
hay una quest activa — eso es una regla de dominio en `rules.py`, no una
instruccion del prompt del Referee.

---

## 7. Registro de resultados

Plantilla para anotar los resultados de cada ejecucion manual del plan.

**Fecha de ejecucion:** ___________  
**Version/commit:** ___________  
**Proveedor y modelo:** ___________  
**Ejecutado por:** ___________

| ID | Descripcion breve | Tipo | Resultado | Observaciones |
|----|-------------------|------|-----------|---------------|
| DA-CFG-01 | Sin API key: mensaje claro | AUTO | PASS / FAIL | |
| DA-CFG-02 | Default Anthropic + claude-haiku-4-5 | AUTO | PASS / FAIL | |
| DA-CFG-03 | Provider openai selecciona key/modelo | AUTO | PASS / FAIL | |
| DA-CFG-04 | Provider desconocido -> defecto | AUTO | PASS / FAIL | |
| DA-CFG-05 | DUNGEON_MODEL anula default | AUTO | PASS / FAIL | |
| DA-CFG-06 | DUNGEON_DEBUG activa debug | AUTO | PASS / FAIL | |
| DA-CFG-07 | Banner muestra provider/modelo/debug | MANUAL | PASS / FAIL | |
| DA-CFG-08 | Spinner en primer arranque | MANUAL | PASS / FAIL | |
| DA-CMD-01 | `stats` es determinista | MANUAL | PASS / FAIL | |
| DA-CMD-02 | `status` == `stats` | MANUAL | PASS / FAIL | |
| DA-CMD-03 | `inventory` solo muestra inventario | MANUAL | PASS / FAIL | |
| DA-CMD-04 | `summary` muestra session_summary | MANUAL | PASS / FAIL | |
| DA-CMD-05 | Meta-comandos remuestran ultima escena | MANUAL | PASS / FAIL | |
| DA-CMD-06 | `help` muestra todos los comandos | MANUAL | PASS / FAIL | |
| DA-CMD-07 | `debug` toggle en caliente | MANUAL | PASS / FAIL | |
| DA-CMD-08 | `exit` termina limpiamente | MANUAL | PASS / FAIL | |
| DA-CMD-09 | Entrada vacia no consume turno | MANUAL | PASS / FAIL | |
| DA-PER-01 | Round-trip save/load | AUTO | PASS / FAIL | |
| DA-PER-02 | Fichero creado en data/ | AUTO | PASS / FAIL | |
| DA-PER-03 | Sin fichero -> None | AUTO | PASS / FAIL | |
| DA-PER-04 | Save incompatible -> None | AUTO | PASS / FAIL | |
| DA-PER-05 | clear_state borra; segunda llamada no-op | AUTO | PASS / FAIL | |
| DA-PER-06 | Resume: recap + ultima escena verbatim | MANUAL | PASS / FAIL | |
| DA-PER-07 | `new` descarta y siembra estado fresco | MANUAL | PASS / FAIL | |
| DA-PER-08 | HP y oro persisten entre sesiones | MANUAL | PASS / FAIL | |
| DA-PER-09 | Schema invalido -> StateError | AUTO | PASS / FAIL | |
| DA-REG-01 | Inventario vacio | AUTO | PASS / FAIL | |
| DA-REG-02 | Anadir item y apilar | AUTO | PASS / FAIL | |
| DA-REG-03 | Reglas son puras (no mutan input) | AUTO | PASS / FAIL | |
| DA-REG-04 | No quitar item que no se tiene | AUTO | PASS / FAIL | |
| DA-REG-05 | No quitar mas cantidad de la que hay | AUTO | PASS / FAIL | |
| DA-REG-06 | GM no puede quitar item inexistente | MANUAL | PASS / FAIL | |
| DA-REG-07 | No gastar mas oro del que se tiene | AUTO + MANUAL | PASS / FAIL | |
| DA-REG-08 | HP clamp [0, MAX_HP] | AUTO | PASS / FAIL | |
| DA-REG-09 | check_can_afford es read-only | AUTO | PASS / FAIL | |
| DA-REG-10 | Stack a cero se elimina | AUTO | PASS / FAIL | |
| DA-DAD-01 | Tirada en [1, sides] | AUTO | PASS / FAIL | |
| DA-DAD-02 | RNG inyectable reproduce tirada | AUTO | PASS / FAIL | |
| DA-DAD-03 | Fuera de [2, 100] -> InvalidDiceError | AUTO | PASS / FAIL | |
| DA-DAD-04 | Tipos no enteros -> InvalidDiceError | AUTO | PASS / FAIL | |
| DA-DAD-05 | resolve_check: exito = roll >= threshold | AUTO | PASS / FAIL | |
| DA-DAD-06 | Dificultad desconocida -> InvalidDifficultyError | AUTO | PASS / FAIL | |
| DA-DAD-07 | Dificultad case-insensitive | AUTO | PASS / FAIL | |
| DA-DAD-08 | Referee llama skill_check, no inventa | MANUAL | PASS / FAIL | |
| DA-DAD-09 | Formato de respuesta de skill_check | AUTO indirecto | PASS / FAIL | |
| DA-MAG-01 | GM tiene rules_referee y lore_keeper | AUTO | PASS / FAIL | |
| DA-MAG-02 | Referee no narra | AUTO | PASS / FAIL | |
| DA-MAG-03 | Lore Keeper no tira dados | AUTO | PASS / FAIL | |
| DA-MAG-04 | Critic da veredicto estructurado | AUTO | PASS / FAIL | |
| DA-MAG-05 | MAX_SCENE_RETRIES es entero | AUTO | PASS / FAIL | |
| DA-MAG-06 | Critic revisa cada escena | MANUAL | PASS / FAIL | |
| DA-MAG-07 | Critic detecta contradiccion y GM regenera | MANUAL | PASS / FAIL | |
| DA-MAG-08 | Lore Keeper actualiza location/quest | MANUAL | PASS / FAIL | |
| DA-MAG-09 | Referee persiste HP y oro en disco | MANUAL | PASS / FAIL | |
| DA-FIN-01 | Continua si HP > 0 y quest abierta | AUTO | PASS / FAIL | |
| DA-FIN-02 | HP = 0 -> "lost" | AUTO | PASS / FAIL | |
| DA-FIN-03 | Quest completada -> "won" | AUTO | PASS / FAIL | |
| DA-FIN-04 | Derrota tiene precedencia sobre victoria | AUTO | PASS / FAIL | |
| DA-FIN-05 | Heroe nuevo: ni gana ni pierde | AUTO | PASS / FAIL | |
| DA-FIN-06 | Victoria: panel verde + loop termina | MANUAL | PASS / FAIL | |
| DA-FIN-07 | Derrota: panel rojo + loop termina | MANUAL | PASS / FAIL | |
| DA-FIN-08 | is_game_won / is_game_over deterministicos | AUTO | PASS / FAIL | |
| DA-ROB-01 | Quest titulo vacio -> ValidationError | AUTO | PASS / FAIL | |
| DA-ROB-02 | Save con HP negativo -> StateError | AUTO | PASS / FAIL | |
| DA-ROB-03 | Item cantidad 0 -> ValidationError | AUTO | PASS / FAIL | |
| DA-ROB-04 | Ctrl+C termina limpiamente | MANUAL | PASS / FAIL | |
| DA-ROB-05 | EOF termina limpiamente | MANUAL | PASS / FAIL | |
| DA-ROB-06 | Dificultad invalida: error string, no crash | AUTO indirecto | PASS / FAIL | |
| DA-ROB-07 | Dado fuera de rango: error string, no crash | AUTO indirecto | PASS / FAIL | |
| DA-ROB-08 | set_location nombre vacio | AUTO indirecto | PASS / FAIL | |
| DA-ROB-09 | set_quest titulo vacio | AUTO indirecto | PASS / FAIL | |
| DA-WIN-01 | Solo ASCII en salida de codigo | MANUAL | PASS / FAIL | |
| DA-WIN-02 | Persistencia en UTF-8 | AUTO indirecto | PASS / FAIL | |

**Total casos:** 68  
**Automaticos (sin API key):** 44  
**Manuales (con API key):** 24  

---

*Plan generado tras lectura directa del codigo fuente. Cada comportamiento
citado se verifico en los archivos correspondientes antes de documentarlo.*
