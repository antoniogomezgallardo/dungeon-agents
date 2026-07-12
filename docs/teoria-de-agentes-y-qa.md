# Teoría de agentes de IA y su aplicación a QA

> Documento de aprendizaje del proyecto **Dungeon Agents**. Es una guía
> conceptual (no un doc de milestone): empieza desde cero con la teoría de
> agentes y aterriza en cómo esa teoría se aplica al testing / QA — el puente
> hacia el futuro producto **TestOps AI**. Está escrito para leerse de principio
> a fin, sin dar nada por sabido. Las afirmaciones importantes están respaldadas
> por fuentes citadas al final.

---

## Cómo leer este documento

Está en dos mitades:

- **Parte I — Teoría de agentes** (secciones 1 a 7): qué es un agente, de dónde
  viene la idea, cómo funciona el bucle, qué son las tools, y las distinciones
  clave. Se apoya en el código real de Dungeon Agents como ejemplo vivo.
- **Parte II — Aplicación a QA** (secciones 8 a 12): por qué todo lo anterior
  importa para testing, los dos usos de la IA en QA, el problema del "oráculo",
  el no-determinismo, y cómo diseñar agentes de QA que fallen de forma honesta.

Si algo no encaja, vuelve al ejemplo de código: la teoría abstracta se vuelve
concreta cuando la ves en `main.py`, `game_master.py`, `game_tools.py` y
`domain/`.

---

# PARTE I — TEORÍA DE AGENTES

## 1. Qué es un agente (la definición clásica, anterior a los LLM)

La idea de "agente" no nació con ChatGPT. Es un concepto fundacional de la
Inteligencia Artificial. La definición estándar, del libro de referencia de la
disciplina (Russell & Norvig, *Artificial Intelligence: A Modern Approach*), es:

> Un **agente** es cualquier cosa que **percibe su entorno mediante sensores** y
> **actúa sobre ese entorno mediante actuadores**.

Un termostato es un agente trivial: percibe la temperatura (sensor) y enciende o
apaga la calefacción (actuador). Un robot aspirador es un agente. Un humano es un
agente. Lo que los distingue es su grado de **racionalidad**: un *agente
racional* elige, en cada momento, la acción que se espera que maximice su
objetivo, dada la información que percibe.

De aquí sale el **bucle de percepción-acción**, que ha sido la estructura básica
de un agente racional desde 1995:

```
percibir el entorno  ->  razonar sobre las opciones  ->  actuar  ->  observar el
resultado  ->  (volver a empezar)
```

Retén esta imagen. Todo lo que viene después —incluidos los agentes con LLM— es
una variación de este mismo bucle.

*(Fuentes: [1], [2].)*

---

## 2. Qué añade un LLM: el "cerebro en un tarro"

Un **modelo de lenguaje grande** (LLM: Claude, GPT, etc.) es, en esencia, una
**función pura de texto a texto**: le das una secuencia de texto (el *prompt*) y
te devuelve una continuación probable. Nada más.

Esto es crucial de entender, porque explica todas sus limitaciones:

- **No tiene memoria** entre llamadas. Cada invocación es independiente; lo único
  que "recuerda" es lo que le vuelves a meter en el prompt.
- **No puede actuar** sobre el mundo. No puede leer un archivo, tirar un dado,
  llamar a una API, ni consultar la hora. Solo produce texto.
- **No tiene fuente de verdad.** Si le preguntas cuánto oro tienes, se lo
  *inventa* de forma plausible a partir del contexto.

Es un cerebro potente flotando en un tarro, desconectado del mundo. Por sí solo
no es un agente: le falta percibir y actuar de verdad.

En Dungeon Agents ese cerebro es `claude-haiku-4-5`, y el único módulo que sabe
qué modelo hay detrás es
[config.py](../src/dungeon_agents/config.py) — el resto del código no depende del
vendor.

---

## 3. De "cerebro en un tarro" a agente: los tres ingredientes

Un **agente con LLM** es ese cerebro conectado al mundo mediante tres cosas.
Aquí es donde la teoría clásica de la sección 1 y el LLM de la sección 2 se
juntan:

| Ingrediente | Qué aporta | En Dungeon Agents |
|---|---|---|
| **Instrucciones** | El objetivo y el contrato de comportamiento (quién es, qué debe y no debe hacer). | `GAME_MASTER_INSTRUCTIONS` en [game_master.py](../src/dungeon_agents/agents/game_master.py) |
| **Tools (herramientas)** | Sus *actuadores* y *sensores*: funciones reales que puede pedir ejecutar para tocar el mundo. | Las 10 funciones de [game_tools.py](../src/dungeon_agents/tools/game_tools.py) |
| **Un loop (bucle)** | El runtime que le pasa mensajes, ejecuta las tools que pide, y le devuelve los resultados, en ciclo. | `Runner.run_sync(...)` en el `while True` de [main.py](../src/dungeon_agents/main.py) |

La definición práctica que usa Anthropic (creadora de Claude) lo resume bien:

> Los **agentes** son sistemas donde el LLM **dirige dinámicamente sus propios
> procesos y el uso de herramientas**, manteniendo el control sobre cómo lograr
> una tarea.

La frase clave es "dirige dinámicamente". El modelo decide, sobre la marcha, qué
hacer a continuación. Eso lo diferencia de un *workflow* (ver sección 7).

*(Fuente: [3].)*

> **Idea para grabar #1:** un agente = LLM (el que decide) + tools (sus manos) +
> un loop (quien ejecuta lo que pide y le devuelve la realidad).
> **El modelo decide; tu código actúa.**

---

## 4. El bucle agéntico, paso a paso

Esta es la mecánica que más cuesta interiorizar, así que vamos despacio con un
ejemplo real: el jugador escribe *"ataco al goblin"*.

```
1. Tu código llama a Runner.run_sync(game_master, conversacion)
      |
      v
2. El SDK manda al modelo:  [instrucciones]  +  [historia de la partida]  +
   ["ataco al goblin"]  +  la LISTA de tools disponibles (nombre, descripcion,
   parametros de cada una).
      |
      v
3. El modelo responde UNA de dos cosas:

   (a) Texto normal          ->  "Blandes tu espada contra el goblin..."
                                  Esto es el FIN del turno.

   (b) "Quiero llamar a       ->  NO es el fin todavia. Es una PETICION de accion.
        roll_dice(sides=20)"
      |
      v
4. Si fue (b): el SDK ejecuta TU funcion roll_dice(20) de verdad (codigo Python
   real, no el modelo), obtiene por ejemplo "Rolled a 14", y le devuelve ese
   resultado al modelo como un mensaje mas del contexto.
      |
      v
5. VUELVE al paso 3, ahora con "Rolled a 14" en el contexto. El modelo ya sabe
   que salio 14 y narra: "Tu golpe acierta limpiamente y el goblin retrocede..."
      |
      v
6. Cuando el modelo responde solo texto (sin pedir mas tools) -> turno terminado.
   Ese texto final es result.final_output, y es lo que ve el jugador.
```

Los dos puntos contraintuitivos, y por eso la mayoría malentiende los agentes:

- **El modelo nunca ejecuta nada.** Solo *pide* llamar a una tool. Quien ejecuta
  el código real es el runtime (el SDK), y luego le devuelve al modelo lo que
  pasó de verdad. El modelo "actúa sobre el mundo" solo indirectamente, a través
  de tus funciones.
- **Un turno puede llamar al modelo varias veces.** No es "una llamada por
  turno". Es modelo → tool → resultado → modelo → tool → resultado → … hasta que
  el modelo decide que ya terminó y responde texto puro. Este encadenamiento es
  precisamente lo que hace "agente" a un agente.

Este patrón —intercalar **razonar** y **actuar** en un bucle— tiene nombre y
origen académico: el framework **ReAct** ("Reasoning + Acting", Yao et al.,
2022). Su hallazgo central es que dejar que el modelo intercale pensamiento y
acciones que consultan el mundo real **reduce las alucinaciones**, porque el
modelo comprueba la realidad (tira el dado, consulta la API) en vez de
inventársela. Es exactamente lo que consigues obligando al Game Master a llamar a
`roll_dice` en vez de inventar el número.

En Dungeon Agents no ves ese ida y vuelta interno porque `run_sync` lo resuelve
entero y te da solo el `final_output`. Pero al activar el comando **`debug`** lo
ves: cada línea `[debug] -> tool roll_dice…` es **una vuelta** del bucle interno.

*(Fuentes: [3], [4], [5].)*

> **Idea para grabar #2:** el bucle agéntico es *modelo → (¿pide tool? → ejecuta →
> repite) → texto final*. El modelo no ejecuta; **pide**. Tu runtime ejecuta y le
> devuelve la realidad.

---

## 5. Las tools: cómo el modelo "elige" una función

Una **tool** es simplemente una función normal que le has *descrito* al modelo.
El SDK hace la magia de traducción. Mira una tool real de Dungeon Agents:

```python
@function_tool
def add_item(item_name: str, quantity: int = 1) -> str:
    """Give the player an item (e.g. loot, a purchase, a reward).

    Args:
        item_name: The item to add.
        quantity: How many to add (must be positive).
    """
    return _apply(rules.add_item(_load_or_new_state(), item_name, quantity))
```

Tres cosas que parecen detalles y son el mecanismo entero:

### (a) El docstring ES el prompt de la tool
Ese texto entre `"""..."""` **no es documentación para ti** — el SDK se lo pasa
al modelo como la descripción de la tool. Es lo que el modelo lee para decidir
*cuándo* y *cómo* usarla. Por eso están escritos en imperativo, dirigidos al
modelo ("Call this when…", "Never remove items the player doesn't have"). Cambiar
un docstring cambia el comportamiento del agente sin tocar una línea de lógica.

### (b) La firma de tipos ES el contrato de entrada
`def add_item(item_name: str, quantity: int = 1)` → el SDK convierte esos type
hints en un **esquema JSON** que le dice al modelo exactamente qué parámetros
mandar y de qué tipo. Los type hints no son decorativos: son la validación de la
entrada de la tool.

### (c) El modelo elige el nombre + los argumentos; tu código hace el resto
Cuando el modelo "llama a una tool", lo que realmente produce es un pequeño JSON:
`{"tool": "add_item", "item_name": "torch", "quantity": 2}`. El SDK lo recibe,
encuentra tu función `add_item`, la ejecuta con esos argumentos, y le devuelve el
resultado. El modelo nunca corre tu código; solo dice *qué* quiere correr.

> **Idea para grabar #3:** una tool = una función + su descripción (docstring) +
> su firma tipada. El modelo lee la descripción para *elegir* la tool y produce un
> JSON de argumentos; el runtime la *ejecuta*.

---

## 6. La arquitectura en dos capas: la decisión más importante

Aquí está la decisión de diseño que más te va a servir en QA. Fíjate en que la
tool `add_item` de arriba **no contiene lógica de negocio**: solo carga el
estado, delega en una regla, y guarda. La lógica real vive en otra capa:

```
tools/game_tools.py        <- CAPA FINA. Toca el SDK. Solo traduce. Sin reglas.
      |  delega en
      v
domain/rules.py            <- CAPA DE DOMINIO. Python puro, CERO SDK.
                              Aqui viven las reglas de verdad, con validacion.
                              Testeable sin API key, en milisegundos.
```

Por qué esto es oro:

- **`domain/` es Python puro sin dependencia del SDK.** Puedes probarlo
  exhaustivamente **sin API key, sin llamar al modelo, sin gastar dinero, y de
  forma 100% determinista**. Por eso Dungeon Agents tiene 81 tests que corren en
  un instante.
- **La capa `tools/` es fina a propósito.** Su único trabajo es darle al modelo
  una forma de invocar el dominio y traducir excepciones a mensajes que el modelo
  entienda. Ninguna regla vive aquí.
- **El modelo solo *elige* qué regla llamar; la regla *decide* si se permite.**
  El modelo puede pedir "gasta 100 de oro", pero `rules.spend_gold` es quien
  comprueba si tienes 100 y se niega si no. La corrección no depende de que el
  modelo se porte bien.

> **Idea para grabar #4:** separa **el QUÉ** (reglas deterministas, en `domain/`,
> testeadas a fondo) de **el CÓMO lo invoca el agente** (wrappers finos, en
> `tools/`). Empuja toda la lógica que puedas *fuera* del modelo. Un test del
> dominio es barato, rápido y reproducible; un test que necesita al modelo es
> caro, lento y no determinista.

Corolario, y esto es de las lecciones más profundas del proyecto: **la memoria
del modelo NO es la fuente de verdad.** En Dungeon Agents la verdad vive en un
archivo validado en disco (`data/game_state.json`). Cada tool sigue un patrón
*cargar → modificar → guardar*. Y los comandos `stats` / `inventory` / `summary`
**no le preguntan al modelo**: leen ese estado validado directamente, así que son
siempre exactos. El modelo *narra*; el estado validado *manda*.

---

## 7. Agente vs. workflow: no todo debe ser un agente

Una distinción de Anthropic que evita el error más común (usar un agente donde no
hace falta):

- **Workflow:** los LLM y las tools se orquestan por **caminos de código
  predefinidos**. *Tú* controlas el flujo. Predecible, consistente, fácil de
  testear. Bueno para tareas bien definidas.
- **Agente:** el LLM **dirige dinámicamente** su propio flujo y su uso de tools.
  *El modelo* controla el flujo. Flexible, pero menos predecible. Bueno cuando la
  tarea necesita decisiones abiertas a escala.

Anthropic lo resume así: *"con un workflow, tú controlas la fontanería; con un
agente, el modelo controla la fontanería"*. Y su consejo, importante para un
perfil de QA: **la mayoría de sistemas en producción no necesitan otro agente
autónomo; necesitan un workflow con pasos claros, tools ajustadas y resultados
medibles.** Usa el agente cuando la flexibilidad justifique perder
predecibilidad.

Dungeon Agents es hoy un **agente** (el Game Master decide libremente qué tools
usar). En M6 evolucionará hacia algo más orquestado (varios agentes
especializados), que es un punto intermedio interesante entre workflow y agente
puro.

*(Fuentes: [3].)*

> **Idea para grabar #5:** "agente" no es sinónimo de "mejor". Cuanta más
> autonomía le das al modelo, menos predecible es el sistema. Elige el nivel de
> autonomía *mínimo* que resuelva el problema. En testing, la predecibilidad vale
> oro.

---

# PARTE II — APLICACIÓN A QA

Ahora conectamos cada idea de la Parte I con el testing. El puente entre este
juego y **TestOps AI** no es el tema (RPG vs. QA); es que **los mismos patrones de
diseño** —tools deterministas, estado como fuente de verdad, fallo honesto,
observabilidad— son exactamente lo que necesita un sistema de QA fiable.

## 8. Los dos usos de la IA en QA (no los confundas)

Hay dos cosas muy distintas que la gente mezcla al hablar de "IA en testing":

1. **Usar agentes para HACER testing.** Un agente que percibe el estado de una
   aplicación, planifica un objetivo de prueba, ejecuta acciones, evalúa el
   resultado y adapta su comportamiento — generación de tests a partir de
   historias de usuario, exploración autónoma, *self-healing* de selectores que
   cambian, triaje de fallos. Aquí el agente es la **herramienta de QA**.

2. **Hacer QA de sistemas que SON agentes.** Probar software que es **no
   determinista por diseño** (un LLM, un agente). Esto es, según el consenso de
   2026, *el reto nuevo más difícil* para los equipos de QA, porque los scripts
   de test tradicionales no se diseñaron para salidas que varían entre
   ejecuciones. Aquí el agente es el **objeto bajo prueba**.

TestOps AI vivirá en el uso (1), pero tendrá que dominar (2) para probarse a sí
mismo. Las secciones siguientes te dan el marco para ambos.

*(Fuentes: [6], [7].)*

---

## 9. El problema del oráculo, y por qué el estado validado lo resuelve a medias

En testing, un **oráculo** es el mecanismo que decide si un resultado es correcto.
Con software clásico es fácil: `assert suma(2, 2) == 4`. El oráculo es la igualdad
exacta.

Con un agente, el oráculo se rompe: no hay *una* respuesta correcta. "Blandes tu
espada contra el goblin" y "Alzas tu acero hacia la criatura" son ambas válidas.
No puedes hacer `assert salida == "texto exacto"`.

La técnica que exige 2026 es **comprobar contra una distribución de respuestas
aceptables, no contra un único valor correcto**. En la práctica esto se traduce en
oráculos más débiles pero robustos: comprobar propiedades ("¿la respuesta menciona
al goblin?", "¿ofrece 2-3 opciones?", "¿el JSON valida contra el esquema?") en vez
de igualdad literal.

Aquí está la lección de diseño que ya aplicaste en Dungeon Agents sin saber que
resolvía el problema del oráculo:

> **Todo lo que PUEDA ser determinista, hazlo determinista, y ponle un oráculo
> fuerte (igualdad exacta). Solo lo que sea irremediablemente abierto (la
> narración) se queda con un oráculo débil (comprobación de propiedades).**

Por eso separaste `roll_dice` y las reglas de `domain/` (deterministas, con tests
de igualdad exacta) de la narración del Game Master (abierta, no testeada por
igualdad). Cuanto más empujas hacia el lado determinista, más de tu sistema queda
cubierto por oráculos fuertes y baratos.

*(Fuentes: [6], [7].)*

---

## 10. No-determinismo, flakiness y reproducibilidad

Un test **flaky** es uno que a veces pasa y a veces falla sin que cambie el
código. Con sistemas de IA el flakiness deja de ser un accidente y pasa a ser
**intrínseco**: un agente puede tomar un camino distinto en cada ejecución, así
que un bug que aparece en la ejecución 1 puede no reproducirse en la 2.

El consejo de los arquitectos de QA de 2026 es revelador: **el trabajo no es
eliminar la flakiness, sino operacionalizar una decisión —arreglar, reintentar o
poner en cuarentena— para cada test inestable antes de que erosione la confianza
en el pipeline.**

Cómo se combate el no-determinismo, y cómo ya lo hiciste en el juego:

- **Inyección de dependencias para reproducibilidad.** En Dungeon Agents, la
  aleatoriedad del dado y la ruta del archivo de estado se pueden *inyectar*
  (RNG con semilla, `tmp_path` en tests). Eso convierte algo aleatorio en algo
  reproducible bajo test. En QA de IA harás lo mismo: fijar semillas, congelar
  temperaturas, y aislar la fuente de variación.
- **Estado externo y validado, no memoria del modelo.** Un resultado que vive en
  un archivo validado es reproducible y auditable; un "recuerdo" del modelo no lo
  es.
- **Registro de la trayectoria.** Para depurar un fallo no reproducible necesitas
  ver *qué camino tomó el agente*. Eso lo dan los hooks (sección 11).

*(Fuentes: [6], [8].)*

> **Idea para grabar #6:** el no-determinismo no se elimina, se *gestiona*. La
> reproducibilidad se diseña: inyecta las fuentes de variación (semillas, rutas,
> tiempo) para poder fijarlas bajo test.

---

## 11. Observabilidad: no puedes hacer QA de una caja negra

Un agente es una caja negra por defecto: ves la salida final, no las decisiones
intermedias. Para hacer QA de él —o para depurarlo— necesitas ver *qué tools
llamó, con qué argumentos, qué devolvieron y cuánto tardaron*. Esa es la
**trayectoria** del agente.

En Dungeon Agents eso son los **hooks** (`RunHooks` en
[main.py](../src/dungeon_agents/main.py)): `on_agent_start`, `on_tool_start`,
`on_tool_end`. El SDK los llama automáticamente alrededor del trabajo del agente;
son su punto de auditoría oficial. Los diseñaste *off por defecto* (opt-in vía el
comando `debug` o `DUNGEON_DEBUG`), de modo que el juego normal queda limpio pero
la ventana a las tripas está a un comando de distancia.

En TestOps AI esto no es un lujo, es un requisito: necesitas un **registro
auditable de cada decisión del agente** para poder afirmar que un test se ejecutó
como debía. Un veredicto de QA sin trazabilidad no vale nada. (Además, ese mismo
`on_agent_start` es lo que te dejará ver *qué agente* trabaja cuando en M6 haya
varios colaborando.)

> **Idea para grabar #7:** un agente sin observabilidad es intesteable e
> inauditable. La trayectoria (qué tools, qué argumentos, qué resultados) es tan
> importante como la salida final.

---

## 12. La lección capital: fallo honesto vs. fallo engañoso

Esta es la lección más importante del proyecto para un perfil de QA, y la
descubriste **probando** el juego, no leyéndola.

Le dijiste al Game Master, en sus instrucciones, que llamara a `set_location` y
`set_quest` en la primera escena. Y con `claude-haiku-4-5`, **a veces no lo
hace.** El código está perfecto; el modelo es el eslabón variable. Tu reacción
correcta fue: en vez de mostrar un valor falso que contradice la historia,
mostrar **"not set yet"** — un hueco honesto y visible.

Destílalo así:

> **Un prompt empuja probabilidades, no garantías.**
> - Lo que **DEBE** ocurrir siempre → va en **código determinista** (las reglas
>   de `domain/`: no puedes gastar oro que no tienes; la HP no baja de 0). El
>   modelo no puede saltárselo.
> - Lo que **depende del modelo** (que se acuerde de llamar a una tool) →
>   diséñalo para **fallar de forma honesta y visible** ("not set yet"), **nunca
>   de forma engañosa** (un valor inventado que parece verdad).

Esto conecta con el problema más temido de la IA en QA: el **falso positivo
silencioso**. Un agente de QA que se olvide de registrar el resultado de un test
debe mostrar **"sin datos"**, jamás inventar un **"PASÓ"**. El peor caso
aceptable es un hueco visible; un falso positivo silencioso es catastrófico,
porque destruye lo único que un sistema de QA vende: **confianza en su veredicto**.

Por eso el consenso de 2026 insiste en *auditar los guardrails* y *stress-testear*
los agentes con entradas adversas: precisamente para cazar los modos en que un
agente falla de forma plausible pero silenciosa.

**Guardrails — la distinción prevención/detección, ya demostrada en el proyecto
(M7).** Un guardrail de *entrada* previene: el mensaje nunca llega al modelo, el
modelo nunca genera respuesta, el turno se descarta limpiamente. Un guardrail de
*salida* detecta: el modelo ya corrió; el guardrail verifica si lo que produjo es
aceptable antes de entregarlo al usuario. En Dungeon Agents, el Injection Judge
(entrada) y el Character Judge (salida) son los dos ejes de esta defensa. El mismo
patrón aplica a QA: un agente de QA puede recibir inputs adversos diseñados para
que produzca veredictos falsos (ataque de entrada), y puede *drift* espontáneo
hacia veredictos fuera de su criterio definido (fallo de salida). Los guardrails
de entrada/salida son controles de calidad del agente, no solo de seguridad.

> **Idea para grabar #8 (la más importante):** diseña siempre para que el fallo
> del modelo sea *ruidoso y honesto*, no *silencioso y plausible*. En QA, un hueco
> visible es aceptable; un falso positivo silencioso es inaceptable.

---

## Resumen: las 8 ideas para grabar

**Teoría de agentes**
1. Un agente = LLM (decide) + tools (manos) + loop (ejecuta). *El modelo decide;
   tu código actúa.*
2. El bucle agéntico: modelo → (¿pide tool? → ejecuta → repite) → texto final. El
   modelo pide; el runtime ejecuta.
3. Una tool = función + docstring (que el modelo lee) + firma tipada (el
   contrato). El modelo elige; el runtime ejecuta.
4. Separa el QUÉ (reglas deterministas en `domain/`) del CÓMO lo invoca el agente
   (`tools/` finas). Empuja la lógica fuera del modelo.
5. "Agente" no es sinónimo de "mejor". Elige la autonomía mínima que resuelva el
   problema; la predecibilidad vale oro.

**Aplicación a QA**
6. El no-determinismo no se elimina, se gestiona. La reproducibilidad se diseña
   (inyecta semillas, rutas, tiempo).
7. Un agente sin observabilidad es intesteable. La trayectoria importa tanto como
   la salida.
8. Fallo honesto, nunca engañoso. Un hueco visible es aceptable; un falso positivo
   silencioso es el pecado capital del QA.

---

## Fuentes

1. Russell, S. & Norvig, P. *Artificial Intelligence: A Modern Approach* — el
   texto de referencia de la disciplina desde 1995; define al agente como aquello
   que percibe su entorno mediante sensores y actúa mediante actuadores, y
   codifica el bucle percepción-acción del agente racional.
2. *LLM-based Agentic Reasoning Frameworks: A Survey* (arXiv:2508.17692) —
   sitúa a los agentes LLM como sistemas que integran planificación, memoria y uso
   de herramientas sobre un LLM. <https://arxiv.org/html/2508.17692v1>
3. Anthropic, *Building Effective Agents* — distinción agente vs. workflow ("con
   un agente, el modelo controla la fontanería"), definición de agente y consejo
   de no sobre-usar agentes.
   <https://www.anthropic.com/engineering/building-effective-agents>
4. Yao, S. et al. (2022). *ReAct: Synergizing Reasoning and Acting in Language
   Models* (arXiv:2210.03629) — el framework de intercalar razonamiento y acción
   en un bucle; reduce alucinaciones al consultar el mundo real.
   <https://arxiv.org/abs/2210.03629>
5. Oracle Developers, *What Is the AI Agent Loop?* — descripción del bucle
   agéntico (el LLM invoca tools en un ciclo iterativo hasta completar la tarea).
   <https://blogs.oracle.com/developers/what-is-the-ai-agent-loop-the-core-architecture-behind-autonomous-ai-systems>
6. *Testing AI Agents in 2026: How to QA LLM-Powered Apps* — el reto de probar
   software no determinista por diseño; comprobar contra una distribución de
   respuestas aceptables en vez de un único valor.
   <https://www.testbooster.ai/en/blog/testing-ai-agents-in-2026-how-to-qa-llm-powered-apps>
7. *Agentic Testing 2026 — Proven QA Guide for AI Agents* — agentes de testing que
   perciben, planifican, ejecutan y adaptan; generación de tests y self-healing.
   <https://aitestingguide.com/agentic-testing/>
8. *Playwright Flaky Tests: 2026 Diagnostic Playbook* — el trabajo del QA no es
   eliminar la flakiness sino operacionalizar arreglar/reintentar/cuarentena.
   <https://testquality.com/playwright-flaky-tests-diagnostic-playbook-2026/>

> Nota sobre las fuentes: [1], [3] y [4] son fuentes primarias y de máxima
> fiabilidad (el libro de referencia del campo, el equipo que construye Claude, y
> el paper académico original de ReAct). El resto son material técnico actual
> (2026) sobre QA con IA; útiles para el estado del arte, pero de menor autoridad
> que las primarias — contrástalas si vas a apoyarte en un dato concreto.
