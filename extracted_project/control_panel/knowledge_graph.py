"""
knowledge_graph.py — Unified multi-type knowledge graph for TitanX Engineering Agent.

Typed edges model the FULL relationship surface of the project:
  IMPORTS    file     → file          (Python import statement)
  RENDERS    router   → template      (TemplateResponse call)
  SERVES     router   → route_path    (@router.get/@router.post)
  USES_DB    file     → database_file (aiosqlite.connect / DB import)
  CONFIGURES config   → consumer      (config/settings imported by)
  USES_JS    template → js_file       (<script src=...>)
  USES_CSS   template → css_file      (<link href=...>)
  EXTENDS    template → base_template ({%extends%})
  CALLS_API  template → api_route     (fetch('/api/...'))
  HANDLES    handler  → bot_command   (@app.add_handler)

File ownership:
  Per-file metadata: purpose, risk_level, responsibilities, dependents, spof

Persistence:
  Disk cache: control_panel/.knowledge_graph.json (survives restarts)
  Memory TTL: 5 minutes

Public API:
  KnowledgeGraph.get()
  KnowledgeGraph.edges_from(node, type?)
  KnowledgeGraph.edges_to(node, type?)
  KnowledgeGraph.full_trace(node)
  KnowledgeGraph.data_flow(entry_file)
  KnowledgeGraph.single_points_of_failure()
  KnowledgeGraph.status()
  FileOwnership.get(rel_file)
  FileOwnership.all_spof()
  FileOwnership.risk_report()
"""
import ast
import os
import re
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

_log = logging.getLogger("titanx.knowledge_graph")

_HERE         = Path(__file__).parent
EXTRACTED_DIR = _HERE.parent
_KG_FILE      = _HERE / ".knowledge_graph.json"

SKIP_DIRS = {"__pycache__", ".git", ".pythonlibs", "node_modules",
             ".venv", "venv", "temp", "backups", "logs", "hf_space"}

_CACHE_TTL    = 300.0
_GRAPH_CACHE: dict  = {}
_GRAPH_TS:    float = 0.0


class E:
    """Edge type constants."""
    IMPORTS    = "IMPORTS"
    RENDERS    = "RENDERS"
    SERVES     = "SERVES"
    USES_DB    = "USES_DB"
    CONFIGURES = "CONFIGURES"
    USES_JS    = "USES_JS"
    USES_CSS   = "USES_CSS"
    EXTENDS    = "EXTENDS"
    CALLS_API  = "CALLS_API"
    HANDLES    = "HANDLES"


def _walk(exts: set = None) -> list:
    exts = exts or {".py", ".html", ".js", ".css"}
    out  = []
    for root, dirs, fnames in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            if any(fn.endswith(e) for e in exts):
                fp = Path(root) / fn
                try:
                    out.append(str(fp.relative_to(EXTRACTED_DIR)))
                except ValueError:
                    pass
    return sorted(out)


def _read(rel: str, cap: int = 80_000) -> str:
    try:
        return (EXTRACTED_DIR / rel).read_text(encoding="utf-8", errors="ignore")[:cap]
    except Exception:
        return ""


def _edge(from_: str, to: str, typ: str, label: str = "") -> dict:
    e = {"from": from_, "to": to, "type": typ}
    if label:
        e["label"] = label
    return e


def _build_import_edges(py_files: list) -> list:
    edges = []
    for rel in py_files:
        try:
            tree = ast.parse(_read(rel), filename=rel)
        except Exception:
            continue
        parts = rel.replace("\\", "/").split("/")
        pkg   = parts[:-1]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    cand = alias.name.replace(".", "/") + ".py"
                    if (EXTRACTED_DIR / cand).exists():
                        edges.append(_edge(rel, cand, E.IMPORTS))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level  = node.level or 0
                if level > 0:
                    base = pkg[:max(0, len(pkg) - (level - 1))]
                    cand = ("/".join(base + module.split(".")) + ".py"
                            if module else "/".join(base) + ".py")
                else:
                    cand = module.replace(".", "/") + ".py"
                if cand and (EXTRACTED_DIR / cand).exists():
                    edges.append(_edge(rel, cand, E.IMPORTS))
    return edges


def _build_render_edges(py_files: list) -> list:
    edges = []
    route_re  = re.compile(r'@(?:router|app)\.(get|post|put|delete|patch)\(["\']([^"\']+)')
    render_re = re.compile(r'TemplateResponse\([^,]+,\s*["\']([^"\']+\.html)["\']')
    for rel in py_files:
        if "router" not in rel and "app.py" not in rel and "server.py" not in rel:
            continue
        src = _read(rel, 40_000)
        for m in route_re.finditer(src):
            edges.append(_edge(rel, m.group(2), E.SERVES, m.group(2)))
        for m in render_re.finditer(src):
            tpl = m.group(1)
            tpl_path = (f"control_panel/templates/{tpl}"
                        if not tpl.startswith("control_panel") else tpl)
            edges.append(_edge(rel, tpl_path, E.RENDERS, tpl))
    return edges


def _build_template_edges(html_files: list) -> list:
    edges   = []
    js_re   = re.compile(r'src=["\'](?:[^"\']*/)([^"\']+\.js)["\']')
    css_re  = re.compile(r'href=["\'](?:[^"\']*/)([^"\']+\.css)["\']')
    ext_re  = re.compile(r'\{%[-\s]*extends\s*["\']([^"\']+)["\']')
    api_re  = re.compile(r'''fetch\s*\(\s*['"]([^'"?]+)['"]''')
    for rel in html_files:
        src = _read(rel, 30_000)
        for m in ext_re.finditer(src):
            base = m.group(1)
            base_path = (f"control_panel/templates/{base}"
                         if not base.startswith("control_panel") else base)
            edges.append(_edge(rel, base_path, E.EXTENDS))
        for m in js_re.finditer(src):
            edges.append(_edge(rel, f"control_panel/static/js/{m.group(1)}", E.USES_JS))
        for m in css_re.finditer(src):
            edges.append(_edge(rel, f"control_panel/static/css/{m.group(1)}", E.USES_CSS))
        for m in api_re.finditer(src):
            path = m.group(1)
            if path.startswith("/"):
                edges.append(_edge(rel, path, E.CALLS_API, path))
    return edges


def _build_db_edges(py_files: list) -> list:
    edges   = []
    db_pats = [
        r"aiosqlite\.connect", r"sqlite3\.connect",
        r"from\s+database\b", r"import\s+database\b",
        r"from\s+\.database\b", r"database\.db",
        r"bot\.db", r"support\.db",
    ]
    for rel in py_files:
        src = _read(rel, 20_000)
        for pat in db_pats:
            if re.search(pat, src):
                db = ("support_bot/database/support.db"
                      if "support" in rel else "database/bot.db")
                edges.append(_edge(rel, db, E.USES_DB))
                break
    return edges


def _build_config_edges(py_files: list) -> list:
    edges   = []
    cfg_files = [
        f for f in py_files
        if Path(f).name in ("config.py", "settings.py")
    ]
    for cfg in cfg_files:
        stem = Path(cfg).stem
        name = Path(cfg).name
        for rel in py_files:
            if rel == cfg:
                continue
            src = _read(rel, 15_000)
            if stem in src or name in src:
                edges.append(_edge(cfg, rel, E.CONFIGURES))
    return edges


def _build_handler_edges(py_files: list) -> list:
    """HANDLES edges: handler file → Telegram command string."""
    edges   = []
    cmd_re  = re.compile(r'CommandHandler\s*\(\s*["\'](\w+)["\']')
    for rel in py_files:
        if "handler" not in rel and "bot.py" not in rel:
            continue
        src = _read(rel, 20_000)
        for m in cmd_re.finditer(src):
            edges.append(_edge(rel, f"/{m.group(1)}", E.HANDLES, m.group(1)))
    return edges


_STATIC_OWNERSHIP: dict = {
    "control_panel/app.py": (
        "FastAPI app factory — mounts all 12 routers, session middleware, auth gates, startup hooks",
        "CRITICAL",
    ),
    "control_panel/auth.py": (
        "Session authentication — ACCESS_TOKEN generation, session cookie, require_owner dependency",
        "CRITICAL",
    ),
    "control_panel/config.py": (
        "Central config — PROJECT_ROOT, OWNER_ID, BOT_TOKEN, all path constants; 12+ routers import this",
        "CRITICAL",
    ),
    "control_panel/ai_engine.py": (
        "AI Operator core — 6700+ line reasoning engine, intent routing, memory, planning, self-test",
        "HIGH",
    ),
    "config/settings.py": (
        "Bot configuration — BOT_TOKEN, points system, SUPPORTED_DOMAINS, achievement definitions",
        "CRITICAL",
    ),
    "database/db.py": (
        "SQLite abstraction — init_db(), get_user(), create_user(), download tracking, points ledger",
        "CRITICAL",
    ),
    "bot.py": (
        "Main bot entry point — Application builder, handler registration, background workers, polling loop",
        "HIGH",
    ),
    "support_bot/bot.py": (
        "Support bot entry point — ticket system polling, agent assignment",
        "HIGH",
    ),
    "control_panel/static/css/style.css": (
        "SINGLE global stylesheet — all 20 panel pages depend on this one file",
        "CRITICAL",
    ),
    "control_panel/static/js/app.js": (
        "SINGLE global JS — sidebar toggle, theme switch, API calls, Chart.js, modals, alerts",
        "CRITICAL",
    ),
    "control_panel/templates/base.html": (
        "Base Jinja2 template — 19 pages extend this; nav, CSS/JS loading, theme vars all live here",
        "CRITICAL",
    ),
    "control_panel/call_graph.py": (
        "Engineering Agent — function-level call graph builder (AST-based)",
        "MEDIUM",
    ),
    "control_panel/knowledge_graph.py": (
        "Engineering Agent — unified multi-type knowledge graph + file ownership registry",
        "MEDIUM",
    ),
}


def _infer_purpose(rel: str) -> str:
    r = rel.lower()
    if "router" in r:       return f"FastAPI router — HTTP endpoints for /{Path(rel).stem} panel section"
    if "handler" in r:      return f"Telegram handler — bot commands/callbacks for {Path(rel).stem}"
    if "service" in r:      return f"Service layer — {Path(rel).stem} business logic"
    if "/database/" in r:   return f"Database layer — SQLite operations ({Path(rel).stem})"
    if r.endswith(".html"): return f"Jinja2 template — {Path(rel).stem} page"
    if r.endswith(".css"):  return f"Stylesheet — {Path(rel).stem}"
    if r.endswith(".js"):   return f"JavaScript — {Path(rel).stem}"
    if "worker" in r:       return f"Background worker — {Path(rel).stem} async task"
    if "middleware" in r:   return f"Middleware — {Path(rel).stem}"
    if "utils" in r or "util" in r: return f"Utility module — {Path(rel).stem}"
    return f"Module — {Path(rel).stem}"


def _infer_responsibilities(rel: str) -> list:
    r, out = rel.lower(), []
    if "auth"      in r: out.append("Authentication / session management")
    if "config"    in r or "settings" in r: out.append("Configuration + environment variables")
    if "database"  in r or "db"  in r: out.append("Data persistence / retrieval")
    if "download"  in r: out.append("Media download orchestration")
    if "broadcast" in r: out.append("Mass Telegram message delivery")
    if "backup"    in r: out.append("Backup creation / restoration")
    if "log"       in r: out.append("Log aggregation / error reporting")
    if "user"      in r: out.append("User management / profile data")
    if "ai_engine" in r: out.append("AI reasoning / project intelligence")
    if "subscription" in r or "sub" in r: out.append("Subscription / channel membership checks")
    if "referral"  in r: out.append("Referral system management")
    if "point"     in r: out.append("Points / gamification ledger")
    if not out:
        out.append(f"{Path(rel).stem} domain logic")
    return out


def _compute_ownership(all_files: list, edges: list) -> dict:
    dependents: dict = {}
    for e in edges:
        tgt = e["to"]
        dependents.setdefault(tgt, set()).add(e["from"])

    ownership = {}
    for rel in all_files:
        dep_set   = dependents.get(rel, set())
        dep_count = len(dep_set)

        if rel in _STATIC_OWNERSHIP:
            purpose, risk = _STATIC_OWNERSHIP[rel]
        else:
            purpose = _infer_purpose(rel)
            risk    = ("CRITICAL" if dep_count >= 8
                       else "HIGH"    if dep_count >= 4
                       else "MEDIUM"  if dep_count >= 2
                       else "LOW")

        ownership[rel] = {
            "purpose":          purpose,
            "risk_level":       risk,
            "dependent_count":  dep_count,
            "dependents":       sorted(dep_set)[:12],
            "spof":             dep_count >= 5 or risk == "CRITICAL",
            "responsibilities": _infer_responsibilities(rel),
        }
    return ownership


def _dedup(edges: list) -> list:
    seen:   set  = set()
    unique: list = []
    for e in edges:
        key = f"{e['type']}|{e['from']}|{e['to']}"
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def _build() -> dict:
    all_files  = _walk({".py", ".html", ".js", ".css"})
    py_files   = [f for f in all_files if f.endswith(".py")]
    html_files = [f for f in all_files if f.endswith(".html")]

    edges = (
        _build_import_edges(py_files)
        + _build_render_edges(py_files)
        + _build_template_edges(html_files)
        + _build_db_edges(py_files)
        + _build_config_edges(py_files)
        + _build_handler_edges(py_files)
    )
    edges = _dedup(edges)

    type_counts: dict = {}
    for e in edges:
        type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1

    nodes: set = set()
    for e in edges:
        nodes.add(e["from"])
        nodes.add(e["to"])

    ownership = _compute_ownership(all_files, edges)

    return {
        "nodes":       sorted(nodes),
        "edges":       edges,
        "ownership":   ownership,
        "edge_types":  type_counts,
        "files_total": len(all_files),
        "edges_total": len(edges),
        "built_at":    datetime.now().isoformat(),
    }


def _load_disk() -> Optional[dict]:
    try:
        if _KG_FILE.exists():
            raw = json.loads(_KG_FILE.read_text(encoding="utf-8"))
            if time.time() - raw.get("_saved_ts", 0) < _CACHE_TTL:
                return raw
    except Exception:
        pass
    return None


def _save_disk(graph: dict):
    try:
        graph["_saved_ts"] = time.time()
        _KG_FILE.write_text(
            json.dumps(graph, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception as exc:
        _log.warning("KnowledgeGraph disk save error: %s", exc)


class KnowledgeGraph:
    """Unified multi-type project knowledge graph (5-min TTL + disk persistence)."""

    @classmethod
    def get(cls) -> dict:
        global _GRAPH_CACHE, _GRAPH_TS
        if time.time() - _GRAPH_TS < _CACHE_TTL and _GRAPH_CACHE:
            return _GRAPH_CACHE
        disk = _load_disk()
        if disk:
            _GRAPH_CACHE = disk
            _GRAPH_TS    = time.time()
            return _GRAPH_CACHE
        try:
            _GRAPH_CACHE = _build()
            _GRAPH_TS    = time.time()
            _save_disk(_GRAPH_CACHE)
            _log.info(
                "KnowledgeGraph built: %d nodes | %d edges | types=%s",
                len(_GRAPH_CACHE["nodes"]),
                _GRAPH_CACHE["edges_total"],
                _GRAPH_CACHE["edge_types"],
            )
        except Exception as exc:
            _log.warning("KnowledgeGraph build error: %s", exc)
            if not _GRAPH_CACHE:
                _GRAPH_CACHE = {
                    "nodes": [], "edges": [], "ownership": {},
                    "edge_types": {}, "files_total": 0, "edges_total": 0,
                    "built_at": datetime.now().isoformat(),
                }
        return _GRAPH_CACHE

    @classmethod
    def edges_from(cls, node: str, edge_type: str = None) -> list:
        return [
            e for e in cls.get()["edges"]
            if e["from"] == node and (edge_type is None or e["type"] == edge_type)
        ]

    @classmethod
    def edges_to(cls, node: str, edge_type: str = None) -> list:
        return [
            e for e in cls.get()["edges"]
            if e["to"] == node and (edge_type is None or e["type"] == edge_type)
        ]

    @classmethod
    def what_renders(cls, router_file: str) -> list:
        return [e["to"] for e in cls.edges_from(router_file, E.RENDERS)]

    @classmethod
    def what_imports(cls, file: str) -> list:
        return [e["to"] for e in cls.edges_from(file, E.IMPORTS)]

    @classmethod
    def who_imports(cls, file: str) -> list:
        return [e["from"] for e in cls.edges_to(file, E.IMPORTS)]

    @classmethod
    def full_trace(cls, node: str) -> dict:
        """Cross-type full relationship trace for any node."""
        return {
            "imports":       cls.what_imports(node),
            "imported_by":   cls.who_imports(node),
            "renders":       cls.what_renders(node),
            "rendered_by":   [e["from"] for e in cls.edges_to(node, E.RENDERS)],
            "uses_db":       [e["to"]   for e in cls.edges_from(node, E.USES_DB)],
            "used_by":       [e["from"] for e in cls.edges_to(node, E.USES_DB)],
            "uses_js":       [e["to"]   for e in cls.edges_from(node, E.USES_JS)],
            "uses_css":      [e["to"]   for e in cls.edges_from(node, E.USES_CSS)],
            "configures":    [e["to"]   for e in cls.edges_from(node, E.CONFIGURES)],
            "configured_by": [e["from"] for e in cls.edges_to(node, E.CONFIGURES)],
            "extends":       [e["to"]   for e in cls.edges_from(node, E.EXTENDS)],
            "extended_by":   [e["from"] for e in cls.edges_to(node, E.EXTENDS)],
            "serves_routes": [e["to"]   for e in cls.edges_from(node, E.SERVES)],
            "calls_apis":    [e["to"]   for e in cls.edges_from(node, E.CALLS_API)],
            "handles_cmds":  [e["to"]   for e in cls.edges_from(node, E.HANDLES)],
        }

    @classmethod
    def data_flow(cls, entry_file: str = "bot.py") -> list:
        """
        BFS data flow trace from an entry point.
        Follows IMPORTS + USES_DB + RENDERS + CONFIGURES edges.
        Returns ordered list of flow steps.
        """
        FOLLOW = {E.IMPORTS, E.USES_DB, E.RENDERS, E.CONFIGURES}
        visited: set  = set()
        steps:  list  = []
        queue = [(entry_file, "ENTRY", 0)]
        while queue:
            node, via, depth = queue.pop(0)
            if node in visited or depth > 6:
                continue
            visited.add(node)
            steps.append({"file": node, "via": via, "depth": depth})
            for e in cls.edges_from(node):
                if e["type"] in FOLLOW and e["to"] not in visited:
                    queue.append((e["to"], e["type"], depth + 1))
        return steps

    @classmethod
    def single_points_of_failure(cls) -> list:
        own = cls.get().get("ownership", {})
        return sorted(
            [{"file": f, **v} for f, v in own.items() if v.get("spof")],
            key=lambda x: x["dependent_count"],
            reverse=True,
        )[:12]

    @classmethod
    def invalidate(cls):
        """Force rebuild on next get() call."""
        global _GRAPH_CACHE, _GRAPH_TS
        _GRAPH_CACHE = {}
        _GRAPH_TS    = 0.0
        try:
            if _KG_FILE.exists():
                _KG_FILE.unlink()
        except Exception:
            pass

    @classmethod
    def status(cls) -> dict:
        g = cls.get()
        return {
            "nodes":       len(g.get("nodes", [])),
            "edges":       g.get("edges_total", 0),
            "edge_types":  g.get("edge_types", {}),
            "files_total": g.get("files_total", 0),
            "built_at":    g.get("built_at", "never"),
            "cache_age_s": int(time.time() - _GRAPH_TS),
        }


class FileOwnership:
    """Per-file ownership, purpose, and risk metadata."""

    @classmethod
    def get(cls, rel_file: str) -> dict:
        return KnowledgeGraph.get().get("ownership", {}).get(rel_file, {
            "purpose":          "Unknown — file not indexed",
            "risk_level":       "UNKNOWN",
            "dependent_count":  0,
            "dependents":       [],
            "spof":             False,
            "responsibilities": [],
        })

    @classmethod
    def all_spof(cls) -> list:
        return KnowledgeGraph.single_points_of_failure()

    @classmethod
    def risk_report(cls) -> dict:
        own    = KnowledgeGraph.get().get("ownership", {})
        report: dict = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "UNKNOWN": []}
        for f, meta in own.items():
            lvl = meta.get("risk_level", "UNKNOWN")
            report.setdefault(lvl, []).append(f)
        return {k: sorted(v) for k, v in report.items() if v}
