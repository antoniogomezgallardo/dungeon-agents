# Agentes en QA: por qué, para qué, y qué buscan las empresas

> Segundo documento de aprendizaje del proyecto **Dungeon Agents**. El
> [primero](teoria-de-agentes-y-qa.md) explica la *teoría* de agentes y su
> aplicación a QA a nivel conceptual. Este es más práctico y responde a tres
> preguntas concretas:
>
> 1. ¿Por qué en QA *necesitamos* agentes? ¿Qué problema real resuelven?
> 2. ¿Cuáles son las principales aplicaciones de agentes (con ejemplos sencillos)?
> 3. Cuando una empresa busca un QA con experiencia en agentes, **¿para qué trabajo
>    lo quiere?**
>
> Igual que el primero, se apoya en fuentes citadas al final y distingue las
> fiables (primarias) del material de estado del arte.

Requisito previo recomendado: lee antes [teoria-de-agentes-y-qa.md](teoria-de-agentes-y-qa.md).
Aquí damos por sabido qué es un agente, el bucle agéntico y las tools.

---

## 1. Primero, ¿por qué en QA necesitamos agentes?

No los necesitamos *siempre*. Los necesitamos cuando el problema tiene una forma
concreta. Para verlo, compara cómo trabaja el testing tradicional y dónde se
rompe.

**El testing tradicional es un script fijo.** Escribes: "abre esta página, pulsa
este botón, comprueba que aparece este texto". Es rápido, barato y **repetible**.
Pero tiene tres puntos ciegos:

1. **Es frágil ante el cambio.** Si el botón cambia de sitio o de nombre, el test
   se rompe aunque la app funcione. Alguien tiene que arreglarlo a mano.
2. **Solo prueba lo que se te ocurrió escribir.** No explora. No descubre el
   camino raro que rompe la app; solo recorre el que tú ya conocías.
3. **No sabe testear salidas abiertas.** `assert respuesta == "texto exacto"` no
   sirve cuando la respuesta correcta puede tener mil formas válidas — justo el
   caso de cualquier sistema con IA (el "problema del oráculo" del documento 1).

Un **agente** aporta exactamente lo que le falta al script: **puede percibir el
estado, decidir qué hacer a continuación y adaptarse**. Esa es la definición de
agente del documento 1 (percibir → razonar → actuar → observar), aplicada a la
tarea de probar software.

De ahí salen las tres razones por las que QA adopta agentes:

- **Para no reescribir tests a mano cada vez que la UI cambia** → *self-healing*:
  el agente vuelve a localizar el botón aunque haya cambiado, porque entiende la
  *intención* ("el botón de comprar"), no una coordenada fija.
- **Para descubrir lo que no anticipaste** → *exploración autónoma*: el agente
  navega la app buscando problemas por su cuenta, como haría un tester manual
  curioso, pero incansable.
- **Para poder testear sistemas de IA** → los productos modernos incorporan LLMs,
  y probarlos exige comparar contra un *rango* de respuestas aceptables, algo que
  un script rígido no puede hacer pero un evaluador con criterio (a menudo otro
  agente) sí.

*(Fuentes: [1], [2], [3].)*

> **La regla honesta:** un agente NO sustituye a los tests deterministas. Los
> *complementa* donde el determinismo no llega (cambio de UI, exploración, salidas
> abiertas). Todo lo que puedas cubrir con un `assert` exacto y barato, cúbrelo
> así — como hiciste con las reglas de `domain/` en Dungeon Agents. El agente es
> para lo que ese `assert` no puede.

---

## 2. Las principales aplicaciones de agentes (con ejemplos sencillos)

Antes de centrarnos en QA, conviene ver el mapa general de para qué se usan los
agentes, porque QA reutiliza estos mismos patrones. Estas son las grandes familias
de aplicaciones, cada una con un ejemplo mínimo.

### a) Atención al cliente que *actúa*
No un chatbot que solo responde, sino uno que **usa tools**: busca tu pedido,
emite un reembolso, abre un ticket. Es literalmente el patrón de Dungeon Agents
(un modelo que decide qué tool llamar), aplicado a soporte.
- *Ejemplo sencillo:* "¿Dónde está mi pedido?" → el agente llama a
  `buscar_pedido(id)`, ve que está retenido, llama a `crear_ticket(...)` y te
  responde con el estado real. Vodafone reporta que un sistema así atiende >70% de
  las consultas sin intervención humana.

### b) Programación (coding agents)
Agentes que leen un repo, planifican un cambio, editan archivos, corren los tests
y iteran hasta que pasan. **Claude Code —la herramienta con la que estás
trabajando ahora mismo— es uno de ellos.**
- *Ejemplo sencillo:* "arregla este bug" → el agente localiza el archivo, hace el
  cambio, ejecuta la suite de tests, ve que uno falla, ajusta, y repite hasta
  verde. Un humano revisa el resultado final.

### c) Búsqueda e investigación (research agents)
Agentes que responden preguntas cuya respuesta está repartida en muchas fuentes,
y producen un informe con citas. (Es justo lo que hice para escribir estos dos
documentos: buscar, contrastar, citar.)
- *Ejemplo sencillo:* "lista las empresas del sector tecnológico del S&P 500 y sus
  consejeros" — una sola búsqueda no basta; el agente encadena varias, sintetiza y
  cita. Anthropic construyó un asistente interno exactamente para esto.

### d) Automatización de procesos de negocio
Agentes que orquestan flujos entre varios sistemas y, a diferencia de la
automatización clásica, **manejan excepciones y variaciones** en vez de romperse.
- *Ejemplo sencillo:* procesar documentación de envíos: leer la factura, validar
  datos, corregir formatos raros, cargar al sistema. Una logística reportó -83% de
  errores y -62% de tiempo con este enfoque.

### e) Tareas de horizonte largo (long-horizon)
Agentes que trabajan de forma continuada durante minutos, horas o días — una
migración de código grande, una investigación extensa — parándose solo en puntos
de control estratégicos para que un humano revise.
- *Ejemplo sencillo:* migrar 400 archivos de una librería vieja a una nueva: el
  agente hace uno, verifica, hace el siguiente, y te avisa solo si algo no encaja.

*(Fuentes: [1], [2], [4].)*

> Fíjate en el hilo común: **todas** son el mismo bucle del documento 1 (percibir →
> razonar → actuar con tools → observar → repetir). Cambia el dominio, no el
> mecanismo. Por eso aprender un agente bien (como el Game Master) te transfiere a
> todos los demás.

---

## 3. Esas mismas aplicaciones, dentro de QA

Ahora aterrizamos las familias de arriba en tareas concretas de testing. Un agente
de QA es un agente que percibe el estado de una aplicación, se fija un objetivo de
prueba, ejecuta acciones, evalúa el resultado y adapta su comportamiento. Sus usos
principales:

| Aplicación de QA | Qué hace el agente | Ejemplo sencillo |
|---|---|---|
| **Generación de tests** | Convierte requisitos o historias de usuario en tests ejecutables. | "Como usuario quiero recuperar mi contraseña" → el agente genera los casos: email válido, email inexistente, enlace caducado. |
| **Exploración autónoma** | Navega la app buscando fallos sin un guion previo. | Suelto al agente en la web de checkout; prueba combinaciones raras (cantidad 0, cupón caducado) y reporta lo que rompe. |
| **Self-healing** | Repara selectores/tests cuando la UI cambia. | El botón `#buy` pasa a `#purchase`; el agente lo reconoce por intención y actualiza el test en vez de fallar. |
| **Triaje de fallos** | Distingue un bug real del ruido del entorno (flaky). | Ante 20 fallos en CI, el agente agrupa, detecta cuáles son flaky y cuáles son una regresión real. |
| **Evaluación de salidas de IA** (LLM-as-a-judge) | Un agente juzga si la salida de *otro* sistema de IA es aceptable. | Un agente evaluador puntúa si la respuesta de un chatbot es correcta, sin alucinaciones y sin sesgo. |
| **Red teaming / testing adversario** | Ataca el sistema a propósito para encontrar vulnerabilidades. | Intenta *prompt injection* o *jailbreak* contra un agente para ver si se salta sus guardrails. |

Los dos últimos son los más nuevos y los mejor pagados, porque atacan el problema
más difícil de 2026: **hacer QA de sistemas que son no deterministas por diseño**
(el documento 1, sección 8, uso #2).

*(Fuentes: [1], [2], [5].)*

### Cómo se conecta esto con lo que ya construiste

No es teoría lejana; ya practicaste los cimientos:

- **LLM-as-a-judge** es un evaluador con un oráculo débil (comprueba propiedades,
  no igualdad) — lo mismo que discutimos para juzgar la narración del Game Master.
- **El triaje de flaky** necesita reproducibilidad — la inyección de dependencias
  (RNG con semilla, rutas) que usaste en `dice.py` y `state.py`.
- **El red teaming** ataca los **guardrails** — justo el Milestone 7 de tu
  roadmap.
- **Todo** necesita **observabilidad** — los hooks (`RunHooks`) que ya montaste en
  M5 para ver qué tools llama el agente.

Por eso el proyecto tiene sentido: cada milestone del juego es un ladrillo de un
sistema de QA con agentes.

---

## 4. Cuando una empresa busca un "QA con experiencia en agentes", ¿para qué lo quiere?

Esta es tu pregunta directa. Mirando ofertas reales de 2026, el puesto (aparece
como *AI QA Engineer*, *QA Engineer – GenAI & AI Agent Testing*, *AI Evaluation &
Test Engineer*) casi nunca es "que un agente haga tu trabajo de testing". Es lo
contrario más a menudo: **te quieren para hacer QA DE los agentes** que la empresa
está metiendo en su producto. Es el uso #2 del documento 1: probar software no
determinista.

En concreto, te contratan para cinco tipos de trabajo:

### 1. Evaluar salidas de LLM/agentes (el núcleo del puesto)
Validar que las respuestas de un sistema de IA no alucinan, no tienen sesgo y se
mantienen dentro de lo aceptable. Se hace construyendo **frameworks de evaluación
automatizada** y usando técnicas como *LLM-as-a-Judge*, *human-in-the-loop* y
benchmarks. Herramientas que piden por nombre: **LangSmith, DeepEval, TruLens,
Promptfoo**.

### 2. Testing adversario y seguridad de IA (red teaming)
Diseñar ataques deliberados para encontrar fallos antes de producción: *prompt
injection*, *jailbreaks*, fugas de datos, casos límite. Comprobar que los
**guardrails** aguantan. Este es de los skills mejor valorados.

### 3. Probar sistemas multi-agente y orquestaciones
Verificar que varios agentes colaborando (un "agent mesh") se comportan de forma
fiable, segura y sin **alucinar llamadas a tools** — es decir, que no inventan una
acción que no deben ejecutar. (Este es exactamente el terreno de tu Milestone 6.)

### 4. Automatización de tests "clásica" reforzada con IA
No desaparece: sigue habiendo que saber **Python, Pytest, Selenium/Playwright**,
planificación de pruebas, gestión de defectos y CI. La IA se añade encima, no
sustituye la base.

### 5. Gobernanza, trazabilidad y IA responsable
Entender *explainability*, *traceability*, guardrails y *model governance*: poder
demostrar **por qué** un agente hizo lo que hizo y que cumple las políticas. Aquí
es donde tu insistencia en observabilidad y fallo honesto (documento 1, sección
12) es oro puro.

**Perfil típico que piden** (de ofertas reales 2026): varios años de Python;
experiencia con frameworks de test (Pytest, Selenium, Playwright); experiencia
evaluando LLMs / agentes / RAG con herramientas como LangSmith/DeepEval/Promptfoo;
conocer *prompt engineering*, comportamiento no determinista, y modos de fallo
propios de IA (alucinación, sesgo, *model drift*); y capacidad de testing
adversario / red teaming. Es un rol nuevo (casi no existía hace dos años), en
rápido crecimiento y con primas salariales notables.

*(Fuentes: [5], [6].)*

> **Traducción para tu carrera:** el puesto no es "sé usar un agente que testea por
> mí". Es **"sé garantizar la calidad de un producto que ES no determinista"**. Y
> el corazón de eso —diseñar oráculos débiles pero robustos, exigir
> reproducibilidad, montar observabilidad, cazar el falso positivo silencioso— es
> exactamente lo que este proyecto te está entrenando a hacer.

---

## 5. El puente concreto a TestOps AI

Uniendo todo, así se mapea lo que construyes en el juego con lo que un producto de
QA con agentes (TestOps AI) necesitará:

| Del juego (ya hecho o en roadmap) | En un producto de QA con agentes |
|---|---|
| Reglas deterministas en `domain/` + tests | Oráculos fuertes: todo lo verificable con exactitud, verificado con exactitud. |
| Estado validado como fuente de verdad | Resultados de test auditables y reproducibles, no "recuerdos" del modelo. |
| Hooks / modo debug (M5) | Trazabilidad: registro de cada decisión del agente para poder auditarla. |
| Inyección de dependencias (RNG, rutas) | Reproducibilidad: fijar las fuentes de variación para reproducir un fallo. |
| "not set yet" en vez de valor falso | Fallo honesto: nunca un falso "PASÓ"; un hueco visible antes que un falso positivo. |
| Guardrails (M7, futuro) | Defensa ante prompt injection / jailbreak; superficie del red teaming. |
| Multi-agente (M6, futuro) | Testing de orquestaciones multi-agente y de llamadas-a-tool alucinadas. |
| Evaluación (M8, futuro) | Frameworks de evaluación tipo LLM-as-a-judge / benchmarks. |

Cada fila de la izquierda es un ejercicio deliberado para dominar la de la
derecha.

---

## Resumen

1. **Por qué agentes en QA:** para lo que el script fijo no puede — UI cambiante
   (self-healing), descubrir lo no anticipado (exploración) y probar salidas
   abiertas de IA. No sustituyen a los tests deterministas; los complementan.
2. **Aplicaciones generales de agentes:** soporte que actúa, coding agents,
   research agents, automatización de procesos, tareas de horizonte largo — todas
   el mismo bucle percibir→razonar→actuar→observar.
3. **Aplicaciones en QA:** generación de tests, exploración, self-healing, triaje
   de flaky, evaluación de IA (LLM-as-a-judge) y red teaming adversario.
4. **Para qué te quieren las empresas:** sobre todo para hacer **QA DE los
   agentes** de su producto — evaluar salidas, red teaming, probar multi-agente,
   automatización clásica reforzada, y gobernanza/trazabilidad. Base de Python +
   frameworks de test + herramientas de evaluación de LLMs. Rol nuevo, en auge y
   bien pagado.
5. **El puente:** cada patrón que practicas en Dungeon Agents (determinismo,
   estado validado, observabilidad, reproducibilidad, fallo honesto, guardrails)
   es un cimiento directo de ese trabajo y de TestOps AI.

---

## Fuentes

1. Anthropic — casos de uso de agentes (coding, soporte que actúa, búsqueda/
   research, tareas de horizonte largo) y *evals* para agentes. *Building
   Effective Agents* / *Demystifying evals for AI agents* / *Effective harnesses
   for long-running agents*.
   <https://www.anthropic.com/engineering/building-effective-agents> ·
   <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents> ·
   <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>
2. *AI Agents: Evolution, Architecture, and Real-World Applications*
   (arXiv:2503.12687) — panorama de arquitecturas y aplicaciones reales de
   agentes. <https://arxiv.org/pdf/2503.12687>
3. *Agentic Testing 2026 — Proven QA Guide for AI Agents* — agentes de testing que
   perciben, planifican, ejecutan y adaptan; generación de tests, exploración,
   self-healing. <https://aitestingguide.com/agentic-testing/>
4. *AI Agent Examples: Common Use Cases* (Latenode) y *22 AI Agent Examples & Use
   Cases* (Domo) — ejemplos de soporte, automatización de procesos y
   recomendación (cifras de Vodafone y logística citadas).
   <https://latenode.com/blog/ai-agents-examples> ·
   <https://www.domo.com/learn/article/ai-agent-examples>
5. *Testing AI Agents in 2026: How to QA LLM-Powered Apps* — QA de sistemas no
   deterministas; evaluación contra distribución de respuestas.
   <https://www.testbooster.ai/en/blog/testing-ai-agents-in-2026-how-to-qa-llm-powered-apps>
6. Ofertas de empleo reales 2026 (Dice.com: *QA Engineer – GenAI & AI Agent
   Testing*, *AI Evaluation & Test Engineer*) y guías de skills — requisitos
   concretos: Python, Pytest/Selenium/Playwright, LangSmith/DeepEval/TruLens/
   Promptfoo, LLM-as-a-Judge, red teaming, prompt injection, gobernanza; rol en
   auge con prima salarial.
   <https://www.dice.com/job-detail/7ecd1552-17ea-473f-8c54-1c5aa8cc6e31> ·
   <https://qaskills.sh/blog/ai-qa-skills-directory-2026>

> Nota sobre fiabilidad: [1] (Anthropic) y [2] (arXiv) son las fuentes de mayor
> autoridad — el equipo que construye Claude y literatura académica revisable. Las
> ofertas de empleo [6] son *primarias* para responder "qué piden las empresas"
> (son las empresas hablando), aunque una oferta concreta puede caducar. El resto
> ([3], [4], [5]) es material técnico actual útil para el estado del arte pero de
> menor autoridad; contrasta cualquier cifra antes de citarla como definitiva.
