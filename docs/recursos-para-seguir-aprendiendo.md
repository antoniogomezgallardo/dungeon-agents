# Recursos para seguir aprendiendo: agentes de IA y QA

> Tercer documento de aprendizaje del proyecto **Dungeon Agents**. Los dos
> anteriores explican la teoría ([teoria-de-agentes-y-qa.md](teoria-de-agentes-y-qa.md))
> y las aplicaciones ([aplicaciones-de-agentes-en-qa.md](aplicaciones-de-agentes-en-qa.md)).
> Este es una **lista curada de recursos** para seguir ganando conocimiento por
> tu cuenta: libros, cursos, artículos, canales de YouTube, herramientas y papers.
>
> No es una lista exhaustiva de todo lo que existe — es una **selección con
> criterio**, ordenada por prioridad, con una nota honesta de para quién y para
> qué sirve cada recurso, y avisando de lo que cuesta dinero. Tu perfil es
> QA-minded aprendiendo agentes en Python, así que la selección se inclina hacia
> lo práctico, lo testeable y el puente hacia QA.

---

## Cómo usar esta lista

Está ordenada por **tipo de recurso**, y dentro de cada tipo por **prioridad para
tu caso** (marcada con ⭐). No intentes con todo a la vez. Una ruta sensata:

1. **Cimientos mentales** (para *entender* qué pasa por dentro): el vídeo de
   Karpathy + la serie de 3Blue1Brown (sección 4).
2. **Práctica de agentes** (para *construir*): un curso corto de DeepLearning.AI +
   el post de Anthropic (secciones 2 y 3).
3. **Tu ángulo: QA de IA** (para *diferenciarte*): DeepEval + Promptfoo, que
   conectan directamente con tu pytest (secciones 5 y 6).

Marcas:
- ⭐ = empieza por aquí para tu perfil.
- 💶 = de pago (el resto es gratis o tiene una parte gratis relevante).

---

## 1. Libros

Los libros dan la visión estructurada que los tutoriales sueltos no dan. Para tu
perfil (Python, QA, agentes en producción), en orden de prioridad:

- ⭐ 💶 **_AI Engineering: Building Applications with Foundation Models_ — Chip
  Huyen (O'Reilly, 2025).** El más recomendado y el más alineado con tu proyecto.
  Cubre el stack completo de construir aplicaciones LLM en producción: evaluación,
  diseño de prompts, arquitecturas de agentes, **guardrails**, memoria, y
  **LLMOps/observabilidad** — justo los temas de tus próximos milestones (M7
  guardrails, M8 evaluación). Su autora escribe con mentalidad de ingeniería de
  sistemas, no de hype.
  - Ficha: <https://www.oreilly.com/library/view/ai-engineering/9781098166298/>
  - Repo de recursos abiertos que la acompaña (gratis):
    <https://github.com/chiphuyen/aie-book>

- 💶 **_Hands-On Large Language Models_ — Jay Alammar & Maarten Grootendorst
  (O'Reilly, 2024).** Alammar es famoso por explicar con diagramas
  (*The Illustrated Transformer*). Ayuda a construir un modelo mental sólido de
  *cómo se comportan* los LLMs — necesario para diseñar agentes que razonen y usen
  tools de forma consistente. Muy visual, ideal si prefieres intuición antes que
  matemáticas.

- 💶 **_Designing Machine Learning Systems_ — Chip Huyen (O'Reilly, 2022).** No es
  sobre agentes, pero es el mejor libro sobre *sistemas* de ML de extremo a
  extremo: pipelines de datos, versionado, despliegue, **monitorización**. Para un
  perfil de QA/TestOps es oro, porque testear un sistema de IA exige entender el
  sistema entero, no solo el modelo.

- 💶 **_Build a Large Language Model (from Scratch)_ — Sebastian Raschka (Manning,
  2024).** Opcional y más profundo: construyes un LLM tipo transformer desde cero
  en PyTorch. Solo si quieres entender los LLMs *a nivel de código*, no solo
  usarlos vía API. Para tu objetivo (agentes + QA) no es imprescindible, pero
  desmitifica la caja negra.

> **Fuentes primarias gratis que valen como "libro":**
> - Anthropic, *Building Effective Agents* — lectura corta y de altísima calidad
>   sobre agente vs. workflow y patrones. Léela ya.
>   <https://www.anthropic.com/engineering/building-effective-agents>

*(Fuentes de esta sección: [1], [2].)*

---

## 2. Fuentes primarias online (gratis, alta fiabilidad)

Antes de pagar cursos, exprime lo que publican gratis quienes construyen esta
tecnología. Es lo más fiable que hay.

- ⭐ **Anthropic — Engineering blog.** La casa que hace Claude. Artículos
  concretos y sin humo:
  - *Building Effective Agents* (agente vs. workflow, patrones):
    <https://www.anthropic.com/engineering/building-effective-agents>
  - *Demystifying evals for AI agents* (cómo evaluar agentes — puro QA de IA):
    <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>
  - *Effective harnesses for long-running agents* (tareas de horizonte largo):
    <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>
  - *Effective context engineering for AI agents* (relevante tras vivir la
    compactación de contexto que te pasó):
    <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>

- **OpenAI — guías de agentes y function calling.** El otro gran proveedor; útil
  aunque tu proyecto use Anthropic por defecto, porque el SDK que usas es el de
  OpenAI. Busca "OpenAI Agents SDK" y "function calling guide" en
  <https://platform.openai.com/docs>.

- **Documentación del OpenAI Agents SDK** (el que usa Dungeon Agents). Léela para
  entender de verdad `Agent`, `Runner`, `@function_tool` y `RunHooks` que ya
  tocas: <https://openai.github.io/openai-agents-python/>

*(Fuentes: [1].)*

---

## 3. Cursos online (prácticos, mayormente gratis)

- ⭐ **DeepLearning.AI — cursos cortos de agentes.** Gratis (con cuenta),
  1-2 horas cada uno, muy prácticos. Los relevantes:
  - *AI Agents in LangGraph* — **empieza construyendo un agente desde cero con
    solo un LLM y Python**, y luego lo reconstruye con un framework. Es
    exactamente tu curva de aprendizaje (entender el bucle antes que el framework).
    Impartido por el CEO de LangChain.
    <https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/>
  - *Multi AI Agent Systems with crewAI* — preparación directa para tu **M6
    (multi-agente)**: roles, objetivos y colaboración entre agentes.
    <https://www.deeplearning.ai/courses/multi-ai-agent-systems-with-crewai>
  - Catálogo completo de agentes:
    <https://www.deeplearning.ai/courses?topics=Agents>

- 💶 **Cursos de pago (Udemy/Coursera/Udacity)** sobre "Agentic AI con LangGraph /
  CrewAI / AutoGen". Útiles si prefieres un temario largo y guiado, pero la
  mayoría de su valor está cubierto gratis por DeepLearning.AI + docs de Anthropic.
  No los priorizaría al principio.

*(Fuentes: [3].)*

---

## 4. Canales de YouTube (para los cimientos y el día a día)

Divididos en "entender los cimientos" (míralos una vez, bien) y "seguir al día"
(suscríbete).

**Cimientos — para entender qué hay dentro de un LLM:**

- ⭐ **Andrej Karpathy** — *Neural Networks: Zero to Hero*. Cofundador de OpenAI,
  explica los LLMs a una profundidad que nadie iguala. El vídeo *"Let's build GPT:
  from scratch, in code, spelled out"* (~2h) es el punto de partida que casi todo
  ingeniero de IA debería ver antes de tocar un framework.
  - Playlist: <https://karpathy.ai/zero-to-hero.html>

- ⭐ **3Blue1Brown** — series *Essence of Linear Algebra* y *Neural Networks*
  (incluye una explicación visual buenísima de los transformers y la atención).
  Si el álgebra o "qué es la atención" te resultan borrosos, esto lo arregla con
  claridad visual. <https://www.youtube.com/c/3blue1brown>

**Al día — frameworks, agentes en producción, herramientas:**

- **LangChain** (canal oficial del framework), **IBM Technology** (explicadores
  conceptuales cortos y muy claros), **Cole Medin** (agentes en producción),
  **AssemblyAI** (tutoriales prácticos de apps LLM), **Yannic Kilcher** (desglosa
  papers de investigación, para cuando quieras profundizar).

> Consejo de ruta (de las propias fuentes): semanas 1-2, mira Karpathy
> *"Let's build GPT"* + la serie de transformers de 3Blue1Brown. Eso te da el
> modelo mental. Luego pasa a lo práctico.

*(Fuentes: [4].)*

---

## 5. Herramientas de evaluación de LLMs/agentes (tu ángulo de QA) ⭐

Esta sección es la más importante **para ti en concreto**, porque es donde tu
experiencia de QA + agentes se vuelve empleable (recuerda el doc 2: las empresas
piden LangSmith/DeepEval/Promptfoo por nombre). Además conectan con tu pytest.

- ⭐ **DeepEval** — *"el pytest de la evaluación de LLMs"*. Framework open-source
  en Python para evaluar LLMs, agentes y RAG. Su feature estrella: **se integra
  con pytest**, así que las evals viven junto a tus tests unitarios, corren en el
  mismo CI y **rompen el build cuando un cambio de prompt empeora una métrica.**
  Para un proyecto que ya usa pytest (como Dungeon Agents), es el punto de entrada
  natural a la evaluación de IA. Empieza aquí.
  - <https://deepeval.com/>

- ⭐ **Promptfoo** — evaluación *YAML-first*, por línea de comandos, agnóstica al
  lenguaje. Fuerte en **red-teaming** y *matrix testing* (comparar prompts/modelos
  en una matriz de casos). Ideal cuando quien escribe las evals no es quien escribe
  la app — muy "modo QA". Open-source (MIT).
  - <https://www.promptfoo.dev/docs/intro/>

- **LangSmith** — plataforma *observability-first* (de pago/hosted): junta trazas
  de producción y suites de evaluación en un solo sistema. Útil cuando quieras
  trazabilidad + evaluación integradas; conecta con lo que aprendiste de hooks/
  observabilidad en M5. Empresa: LangChain.
  - <https://www.langchain.com/langsmith>

- **Giskard** — otro framework open-source de evaluación, con foco en detección de
  vulnerabilidades y sesgo. Complementa a los anteriores.

> **Qué elegir, según las fuentes:** si tu equipo es Python-first y ya usa pytest,
> **empieza por DeepEval** (curva casi cero). Añade **Promptfoo** cuando quieras
> comparar prompts/modelos o hacer red-teaming. Usa **LangSmith** si quieres
> trazas de producción + evals en un solo sitio (y aceptas un servicio de pago).

*(Fuentes: [5], [6].)*

---

## 6. Papers fundacionales (para cuando quieras profundidad)

No hace falta leerlos para construir agentes, pero entender estos te da los
cimientos de por qué las cosas funcionan como funcionan. En orden de relevancia
para agentes:

- ⭐ **ReAct: Synergizing Reasoning and Acting in Language Models** (Yao et al.,
  2022). El paper del patrón razonar+actuar en bucle — literalmente lo que hace tu
  Game Master al intercalar narración y llamadas a `roll_dice`. Legible.
  <https://arxiv.org/abs/2210.03629>

- **Attention Is All You Need** (Vaswani et al., 2017). El paper que introdujo el
  transformer, la arquitectura detrás de todos los LLMs actuales. Denso, pero es
  *el* origen. <https://arxiv.org/abs/1706.03762>

- **Toolformer: Language Models Can Teach Themselves to Use Tools** (Schick et al.,
  2023). Sobre cómo los modelos aprenden a usar herramientas — el concepto que hay
  detrás de las tools que ya construiste. <https://arxiv.org/abs/2302.04761>

- **Chain-of-Thought Prompting** (Wei et al., 2022). Por qué "pensar paso a paso"
  mejora el razonamiento — base conceptual de ReAct.
  <https://arxiv.org/abs/2201.11903>

- **Surveys de agentes** (para panorámica): *AI Agents: Evolution, Architecture,
  and Real-World Applications* (arXiv:2503.12687) y *LLM-based Agentic Reasoning
  Frameworks: A Survey* (arXiv:2508.17692).

---

## 7. Un plan de estudio sugerido (si quieres una ruta)

No es obligatorio, pero si te sirve tener un orden concreto para tu perfil:

1. **Semana 1-2 — cimientos.** Karpathy *"Let's build GPT"* + serie de
   transformers de 3Blue1Brown. Lee Anthropic *Building Effective Agents*.
2. **Semana 3-4 — construir.** Curso *AI Agents in LangGraph* de DeepLearning.AI.
   En paralelo, sigue avanzando tus milestones (la mejor práctica es tu propio
   proyecto).
3. **Semana 5-6 — tu diferenciador (QA de IA).** Instala **DeepEval**, escribe tus
   primeras evals sobre el Game Master (¿ofrece 2-3 opciones? ¿llama a `roll_dice`
   cuando toca?). Lee Anthropic *Demystifying evals for AI agents*. Esto es
   directamente tu **M8**.
4. **Continuo.** Libro de Chip Huyen *AI Engineering* como referencia de fondo;
   suscríbete a 2-3 canales de la sección 4; lee ReAct cuando quieras el "por qué".

> Regla de oro: **el mejor recurso es tu propio proyecto.** Cada recurso de esta
> lista rinde el doble si lo aplicas inmediatamente a un milestone de Dungeon
> Agents. Aprendes el patrón leyendo; lo *dominas* implementándolo.

---

## Fuentes

Los enlaces a cada recurso concreto están en línea, arriba. Estas son las fuentes
que usé para *seleccionar y verificar* las recomendaciones:

1. Reseñas y comparativas de libros de IA/LLM 2025-2026 (KDnuggets, DEV Community,
   O'Reilly) — para identificar los libros más recomendados y vigentes.
   <https://www.kdnuggets.com/5-best-books-for-building-agentic-ai-systems-in-2026> ·
   <https://www.oreilly.com/library/view/ai-engineering/9781098166298/>
2. Repositorio oficial de recursos de Chip Huyen (acompaña a *AI Engineering*).
   <https://github.com/chiphuyen/aie-book>
3. Catálogo de cursos de DeepLearning.AI (agentes).
   <https://www.deeplearning.ai/courses?topics=Agents>
4. Rankings de canales de YouTube para IA/LLM 2026 y la serie de Karpathy.
   <https://learnwithpath.com/blog/best-youtube-channels-for-ai-engineering-2026> ·
   <https://karpathy.ai/zero-to-hero.html>
5. Documentación oficial de los frameworks de evaluación.
   <https://deepeval.com/> · <https://www.promptfoo.dev/docs/intro/>
6. Comparativas de frameworks de evaluación de LLMs 2026 (para el "cuándo usar
   cada uno"). <https://inference.net/content/llm-evaluation-tools-comparison/>

> Nota sobre fiabilidad: las fuentes primarias (Anthropic, la documentación
> oficial de cada herramienta/SDK, los papers de arXiv, los canales de sus propios
> autores como Karpathy) son de máxima confianza. Las reseñas y rankings de blogs
> los usé solo para *descubrir y priorizar* recursos, no como autoridad sobre su
> contenido — verifica cada libro/curso en su fuente oficial (enlazada) antes de
> comprarlo, y ten en cuenta que precios y disponibilidad de cursos cambian.
