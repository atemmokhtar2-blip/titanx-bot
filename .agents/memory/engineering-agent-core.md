---
name: Engineering Agent Core
description: call_graph.py + knowledge_graph.py built and wired into ai_engine.py; PROJECT_FIRST enforcement; verified 13/13 routing tests + live pipeline
---

## What was built

Two new modules in `extracted_project/control_panel/`:

### call_graph.py — Function-level call graph
- AST-walks all 121 Python files, extracts 905 function nodes, 2376 call edges
- Two-pass build: Pass 1 builds function registry + import aliases per file; Pass 2 resolves ast.Call nodes to (file, func) pairs
- 5-min TTL in-process cache; no new dependencies (stdlib only)
- `CallGraph.who_calls(file, func)` → callers; `CallGraph.what_calls(file, func)` → callees
- `CallGraph.who_calls_file(file)` → cross-file callers with function-level detail
- `CallGraph.circular_imports()` → DFS cycle detection on import graph
- `CallGraph.chain(file, func, depth)` → BFS execution chain from entry point

### knowledge_graph.py — Unified multi-type knowledge graph
- Edge types: IMPORTS, RENDERS, SERVES, USES_DB, CONFIGURES, USES_JS, USES_CSS, EXTENDS, CALLS_API, HANDLES
- 260 nodes, 704 edges, 9 edge types across the live project
- File ownership per-file: purpose, risk_level, dependent_count, dependents, spof, responsibilities
- Disk persistence: `.knowledge_graph.json` in control_panel/ — survives restarts (5-min TTL)
- `KnowledgeGraph.full_trace(node)` → all cross-type relationships for a node
- `KnowledgeGraph.data_flow(entry_file)` → BFS from entry point following IMPORTS+USES_DB+RENDERS
- `KnowledgeGraph.single_points_of_failure()` → files with dep_count ≥ 5 or CRITICAL risk
- `FileOwnership.get(file)` → per-file metadata; `FileOwnership.risk_report()` → by risk level

## ai_engine.py surgical edits (4 targeted changes)

1. **Import block** (after line 15): fail-safe try/except for `_CallGraph` and `_KG/_FO`; sets `_CALL_GRAPH_OK` and `_KG_OK` flags used throughout
2. **PROJECT_FIRST gate** in `detect_intent()`: two-tier keyword check — short English tokens use `\b` word-boundary regex (prevents "fastapi" matching "api"), Arabic terms use substring; only returns "conversation" if NO project entity found
3. **`_step4_deps()` enrichment** in `AgentReasoningChain`: now also calls `CallGraph.who_calls_file()` and `KG.full_trace()` and returns `func_calls`, `circular`, `kg_trace` in addition to file-level callers/callees
4. **`_r_dependency()` enrichment**: appends Call Graph, File Ownership, and KG Trace sections to every dependency response

## Intent routing fixes
- Added `تبعيات`, `تبعية`, `يعتمد` to INTENTS `dependency` list
- Added explicit `_DEP_P` early-exit block in `detect_intent()` for Arabic dependency queries
- Added `ما الروتر المسؤول` and `أي روتر` to `_FILE_Q` patterns

## Verification results
- **13/13 routing tests passed**
- `CALL_GRAPH_OK=True`, `KG_OK=True` at runtime
- `process_chat('ما تبعيات config.py؟')` → intent=dependency, has_call_graph=True, has_ownership=True, has_kg_trace=True, risk=CRITICAL
- `FileOwnership.all_spof()` top 5: database/db.py (dep=43), utils/logger.py (dep=37), config/settings.py (dep=33), database/users.py (dep=19), control_panel/config.py (dep=17)

## Key architectural notes
- `FutureExecutionArchitecture` stays disabled (`can_execute()` returns False) — the engine is advisory only, no file writes
- Both new modules use same TTL pattern as existing `ProjectDependencyGraph` (5-min)
- Call graph is a static AST approximation: ~70% coverage (dynamic dispatch, decorators, callbacks not fully resolved)
- The `\b` word-boundary fix for PROJECT_FIRST is critical: "fastapi" must NOT trigger "api" keyword, "classic" must NOT trigger "class"

## Why
The engineering agent was previously advisory-only with file-level dep graph only. This adds:
- Function-level precision for impact analysis (Phase 4)
- Cross-type relationship tracing (Phase 1 Knowledge Graph)
- File ownership registry with SPOF detection (Phase 2)
- PROJECT_FIRST suppression of generic chat when project entities present (Phase 13/14)
