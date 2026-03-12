---
status: "accepted"
date: 2026-03-12
decision-makers: ["Engineering Team"]
---

# ADR-001: LangGraph for Agent Orchestration

## Context and Problem Statement
Cognify requires a multi-agent orchestration framework to coordinate trend detection, parallel research, content synthesis, and article generation. The system needs stateful workflows where an orchestrator agent plans research, spawns parallel sub-agents, collects results, and triggers sequential content generation steps. The framework must support:
- Conditional branching (skip image gen if no data-driven content)
- Parallel execution (multiple research agents simultaneously)
- State persistence (resume interrupted workflows)
- Human-in-the-loop review gates
- Tool integration (web search, vector DB, LLM APIs)

## Decision Drivers
* PRD requires multi-agent orchestration with parallel research agents
* Must support stateful, long-running workflows (research sessions can take 5+ minutes)
* Need checkpointing to resume interrupted workflows without re-running completed steps
* Agent workflows must be observable (step-by-step status for dashboard)
* Python ecosystem requirement (PRD specifies Python for agents and pipelines)
* Production readiness — must handle failures gracefully with retry/fallback

## Considered Options
* **LangGraph (LangChain ecosystem)** — Graph-based multi-agent orchestration with StateGraph
* **CrewAI** — Role-based multi-agent framework with YAML configuration
* **AutoGen (Microsoft)** — Conversational multi-agent framework

## Decision Outcome
Chosen option: **LangGraph**, because it provides the most granular control over agent workflow execution with explicit state management, conditional routing, and built-in checkpointing — all critical for Cognify's complex, long-running content generation pipeline.

### Consequences
* Good, because LangGraph's StateGraph model maps directly to Cognify's pipeline stages (detect → research → synthesize → write → visualize → publish)
* Good, because built-in checkpointing enables resuming failed workflows without re-running expensive LLM calls
* Good, because LangChain ecosystem provides mature tool integrations (web search, vector stores, LLM providers)
* Good, because conditional edges allow dynamic workflow branching (e.g., skip illustration when no visual data)
* Bad, because LangGraph has a steeper learning curve than CrewAI's declarative YAML approach
* Bad, because tight coupling to the LangChain ecosystem may limit future framework migration

### Confirmation
Validated through: prototype implementation of a trend-to-article pipeline in Sprint 1, demonstrating parallel research agent execution, state checkpointing, and human-in-the-loop review gate.

## Pros and Cons of the Options

### LangGraph (LangChain ecosystem)
* Good, because explicit graph-based workflow definition with conditional edges
* Good, because built-in state persistence and checkpointing (PostgreSQL-backed)
* Good, because mature LangChain tool ecosystem (search, vector stores, LLM providers)
* Good, because supports parallel node execution for concurrent research agents
* Good, because active development and large community (129k+ stars for LangChain)
* Bad, because requires understanding of graph-based programming paradigm
* Bad, because debugging complex graphs can be challenging

### CrewAI
* Good, because simple YAML-based agent configuration with role/task definitions
* Good, because intuitive "crew" mental model (researcher, writer, editor roles)
* Good, because growing community (45k+ stars) and production-focused
* Bad, because less granular control over execution flow than graph-based approaches
* Bad, because limited checkpointing and state persistence for long-running workflows
* Bad, because parallel execution support is less mature

### AutoGen (Microsoft)
* Good, because conversational agent pattern is flexible and natural
* Good, because supports Python and .NET, with strong Microsoft ecosystem integration
* Good, because 55k+ stars and active development
* Bad, because conversational pattern adds overhead for structured pipelines
* Bad, because less suited for deterministic, staged workflows (research → write → publish)
* Bad, because state management requires more custom implementation
