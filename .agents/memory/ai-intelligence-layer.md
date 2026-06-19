---
name: AI Intelligence Layer
description: Foundation upgrade — complete Project Knowledge System in ai_engine.py v3.0. Full knowledge graph, dependency analyzer, root cause analysis, architecture intelligence, 16-test suite.
---

# AI Intelligence Layer — v3.0 Complete Foundation

## What was built
`extracted_project/control_panel/ai_engine.py` upgraded to v3.0 — complete rewrite.

## Core data structures

### `_ROUTE_GRAPH` (20 routes)
Every control panel route → {router, template, base, css, js, apis, description, aliases}.
Used by `_route_for_concept()` and `answer_file_question()`.

### `_SEMANTIC_MAP` (56 concepts)
All project concepts → [(file, role, description)]. Covers every page, CSS section, JS section, DB model, bot, service, config.

### `_CSS_MAP` / `_JS_MAP`
Detailed section maps for the single CSS file (15 sections) and single JS file (13 sections).

### `_DB_MAP` (11 models)
All database models with functions + used_by relationships.

### `_BOT_MAP` (2 bots)
Main bot + support bot with all handlers, services, middlewares, databases.

### `_CONFIG_MAP` / `_ARCH_MAP`
Config files + architecture descriptions for frontend, bots, database, panel subsystems.

### `_PLAN_TEMPLATES`
Pre-built accurate modification plans for: homepage, dashboard, sidebar, colors, css, login, auth, users, ai_engineer, navigation, bots, backup.

## Engines

### `_find_concept(q)` — 4-pass matching
1. Exact substring (longest concept wins — "ai_engineer" beats "ai")
2. All keywords in concept present (AND logic)
3. Any meaningful keyword (len > 2)
4. Route alias search fallback

### `answer_file_question(msg)`
Returns router + template + base + css + js + apis + semantic entries for any concept.

### `create_modification_plan(description)`
Uses `_PLAN_TEMPLATES` for known pages, falls back to `_route_for_concept()` + `_find_concept()`. Returns real files, why, risk, rollback, numbered steps.

### `analyze_file_impact(file)`
Static impact map for all critical files (style.css → critical, base.html → critical, db.py → critical, etc.).

### `analyze_root_cause(question)`
Identifies failure layers: router, template, CSS, JS, API. Returns diagnostic steps.

### `explain_architecture(query)`
Returns architecture doc for: project, control_panel, bots, database, frontend.

## Self-test suite
- 8 canonical (required): 8/8 ✅ 100%
- 16 extended: 16/16 ✅ 100%

## Critical rule: longest-match-first
Sort `_SEMANTIC_MAP` items by `len(concept)` descending before any match pass.
Short keys like "ai", "db", "css" would otherwise swallow longer keys.

## Self-test pass list (canonical 8)
1. What file controls the homepage? → dashboard.html ✅
2. What file controls the dashboard? → dashboard.html ✅
3. What file controls the colors? → style.css ✅
4. What file controls the sidebar? → base.html ✅
5. What file loads the AI Engineer page? → ai_engineer ✅
6. What route serves the users page? → users ✅
7. What files must change to redesign the homepage? → dashboard.html ✅
8. What files must change to redesign the sidebar? → base.html ✅
