# Documentación de Dungeon Agents

Índice de toda la documentación del proyecto. **Dungeon Agents** es un proyecto de
aprendizaje: una consola RPG en Python que sirve de pretexto para dominar patrones
de agentes de IA, con el objetivo de migrarlos a un futuro producto de QA/testing,
**TestOps AI**. Por eso la documentación explica el *porqué* de cada decisión, no
solo el *qué*.

La documentación tiene tres familias: **guías conceptuales** (aprender la teoría y
la práctica de los agentes), un **plan de pruebas** (validar la aplicación), y los
**deep-dives de milestone** (la historia detallada de cómo se construyó, paso a
paso).

---

## Guías conceptuales (en español)

Documentos transversales, pensados para leerse fuera del código. Si empiezas de
cero, léelos en este orden:

0. **[Guía completa M1 a M7 — onboarding y consolidación](guia-completa-m1-a-m7.md)**
   El documento maestro del proyecto. Lee esto si quieres entender todo lo
   construido de M1 a M7 en una sola lectura: teoría de agentes desde cero,
   arquitectura, recorrido milestone a milestone con código real comentado, y el
   puente a TestOps AI. Pensado para alguien que llega sin conocer el proyecto ni
   el mundo de los agentes.

1. **[Teoría de agentes y su aplicación a QA](teoria-de-agentes-y-qa.md)**
   Empieza desde cero: qué es un agente, el bucle agéntico, qué son las tools, y
   cómo toda esa teoría se aplica al testing/QA. El punto de partida. Con fuentes
   citadas.

2. **[Agentes en QA: por qué, para qué, y qué buscan las empresas](aplicaciones-de-agentes-en-qa.md)**
   Más práctico: por qué QA necesita agentes, las principales aplicaciones (con
   ejemplos sencillos), y para qué trabajo te quieren las empresas cuando piden
   experiencia en agentes.

3. **[Principios y patrones de agentes](principios-y-patrones-de-agentes.md)**
   Guía de referencia consultable: cuándo usar un agente y cuándo NO (y qué usar
   en su lugar), los principios innegociables, los tres patrones de coordinación
   (agent-as-tool, handoff, pipeline), y un checklist práctico. El destilado de
   todo lo aprendido.

4. **[Recursos para seguir aprendiendo](recursos-para-seguir-aprendiendo.md)**
   Lista curada para estudiar por tu cuenta: libros, cursos, artículos, canales de
   YouTube, herramientas de evaluación y papers fundacionales, con un plan de
   estudio sugerido.

---

## 🧪 Plan de pruebas

- **[Plan de pruebas (M1–M6)](plan-de-pruebas.md)**
  Plan de pruebas funcional y exploratorio en toda regla: 68 casos organizados por
  área, distinguiendo pruebas automáticas (deterministas, sin API key) de manuales
  (comportamiento de agentes, con API key), más una matriz de trazabilidad y una
  plantilla de registro de resultados. Úsalo para validar la aplicación de
  principio a fin.

---

## 🏗️ Deep-dives de milestone (en inglés)

La historia detallada de cómo se construyó el proyecto, un documento por
milestone, siguiendo una estructura fija de 8 secciones (objetivo, qué se
construyó, conceptos, mentalidad QA, cómo probarlo, riesgos, puente a TestOps AI,
qué sigue). Léelos en orden; cada uno asume el anterior.

Índice y estado en **[milestones/README.md](milestones/README.md)**. Resumen:

| Milestone | Tema | Documento |
|-----------|------|-----------|
| M1 | Game Master en consola | [milestone-01-game-master.md](milestones/milestone-01-game-master.md) |
| M2 | Tools deterministas | [milestone-02-tools.md](milestones/milestone-02-tools.md) |
| M3 | Modelos de dominio (Pydantic) | [milestone-03-domain-models.md](milestones/milestone-03-domain-models.md) |
| M4 | Inventario y reglas | [milestone-04-inventory-rules.md](milestones/milestone-04-inventory-rules.md) |
| M5 | Estado de sesión y UX | [milestone-05-session-ux.md](milestones/milestone-05-session-ux.md) |
| M6 | Multi-agente | [milestone-06-multi-agent.md](milestones/milestone-06-multi-agent.md) |
| M7 | Guardrails y seguridad | [milestone-07-guardrails.md](milestones/milestone-07-guardrails.md) |

---

## Por dónde empezar

- **¿Llegas de cero y quieres entender todo el proyecto de una vez?** →
  [Guía completa M1 a M7](guia-completa-m1-a-m7.md) (onboarding exhaustivo).
- **¿Quieres entender los agentes desde cero?** → Guías conceptuales 1 → 2 → 3.
- **¿Quieres validar la aplicación?** → El [plan de pruebas](plan-de-pruebas.md).
- **¿Quieres ver cómo se construyó, paso a paso?** → Los deep-dives de milestone,
  empezando por [M1](milestones/milestone-01-game-master.md).
- **¿Buscas una regla o patrón concreto para aplicar?** →
  [Principios y patrones de agentes](principios-y-patrones-de-agentes.md).

Para instalar y ejecutar el juego, consulta el
[README principal del proyecto](../README.md).
