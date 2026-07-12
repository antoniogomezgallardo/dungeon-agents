# Principios y patrones de agentes de IA

> Guía de referencia transversal del proyecto **Dungeon Agents**. No está atada a
> ningún milestone: recoge los principios y patrones que el proyecto ha demostrado
> milestone tras milestone y los pone en un solo lugar consultable.
>
> Prerrequisito recomendado: lee primero
> [teoria-de-agentes-y-qa.md](teoria-de-agentes-y-qa.md) (qué es un agente, el
> bucle agéntico, tools, arquitectura en dos capas, agente vs. workflow) y
> [aplicaciones-de-agentes-en-qa.md](aplicaciones-de-agentes-en-qa.md) (por qué
> los agentes en QA, los patrones de evaluación). Este documento asume ese
> vocabulario y no lo repite; lo cita y enlaza en su lugar.

---

## Tabla de contenidos

1. [Cuándo USAR un agente](#1-cuándo-usar-un-agente)
2. [Cuándo NO usar un agente (y qué usar en su lugar)](#2-cuándo-no-usar-un-agente-y-qué-usar-en-su-lugar)
3. [Principios innegociables al trabajar con agentes](#3-principios-innegociables-al-trabajar-con-agentes)
   - 3.1 Un prompt empuja probabilidades, no garantías
   - 3.2 El resultado de una acción lo decide el código, no el modelo
   - 3.3 Fallo honesto, nunca engañoso
   - 3.4 El estado validado es la fuente de verdad
   - 3.5 Una llamada a tool es la frontera entre narración y hecho persistente
   - 3.6 Especialización más coordinación producen fiabilidad
   - 3.7 Contratos estructurados entre capas y agentes
   - 3.8 La observabilidad no es opcional
4. [Patrones de coordinación de múltiples agentes](#4-patrones-de-coordinación-de-múltiples-agentes)
   - 4.1 Agent-as-tool / orquestador
   - 4.2 Handoff (transferencia de control)
   - 4.3 Pipeline / cadena de revisión
   - 4.4 Tabla comparativa y por qué M6 eligió agent-as-tool
5. [Checklist práctico antes de meter un agente](#5-checklist-práctico-antes-de-meter-un-agente)
6. [Puente a QA y TestOps AI](#6-puente-a-qa-y-testops-ai)

---

## 1. Cuándo USAR un agente

Un agente aporta valor cuando la tarea tiene al menos una de estas tres
características:

**La tarea requiere juicio abierto.** La respuesta correcta no es única ni
predefinida — hay que interpretar el contexto, explorar opciones, adaptar el
comportamiento según lo que se descubre. Un script fijo no puede hacerlo; un
modelo que decide dinámicamente qué tool llamar, sí.

**La entrada llega como lenguaje natural y necesita traducirse a datos
estructurados.** El jugador escribe "quiero comprar una cuerda por 5 monedas de
oro". Algo tiene que convertir esa frase en tres enteros (`gold_cost=5`,
`item_name="rope"`, `item_quantity=1`) antes de que el código pueda evaluar si la
compra es viable. Esa traducción es el trabajo del modelo.

**El flujo de acciones no se puede fijar de antemano.** La secuencia de tools que
hay que llamar depende de los resultados intermedios. El Game Master puede acabar
un turno sin llamar a ninguna tool (si el jugador solo habla), o puede llamar a
`rules_referee`, que internamente llama a `skill_check` y luego a `change_hp`.
Ningún script fijo conoce esa secuencia antes de ejecutar el turno.

### Ejemplos reales del proyecto

| Situación | Por qué necesita un agente |
|-----------|---------------------------|
| El Game Master narra la escena y decide qué tools llamar según lo que el jugador hace | El flujo es abierto; no hay un orden de tools fijo |
| El Lore Keeper decide si la escena describe una ubicación nueva o un cambio de misión | Es un juicio sobre qué es "narrativamente significativo" — no hay regla Python para eso |
| El Rules Referee juzga qué nivel de dificultad asignar a una acción ("escalar el muro es *moderate*") | La dificultad es subjetiva, dependiente del contexto; el modelo la interpreta bien |
| El modelo traduce "ataco al goblin con mi espada" en `skill_check(difficulty="moderate")` | Traducción lenguaje natural → parámetros estructurados |

En todos estos casos el agente aporta porque el trabajo es abierto, contextual o
lingüístico. La decisión de si la acción tiene éxito — eso ya no es trabajo del
agente (ver sección 2).

---

## 2. Cuándo NO usar un agente (y qué usar en su lugar)

Esta es la sección más importante de esta guía, porque el error más común es
meter un agente donde el código es la respuesta correcta.

**La regla central: usa un agente para lo que requiere juicio; usa código para lo
que requiere garantía.**

Anthropic lo formula así en *Building Effective Agents*: la mayoría de sistemas
en producción no necesitan otro agente autónomo; necesitan un workflow con pasos
claros, tools ajustadas y resultados medibles. El agente es para cuando la
flexibilidad justifica perder predecibilidad. Cuando necesitas predecibilidad,
necesitas código.

### Señales de que el trabajo pertenece al código

**Cuando el resultado debe ser siempre el mismo dada la misma entrada.** Si "el
jugador tiene 3 monedas de oro y quiere gastar 5" debe producir *siempre* un
fallo, ese fallo tiene que salir de una función Python, no de un prompt. Un prompt
puede producir el fallo el 95% de las veces. El 5% restante es inaceptable si la
regla de negocio importa.

**Cuando el incumplimiento produce un falso positivo silencioso.** Un agente que
decide si una acción es asequible puede equivocarse y decir "sí" cuando la
respuesta es "no". En QA, el equivalente es un agente que decide si un test
pasó: si se equivoca y dice "PASÓ" cuando no lo hizo, ha destruido la confianza
en el sistema. Ese veredicto pertenece al código.

**Cuando la función es "leer un valor del estado y compararlo".** No necesitas
un modelo para saber si `state.player.gold >= 5`. Necesitas la función
`can_afford` de `domain/rules.py`.

### Ejemplos concretos del proyecto

`can_afford` (`domain/rules.py:46`) es el ejemplo más claro. En M4-M5 existía
`validate_action`, que tomaba una descripción de acción y... le pedía al modelo
que decidiera si era viable. El nombre sugería validación determinista; la
implementación delegaba en una probabilidad. Fue reemplazada en M6 por
`can_afford`: una función pura que carga el `GameState`, compara los enteros, y
devuelve `ActionResult(success=False, message="Cannot afford: needs 5 gold but
only has 3.")` — sin modelo, sin ambigüedad, sin margen de error.

```
# Lo que hace can_afford: puro Python, sin SDK, sin API key.
# domain/rules.py:46-95
def can_afford(state, gold_cost=0, item_name="", item_quantity=1) -> ActionResult:
    ...
```

`resolve_check` (`domain/dice.py:102`) es el segundo caso. Antes de M6, el modelo
recibía "Rolled a 9 on a 20-sided die" y era libre de interpretar si 9 era éxito
o fracaso. El dado era teatro. `resolve_check` fija eso: tira 1d20, compara
contra un umbral (`DIFFICULTY_THRESHOLDS`), y devuelve `CheckResult(success=bool)`
— el código decide. El modelo solo elige la dificultad (un juicio subjetivo,
apropiado para un LLM); el código decide si el resultado supera esa dificultad.

`spend_gold`, `change_hp`, `earn_gold` (`domain/rules.py:182-245`): las
consecuencias numéricas de una acción pertenecen al código. La HP se clampea a
`[0, max_hp]` con `max(0, min(player.hp + delta, player.max_hp))`. Esa
garantía no puede ser una instrucción de prompt.

**La decisión de M6 que confirma el principio.** Cuando se diseñó el Lore Keeper
se valoró una alternativa: llamar a `lore_keeper.run(scene_text)` de forma
incondicional después de cada turno del Game Master, convirtiendo la
sincronización del mundo narrativo en un paso de pipeline determinista. La
alternativa fue rechazada por dos razones. Primera: si la sincronización debe
garantizarse, un LLM es la herramienta equivocada — si quieres un valor escrito
en un campo, escríbelo en código. Segunda: el Lore Keeper aporta valor
precisamente porque ejerce juicio ("¿esto es una nueva ubicación? ¿hay un cambio
de misión?") — garantizar la llamada sin garantizar el juicio no resuelve el
problema y añade latencia y coste en cada turno. La conclusión queda en
`agents/lore_keeper.py:14-18`:

> "Use an agent for what needs judgment; use code for what needs a guarantee."

### Mapa de decisión

```
¿El resultado debe ser el mismo siempre para la misma entrada?
    Sí -> código (función determinista en domain/)
    No -> ¿requiere interpretar lenguaje natural o contexto abierto?
              Sí -> agente
              No -> workflow (pasos fijos, código controla el flujo)
```

---

## 3. Principios innegociables al trabajar con agentes

Cada principio tiene un porqué y una evidencia concreta del código.

---

### 3.1 Un prompt empuja probabilidades, no garantías

**El principio.** Cuando le dices a un modelo "llama a `set_location` al inicio
de cada partida", aumentas la probabilidad de que lo haga. No garantizas que lo
haga. El modelo puede distraerse, tener contexto competitivo, o simplemente
producir una predicción diferente ese turno. Las instrucciones son un empuje
estadístico, no un contrato de código.

**Por qué importa.** Todo lo que DEBE ocurrir siempre — "no puedes gastar oro que
no tienes", "la HP no baja de 0", "el veredicto de test está en el estado
persistente" — tiene que ir en código determinista que el modelo no pueda
saltarse. Lo que puede ocurrir la mayoría de las veces — "sincroniza la
ubicación cuando cambias de escena" — puede quedarse en un agente, siempre que
el sistema falle de forma honesta cuando no ocurre.

**La evidencia en el proyecto.** En M5, el Game Master tenía instrucciones
explícitas de llamar a `set_location` y `set_quest` en la primera escena. Con
`claude-haiku-4-5`, a veces no lo hacía. El código era correcto; el modelo era
el eslabón variable. La respuesta correcta fue mostrar "not set yet" (hueco
honesto), no fabricar un valor. Ver `GAME_MASTER_INSTRUCTIONS`
(`agents/game_master.py:35`):

> "(If a value hasn't been set yet, the player's stats simply show 'not set yet' —
> an honest gap, never a wrong value.)"

En M6, el Lore Keeper especializado aumenta la probabilidad de que la
sincronización ocurra. Pero el docstring de `lore_keeper.py:13` lo dice
explícitamente: "It does not GUARANTEE it (a prompt pushes probability, not
certainty)."

---

### 3.2 El resultado de una acción lo decide el código, no el modelo

**El principio.** El modelo orquesta — decide qué herramienta llamar — y traduce
— convierte lenguaje natural en parámetros estructurados. El resultado de la
acción lo produce el código. La división es: el modelo elige el "qué"; el código
produce el "cuánto" y el "si se permite".

**Por qué importa.** Si el resultado depende del modelo, es probabilístico: el
mismo estado de juego puede producir resultados distintos en ejecuciones
distintas. Eso es el no-determinismo que hace inauditable un sistema. En QA, un
veredicto de test producido por el modelo — no por código que evalúa una
aserción — no es un veredicto; es una predicción.

**La evidencia en el proyecto.** `can_afford` (`domain/rules.py:46`):

- El modelo traduce "el aventurero quiere comprar una cuerda por 5 monedas" en
  `gold_cost=5, item_name="rope", item_quantity=1`.
- `can_afford` carga el `GameState` y compara. La función decide.
- El modelo recibe el mensaje de resultado y lo narra. El modelo no interpreta si
  era asequible; recibe el veredicto.

`resolve_check` (`domain/dice.py:102`):

- El modelo (el Rules Referee) juzga que escalar un muro es `"moderate"`.
- `resolve_check("moderate")` tira 1d20, compara contra el umbral 10, y devuelve
  `CheckResult(success=True/False)`.
- El modelo recibe "SUCCESS: rolled 14 on 1d20 vs 10+." No puede contradecirlo.

El módulo `domain/dice.py:7` lo formula en su docstring:

> "The agent decides *when* to roll; this code decides *what* the roll is."

---

### 3.3 Fallo honesto, nunca engañoso

**El principio.** Cuando el sistema no puede producir un valor correcto — porque
el modelo no llamó a la tool, porque no hay datos suficientes, porque la regla se
violó — el sistema debe producir un hueco visible, nunca un valor plausible
inventado. Un "not set yet" es correcto. Un valor fabricado que parece real es el
peor modo de fallo posible.

**Por qué importa en QA especialmente.** El pecado capital de un sistema de QA no
es que falle; es que falle silenciosamente con apariencia de éxito. Un agente de
QA que dice "PASÓ" cuando no corrió la evaluación ha destruido lo único que un
sistema de testing vende: confianza en su veredicto. El hueco visible es
aceptable; el falso positivo silencioso es catastrófico.

**La evidencia en el proyecto.** El reemplazo de `validate_action` por
`can_afford` es la demostración directa. `validate_action` (M4-M5) devolvía un
fragmento de prompt instruyendo al modelo a "juzgar si esto es posible". El
modelo podía decir "sí" aunque el jugador tuviera cero monedas de oro, porque la
decisión era probabilística. `can_afford` produce exactamente:

```
"Cannot afford: needs 5 gold but only has 3; needs 1x Rope but has 0."
```

Ese texto viene del código (`domain/rules.py:91-94`), no del modelo. El modelo
lo recibe y lo narra; no lo genera. No puede suavizarlo ni fudgearlo.

La nota de diseño en `rules_referee.py:64-66` codifica el principio:

> "Do NOT invent game state you weren't given. If you lack the information to
> rule, say what you would need. An honest 'cannot rule without X' is correct;
> a made-up ruling is not."

---

### 3.4 El estado validado es la fuente de verdad

**El principio.** La memoria del modelo — lo que narró, lo que "recuerda" del
contexto de conversación — no es una fuente de verdad fiable. El estado
persistente y validado (en este proyecto: `data/game_state.json` validado con el
esquema Pydantic de `GameState`) es la única fuente de verdad. Los comandos que
leen datos (`stats`, `inventory`, `summary`) leen ese estado directamente; nunca
le preguntan al modelo.

**Por qué importa.** Un dato que vive solo en la narración desaparece al cerrar
la sesión. Un dato que vive en el estado validado sobrevive reinicios, es
auditable, y puede ser verificado con un `assert` exacto. En QA: un resultado de
test que existe solo en el contexto de conversación del agente es un resultado de
test que no existe.

**La evidencia en el proyecto.** El bug de persistencia descubierto en M6 Block 2
es la prueba más directa. `earn_gold`, `spend_gold` y `change_hp` existían como
funciones de dominio desde M4 pero nunca se habían expuesto como `@function_tool`.
El modelo narraba "ganas 10 monedas de oro" — y el estado persistente seguía
mostrando 0 porque ninguna tool había escrito el cambio. La corrección fue
añadir los tres wrappers en `tools/game_tools.py:177-216` y dárselos al Rules
Referee para que los llamara tras cada decisión de consecuencias.

La lección queda en `agents/rules_referee.py:51-55`:

> "These write the change to the game state; without them the change exists only
> in the story and is lost on reload."

---

### 3.5 Una llamada a tool es la frontera entre narración y hecho persistente

**El principio.** Un evento existe en el sistema solo cuando una tool call lo
escribe al estado validado. Hasta ese momento, el evento existe en la narración —
es texto en el historial de conversación — pero no en el sistema. Audita las tool
calls, no la narración.

**Por qué importa.** Es fácil pasar por alto este principio durante el desarrollo,
porque la narración parece correcta. El bug de M6 Block 2 solo se detectó porque
el usuario jugó, ganó recompensas, y luego ejecutó `stats` — que lee el estado
validado, no la conversación. El síntoma fue el estado mostrando los valores
originales. La prueba definitiva de persistencia siempre es: cierra la sesión,
recarga, verifica.

**La evidencia en el proyecto.** El patrón load-modify-save en `tools/game_tools.py`
es la implementación de este principio. Cada tool que muta estado sigue
exactamente esta secuencia:

```python
# tools/game_tools.py: patrón en earn_gold, spend_gold, change_hp
def earn_gold(amount: int) -> str:
    return _apply(rules.earn_gold(_load_or_new_state(), amount))
```

`_apply` (`tools/game_tools.py:46`) llama a `state.save_state(result.new_state)`
en caso de éxito. Sin ese `save_state`, el cambio no ocurrió desde el punto de
vista del sistema.

---

### 3.6 Especialización más coordinación producen fiabilidad

**El principio.** Un agente con diez instrucciones compite consigo mismo: cada
instrucción que atiende reduce la atención disponible para las demás. La
solución no es un modelo más grande ni un prompt más largo; es un agente con un
trabajo más estrecho y solo las tools que ese trabajo necesita.

Dos agentes especializados con una frontera limpia entre ellos producen más
fiabilidad que un solo agente generalista con el mismo conjunto de capacidades.
La frontera no es cortesía; es el mecanismo por el cual cada agente conserva
atención para su propio trabajo.

**Por qué importa.** La fiabilidad de un trabajo estrecho es medible: es una tasa
de cumplimiento. Si el Lore Keeper llama a `set_location` el 85% de los turnos
en que debería, eso es un número — un objetivo de M8. Si el cumplimiento es bajo,
la escalada correcta es hacer ese paso determinista en código. La tasa de
cumplimiento de un agente generalista con diez trabajos simultáneos es cinco tasas
entrelazadas que no se pueden medir ni escalar independientemente.

**La evidencia en el proyecto.** La frontera entre el Rules Referee y el Lore
Keeper (`agents/lore_keeper.py:59-61`) no es una elección de diseño estética:

> "Do NOT roll dice, change gold or HP, or add/remove items — that is the Rules
> Referee's and the Game Master's job, not yours."

El Referee no puede llamar a `set_location` porque no tiene esa tool. El Lore
Keeper no puede llamar a `change_hp` porque no tiene esa tool. La especialización
se refuerza con restricción de tools, no solo con instrucciones.

El mismo principio aparece en el módulo `domain/rules.py:1-16`:

> "Rules live in Python, not in prompts. The agent proposes an action; these
> deterministic functions decide whether it's allowed."

---

### 3.7 Contratos estructurados entre capas y agentes

**El principio.** El límite de ambigüedad en un sistema de agentes debe empujarse
lo más cerca posible de la entrada del modelo, y hacerse determinista en cuanto
sea posible. Las interfaces entre capas y entre agentes deben ser estrechas y
tipadas: enteros, modelos Pydantic, cadenas con formato fijo.

**Por qué importa.** Un componente que recibe `dict[str, Any]` es más difícil de
testear y razonar que uno que recibe un `GameState`. Un agente que recibe
"el jugador quiere hacer algo" produce más varianza que uno que recibe "el jugador
quiere escalar un muro con dificultad moderada". Cuanto más estructurado el
contrato, menos superficie de alucinación.

**La evidencia en el proyecto.** Hay tres niveles de contrato en el sistema:

| Frontera | Tipo de contrato | Ejemplo |
|----------|-----------------|---------|
| Jugador → Game Master | Lenguaje natural libre | "quiero comprar una cuerda" |
| Game Master → Rules Referee | Inglés estructurado (descripción de acción) | "player tries to buy a rope for 5 gold" |
| Rules Referee → `check_can_afford` | Tres enteros tipados Python | `gold_cost=5, item_name="rope", item_quantity=1` |
| `can_afford` → Rules Referee | `ActionResult` (Pydantic) + mensaje de texto exacto | `"Cannot afford: needs 5 gold but only has 3."` |

La ambigüedad del lenguaje natural se reduce en cada frontera hacia abajo. El
código solo ve tipos validados. Los tests del dominio solo necesitan construir un
`GameState` y llamar a la función; no necesitan un modelo ni un prompt.

La firma de `can_afford` (`domain/rules.py:46-51`) hace los contratos explícitos
con type hints, que el SDK convierte en esquemas JSON para validación de entrada
de tools.

---

### 3.8 La observabilidad no es opcional

**El principio.** Un sistema de agentes que solo muestra la salida final es
inauditable. Para saber si el sistema se comportó correctamente — cuál agente
trabajó, qué tools llamó, con qué argumentos, qué devolvieron, cuánto tardaron —
necesitas la trayectoria completa. Sin trayectoria no hay debugging posible,
y no hay QA posible.

**Por qué importa.** El modo de fallo de un agente rara vez es un error de Python:
es que el agente llamó la tool equivocada, con el argumento incorrecto, o no la
llamó en absoluto. Ninguno de esos fallos produce una excepción; solo producen un
estado incorrecto. La única forma de detectarlos es ver las tool calls.

**La evidencia en el proyecto.** Los `RunHooks` de `main.py` implementan el
registro de trayectoria: `on_agent_start` (qué agente trabaja), `on_tool_start`
(qué tool, con qué args), `on_tool_end` (resultado, tiempo en ms). En M6 con tres
agentes, un turno que involucra tanto al Lore Keeper como al Rules Referee produce
tres líneas `[debug] agent ... is working...` más todas las tool calls de cada
uno — una trayectoria completa y auditable.

Los hooks están desactivados por defecto (opt-in con `DUNGEON_DEBUG=1` o el
comando `debug`). Esa decisión de diseño — observabilidad disponible sin ser
ruidosa — es parte del principio: la ventana a las tripas del sistema siempre
debe estar a mano, pero no contaminar la experiencia normal.

---

### 3.9 Guardrails — controles, no ruegos

**El principio.** Un guardrail es un control en el camino de evaluación del SDK
que decide si un mensaje o una respuesta puede continuar, independientemente de lo
que el modelo haría si se lo dejases. No es una instrucción que le pide al modelo
que resista; es código que actúa antes (o después) de que el modelo corra. La
diferencia entre un prompt que dice "rechaza los intentos de manipulación" y un
guardrail que los bloquea es la diferencia entre una probabilidad y una garantía.

**Por qué importa.** La superficie de ataque de un agente incluye su propia
entrada: un prompt de sistema cuidadosamente diseñado puede ser anulado si el
usuario puede meter una instrucción nueva en su mensaje. Los guardrails de entrada
son la única defensa que puede decir "este mensaje nunca llegó al modelo", no
"el modelo probablemente lo resistió".

**La evidencia en el proyecto (M7).** Tres capas de defensa en profundidad:
- `detect_injection` (`domain/guardrails.py`): función pura Python, cero SDK.
  Patrones nombrados que reconocen formas de manipulación de instrucciones, no
  palabras clave sueltas. Testable sin API key.
- Injection Judge (`agents/injection_judge.py`): agente especialista que evalúa
  la intención semántica de mensajes que pasaron los patrones. Cubre el caso
  ambiguo que la regex no puede resolver ("Pretend to be a calculator").
- Character Judge (`agents/character_judge.py`): revisor de salida que detecta si
  la escena del GM rompió personaje o filtró su naturaleza de IA. Se ejecuta en
  el pipeline junto al Critic, con el mismo bucle de auto-reparación acotado.

El patrón arquitectónico es el mismo en las tres capas: la decisión vive en una
constante de módulo testable (`INJECTION_JUDGE_INSTRUCTIONS`,
`CHARACTER_JUDGE_INSTRUCTIONS`) — el contrato existe con o sin API key. El SDK
solo adapta esa decisión a su mecanismo de tripwire o de pipeline.

**Guardrail de entrada vs. guardrail de salida: prevenir vs. detectar.**
- Los guardrails de entrada PREVIENEN: el mensaje nunca llega al modelo, no hay
  escena generada, el turno se descarta limpiamente.
- El guardrail de salida DETECTA: el modelo ya corrió; lo que se verifica es si
  lo que produjo es aceptable antes de mostrarlo al usuario.
  
Ambos son necesarios porque ninguno es suficiente solo: la entrada puede parecer
inocente y producir una salida problemática (drift de personaje espontáneo); y la
salida puede ser perfectamente correcta incluso si el intento de ataque pasó los
patrones. La defensa en profundidad cubre los modos de fallo de cada capa.

---

## 4. Patrones de coordinación de múltiples agentes

Cuando un sistema necesita varios agentes, hay tres formas de coordinarlos. El
vocabulario y la elección importan: el mismo conjunto de agentes coordinados de
formas distintas tiene propiedades de testabilidad, auditabilidad y coste muy
diferentes.

---

### 4.1 Agent-as-tool / orquestador

**Cómo funciona.** Un agente orquestador llama a otro agente como si fuera una
tool, usando el método `.as_tool(...)` del SDK. El agente interno corre hasta
completarse (puede llamar a sus propias tools en su propio bucle interno) y
devuelve su texto final como resultado de la tool. El control vuelve al
orquestador después de cada llamada.

**En el proyecto.** Es el patrón de M6. El Game Master es el orquestador.
El Rules Referee y el Lore Keeper son agentes especializados expuestos como tools.

El cableado del Rules Referee está en `agents/game_master.py:125-133`:

```python
referee = build_rules_referee(settings)
rules_referee_tool = referee.as_tool(
    tool_name="rules_referee",
    tool_description=(
        "Consult the Rules Referee to resolve the outcome of a risky or "
        "resource-spending action. Describe the action; it returns a ruling "
        "(allowed/disallowed, any dice rolled, a one-line reason)."
    ),
)
```

El Lore Keeper sigue el mismo patrón en `agents/game_master.py:138-146`.

**Propiedad crítica: un hilo único y auditable.** Desde fuera, un agente condujo
el turno. Dentro de ese turno, dos especialistas pudieron ser consultados. El
modo debug muestra un hilo de conversación único con sub-invocaciones anidadas.

**Cuándo usarlo.** Cuando el orquestador necesita retener control, cuando la
decisión de consultar al especialista es contextual (no siempre), y cuando la
auditabilidad es prioritaria.

---

### 4.2 Handoff (transferencia de control)

**Cómo funciona.** Un agente transfiere el control a otro agente y no lo
recupera. El agente receptor corre hasta completarse y su salida es la salida
final del turno. El SDK lo implementa con `handoff(target_agent)`.

**En el proyecto.** No se usa todavía. El motivo: si el Game Master transfiriera
el control al Referee, la salida del turno sería el veredicto del Referee — sin
narración, sin historia, sin las opciones que el Game Master siempre debe ofrecer
al final del turno. Para este caso, el handoff produce el tipo equivocado de
salida.

**Cuándo usarlo.** Cuando el agente originador ha terminado su trabajo y el agente
receptor puede producir la respuesta final completa por sí solo. Ejemplo:
un agente de triaje que identifica el tipo de consulta y transfiere a un
especialista que la resuelve completamente. En el proyecto, los handoffs se
explorarán en bloques futuros de M6, posiblemente cuando un turno sea puramente
de gestión de inventario y el Inventory Keeper pueda resolverlo sin narración del
Game Master.

---

### 4.3 Pipeline / cadena de revisión

**Cómo funciona.** Los agentes se encadenan en una secuencia fija definida por el
código, no por la decisión del modelo. La salida del agente A se convierte en la
entrada del agente B, independientemente del contenido. Es un workflow (el código
controla el flujo, no el modelo), no un agente autónomo.

**En el proyecto.** Es el patrón del agente Critic (M6). El Critic revisa la
respuesta del Game Master antes de que llegue al jugador: si la aprueba, se
muestra; si no, el Game Master regenera la escena. Esa revisión ocurre siempre —
no es una decisión contextual del GM, sino un paso incondicional orquestado en
`main.py` (función `_play_turn`, `main.py:336-378`). La función `_review_scene`
pasa al Critic el estado validado del `GameState` como datos duros, no desde la
memoria del modelo. El cap `MAX_SCENE_RETRIES = 1` (`main.py:46`) garantiza que
un Critic demasiado estricto nunca puede colgar la partida. El veredicto
estructurado (`OK` / `PROBLEM: ...`) es parseado por código (`startswith`), no
por otro modelo.

La propiedad clave que diferencia este patrón de agent-as-tool: la revisión está
garantizada en código, no depende de que el GM llame la tool. Un verificador que
solo a veces verifica no es un verificador.

**Cuándo usarlo.** Cuando una secuencia de pasos debe ocurrir siempre, en un
orden fijo, con cada paso incondicionalmente dependiente del anterior. Útil para
flujos de evaluación, revisión de calidad, o cuando la predecibilidad del flujo
es más importante que la flexibilidad. La distinción clave: si el paso puede
omitirse honestamente (como el Lore Keeper), usa agent-as-tool; si omitirlo
destruye la garantía (como el Critic), usa pipeline.

---

### 4.4 Tabla comparativa y por qué M6 eligió agent-as-tool

| Propiedad | Agent-as-tool | Handoff | Pipeline |
|-----------|--------------|---------|----------|
| Control después de la consulta | Vuelve al orquestador | Se transfiere; no vuelve | El código controla siempre |
| Quién decide cuándo consultar | El orquestador (modelo) | El agente que cede | El código (siempre) |
| Auditabilidad | Un hilo único | Dos trazas independientes | Secuencia fija auditable |
| Flexibilidad | Alta (contextual) | Alta (pero sin retorno) | Baja (fija) |
| Predecibilidad | Media | Baja (depende del receptor) | Alta |
| Latencia por turno | Solo cuando se consulta | Un call por cedente | Siempre todos los pasos |
| Testabilidad | Contratos en constantes, un hilo | Más complejo (dos agentes) | Más fácil (secuencia fija) |

**Por qué M6 eligió agent-as-tool.**

*Razón 1 — Testabilidad y auditabilidad.* El patrón preserva un hilo único de
decisiones. Un handoff divide la traza en dos conversaciones independientes;
reconstruir qué ocurrió requiere unirlas. Para un proyecto cuya primera
obligación es la testabilidad, un hilo auditable es el tradeoff correcto.

*Razón 2 — Control reversible.* El orquestador siempre permanece a cargo. Si el
veredicto del Referee es incorrecto, el Game Master puede narrarlo de una forma
que lo contextualice. Con un handoff, el agente originador desaparece; no hay
fallback. Mantener al GM como autoridad persistente sobre la experiencia del
jugador es una decisión sobre responsabilidad, no solo sobre arquitectura.

*Razón 3 — Adopción incremental.* Desde el punto de vista del Game Master, añadir
el Rules Referee fue añadir una entrada más en su lista de tools. No requirió
restructurar el bucle del juego, ni añadir nuevas invocaciones de `Runner`, ni
lógica de enrutamiento en `main.py`. Esa propiedad — cada especialista es "solo
una tool más" — hace que los bloques restantes de M6 sean simples de añadir.

*Razón 4 — La guía de Anthropic.* La mayoría de sistemas en producción necesitan
un workflow controlado, no otro agente autónomo. Agent-as-tool es el paso mínimo
hacia arriba desde un agente único: una consulta controlada, no una transferencia
de autoridad. Añadir agentes de forma incremental, con el orquestador reteniendo
el control, es el camino que preserva la predecibilidad a medida que el sistema
crece.

---

## 5. Checklist práctico antes de meter un agente

Antes de introducir un nuevo agente (o antes de dar a un agente existente una
nueva capacidad), responde estas preguntas:

**1. ¿Requiere juicio o requiere garantía?**
Si la tarea necesita producir el mismo resultado garantizado para la misma
entrada, pertenece al código. Si necesita interpretar contexto y tomar una
decisión abierta, puede ser un agente.

**2. ¿Puede fallar de forma honesta?**
Si el agente no llama a la tool esperada, ¿el sistema muestra un hueco visible
("not set yet", "no result recorded") o puede producir silenciosamente un valor
falso? Diseña siempre para el primer caso.

**3. ¿Las decisiones están en el código, no en el modelo?**
¿Hay una función Python determinista que evalúa la regla de negocio? ¿El modelo
solo traduce y elige cuándo llamar a esa función? Si el modelo es quien decide
el resultado (no solo cuándo invocar el código que decide), revisa el diseño.

**4. ¿El estado importante persiste via tool call?**
¿Hay una tool que escribe cada dato crítico al estado validado? ¿O existe el
riesgo de que un dato importante viva solo en la narración y se pierda al
recargar?

**5. ¿El sistema es observable?**
¿Puedes ver qué agente trabajó, qué tools llamó, con qué argumentos y qué
devolvieron? Sin esa trayectoria, cualquier fallo será opaco.

**6. ¿El contrato entre agentes es estructurado?**
¿La interfaz de salida del agente es predecible y tipada (un `ActionResult`, una
cadena con formato, enteros)? ¿O es prosa libre que el siguiente agente tendrá
que interpretar con margen de error?

**7. ¿Qué patrón de coordinación es el adecuado?**
- ¿El orquestador necesita retener el control y la decisión de consultar es
  contextual? → agent-as-tool.
- ¿El agente originador no tiene más trabajo que hacer y el receptor puede
  resolver el turno completamente? → handoff.
- ¿El paso debe ocurrir siempre, en un orden fijo, de forma incondicional? →
  pipeline.

**8. ¿Cuál es la tasa de cumplimiento esperada, y qué ocurre si es baja?**
Define de antemano cómo medirás si el agente cumple su trabajo (M8 es el
milestone dedicado a esto). Y define qué harás si la tasa es baja: ¿un prompt
más preciso? ¿pasar a código determinista? Saber la respuesta antes de
implementar evita sorpresas.

**9. ¿La entrada y la salida necesitan guardrails?**
¿Puede un usuario malintencionado (o un input externo) inyectar una instrucción
en el mensaje del agente? ¿Puede el agente producir una respuesta que rompa las
restricciones de negocio o de seguridad? Si la respuesta a cualquiera de las dos
preguntas es sí, añade guardrails — no instrucciones de prompt que pidan al modelo
que resista, sino controles en el camino de evaluación del SDK. Define el guardrail
más barato primero (patrones deterministas, cero coste); añade el más potente
encima (LLM judge) para los casos que el barato no puede alcanzar.

---

## 6. Puente a QA y TestOps AI

Los principios de esta guía son transferibles directamente a un sistema de QA con
agentes porque el problema estructural es el mismo: necesitas que algunas cosas
ocurran siempre (los veredictos de test son correctos), que algunas cosas fallen
de forma honesta (un test sin resultado dice "sin datos", no "PASÓ"), y que el
sistema sea observable (puedes auditar por qué un agente marcó un test de
determinada manera).

| Este proyecto (Dungeon Agents) | En un sistema de QA con agentes (TestOps AI) |
|-------------------------------|---------------------------------------------|
| `can_afford` decide si una acción es asequible; el modelo traduce la historia a números | Una función de aserción decide si el test pasa; el agente traduce la salida del sistema al argumento de la aserción |
| `validate_action` fue reemplazada porque delegaba la decisión al modelo con un nombre que prometía determinismo | Cualquier función de QA llamada `validate_*` que delega la decisión al modelo está igualmente mal diseñada |
| El Rules Referee arbitra; el Lore Keeper registra narrativa; el Game Master narra | Un agente "Evaluador" decide pass/fail; un agente "Recorder" escribe el resultado; un agente "Orchestrator" conduce la ejecución |
| Un tool call es la frontera entre narración y hecho persistente | Un tool call es la frontera entre "el agente dijo que el test pasó" y "el resultado está en la base de datos de test runs" |
| "not set yet" en vez de un valor fabricado | "sin resultado" en vez de heredar el resultado anterior del mismo test |
| El debug mode muestra la trayectoria completa de tool calls | El registro de auditoría de un pipeline de QA debe mostrar qué agente evaluó qué aserción y qué devolvió |
| La tasa de cumplimiento del Lore Keeper es una métrica medible | La tasa de precision de los veredictos del agente evaluador es el KPI central del producto |
| `detect_injection` + Injection Judge: guardrail de entrada en 2 capas (M7) | Un pipeline de QA puede ser atacado: un agente de generación de tests puede recibir descripciones maliciosas diseñadas para producir veredictos falsos positivos. La misma arquitectura aplica: filtro determinista primero, juez LLM segundo |
| Character Judge: guardrail de salida que detecta ruptura de personaje (M7) | Un agente de QA que "rompe personaje" es uno que emite veredictos fuera de su criterio definido — dice "PASÓ" por razones no relacionadas con la aserción. Un guardrail de salida puede detectarlo antes de que el veredicto llegue al informe |
| Defensa en profundidad: input capa1 → input capa2 → modelo → Critic + Character Judge (M7) | Arquitectura de calidad en capas: pre-filtro de artefacto → validación semántica → evaluación del agente → revisión de coherencia + revisión de rol → resultado persistido |

Para más detalle sobre estas conexiones, ver
[aplicaciones-de-agentes-en-qa.md](aplicaciones-de-agentes-en-qa.md) (sección 5,
"El puente concreto a TestOps AI") y el capítulo 8 del documento de milestone M6
([docs/milestones/milestone-06-multi-agent.md](milestones/milestone-06-multi-agent.md)).

Para recursos externos sobre evaluación de agentes y QA de sistemas no
deterministas, ver
[recursos-para-seguir-aprendiendo.md](recursos-para-seguir-aprendiendo.md)
(sección 5, herramientas de evaluación: DeepEval, Promptfoo, LangSmith).
