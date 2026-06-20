"""
project_indexer.py — Phase 1: Permanent Project Index

Indexes ALL project files with their metadata:
  - Classes, functions, imports (Python)
  - Routes, handlers, template references (FastAPI routers)
  - Template names, blocks, JS/CSS links, fetch() calls (HTML)
  - Function names, fetch() calls, event listeners (JavaScript)
  - Selectors, CSS variables, media queries (CSS)

Persistence:
  Disk: .project_index.json  (full index)
       .project_index_mtimes.json  (per-file mtimes for incremental update)
  Memory TTL: 10 minutes

Incremental: only re-indexes files whose mtime changed.
Always search index first before any filesystem walk.

Public API:
  ProjectIndexer.get()                → full index dict {rel: entry}
  ProjectIndexer.search(query)        → [rel, ...] scored match
  ProjectIndexer.get_file(rel)        → entry dict for a file
  ProjectIndexer.find_function(name)  → [(rel, type), ...]
  ProjectIndexer.find_class(name)     → [rel, ...]
  ProjectIndexer.find_route(path)     → [(rel, method, path), ...]
  ProjectIndexer.find_command(cmd)    → [rel, ...]
  ProjectIndexer.context_files(ctx)   → [rel, ...] by subsystem
  ProjectIndexer.infrastructure_report() → audit stats dict
  ProjectIndexer.status()             → health dict
  ProjectIndexer.invalidate()         → force full rebuild
"""

import ast
import os
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Optional

_log = logging.getLogger("titanx.project_indexer")

_HERE         = Path(__file__).parent
EXTRACTED_DIR = _HERE.parent
_INDEX_FILE   = _HERE / ".project_index.json"
_MTIMES_FILE  = _HERE / ".project_index_mtimes.json"

SKIP_DIRS = {
    "__pycache__", ".git", ".pythonlibs", "node_modules",
    ".venv", "venv", "temp", "backups", "logs", "hf_space",
    ".ai_backups",
}
SKIP_FILES = {"ziews84U"}

_CACHE_TTL  = 600.0   # 10 minutes in-memory
_INDEX_CACHE: dict  = {}
_INDEX_TS:   float  = 0.0


# ─── Filesystem walk ──────────────────────────────────────────────────────────

def _walk_all() -> List[Path]:
    out = []
    for root, dirs, fnames in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            if fn in SKIP_FILES:
                continue
            if fn.endswith((".py", ".html", ".js", ".css")):
                out.append(Path(root) / fn)
    return out


def _read(fp: Path, cap: int = 60_000) -> str:
    try:
        return fp.read_text(encoding="utf-8", errors="ignore")[:cap]
    except Exception:
        return ""


def _rel(fp: Path) -> str:
    try:
        return str(fp.relative_to(EXTRACTED_DIR))
    except ValueError:
        return str(fp)


# ─── Python file indexer ──────────────────────────────────────────────────────

def _index_python(fp: Path) -> dict:
    src = _read(fp)
    rel = _rel(fp)
    entry: dict = {
        "type":            "python",
        "rel":             rel,
        "classes":         [],
        "functions":       [],
        "async_functions": [],
        "imports":         [],
        "routes":          [],
        "handlers":        [],
    }
    try:
        tree = ast.parse(src, filename=rel)
    except Exception:
        return entry

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            entry["classes"].append(node.name)
        elif isinstance(node, ast.FunctionDef):
            entry["functions"].append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            entry["async_functions"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                entry["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            entry["imports"].append(f"from {node.module or ''}")

    for m in re.finditer(
        r'@(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
        src,
    ):
        entry["routes"].append({"method": m.group(1).upper(), "path": m.group(2)})

    for m in re.finditer(r'CommandHandler\s*\(\s*["\'](\w+)["\']', src):
        entry["handlers"].append({"type": "command", "cmd": m.group(1)})
    for _ in re.finditer(r'CallbackQueryHandler\s*\(', src):
        entry["handlers"].append({"type": "callback"})
    for m in re.finditer(r'MessageHandler\s*\(', src):
        entry["handlers"].append({"type": "message"})

    return entry


# ─── HTML template indexer ────────────────────────────────────────────────────

def _index_html(fp: Path) -> dict:
    src  = _read(fp)
    rel  = _rel(fp)
    entry: dict = {
        "type":       "html",
        "rel":        rel,
        "extends":    None,
        "blocks":     [],
        "js_files":   [],
        "css_files":  [],
        "api_calls":  [],
        "forms":      [],
    }
    m = re.search(r'\{%[-\s]*extends\s*["\']([^"\']+)["\']', src)
    if m:
        entry["extends"] = m.group(1)
    entry["blocks"]    = re.findall(r'\{%[-\s]*block\s+(\w+)', src)
    entry["js_files"]  = re.findall(r'src=["\'][^"\']*?([^/"\']+\.js)["\']', src)
    entry["css_files"] = re.findall(r'href=["\'][^"\']*?([^/"\']+\.css)["\']', src)
    entry["api_calls"] = re.findall(r'''fetch\s*\(\s*['"]([^'"?#]+)['"]''', src)
    entry["forms"]     = re.findall(r'action=["\']([^"\']+)["\']', src)
    return entry


# ─── JavaScript indexer ───────────────────────────────────────────────────────

def _index_js(fp: Path) -> dict:
    src  = _read(fp)
    rel  = _rel(fp)
    entry: dict = {
        "type":             "js",
        "rel":              rel,
        "functions":        [],
        "api_calls":        [],
        "event_listeners":  [],
    }
    raw_funcs = re.findall(
        r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()',
        src,
    )
    entry["functions"]       = [f[0] or f[1] for f in raw_funcs if f[0] or f[1]]
    entry["api_calls"]       = re.findall(r'''fetch\s*\(\s*['"]([^'"?#]+)['"]''', src)
    entry["event_listeners"] = re.findall(r'''addEventListener\s*\(\s*['"](\w+)['"]''', src)
    return entry


# ─── CSS indexer ──────────────────────────────────────────────────────────────

def _index_css(fp: Path) -> dict:
    src  = _read(fp)
    rel  = _rel(fp)
    selectors = list(set(re.findall(r'^([.#][\w-]+)\s*\{', src, re.MULTILINE)))[:100]
    entry: dict = {
        "type":          "css",
        "rel":           rel,
        "selectors":     selectors,
        "variables":     re.findall(r'(--[\w-]+)\s*:', src)[:50],
        "media_queries": len(re.findall(r'@media\s', src)),
    }
    return entry


# ─── Disk persistence ─────────────────────────────────────────────────────────

def _load_mtimes() -> dict:
    try:
        if _MTIMES_FILE.exists():
            return json.loads(_MTIMES_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_mtimes(mtimes: dict):
    try:
        _MTIMES_FILE.write_text(json.dumps(mtimes, separators=(",", ":")))
    except Exception:
        pass


def _load_index() -> dict:
    try:
        if _INDEX_FILE.exists():
            return json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_index(index: dict):
    try:
        _INDEX_FILE.write_text(
            json.dumps(index, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception as e:
        _log.warning("ProjectIndexer save error: %s", e)


# ─── Incremental build ────────────────────────────────────────────────────────

def _build_or_update(existing_index: dict, existing_mtimes: dict) -> tuple:
    """
    Scan project. Re-index only files whose mtime changed.
    Returns (new_index, new_mtimes, stats_dict).
    """
    all_files = _walk_all()
    new_mtimes: dict = {}
    index = dict(existing_index)
    added = updated = unchanged = 0

    for fp in all_files:
        rel = _rel(fp)
        try:
            mtime = fp.stat().st_mtime
        except Exception:
            continue
        new_mtimes[rel] = mtime

        if existing_mtimes.get(rel) == mtime and rel in existing_index:
            unchanged += 1
            continue

        try:
            suf = fp.suffix
            if suf == ".py":
                entry = _index_python(fp)
            elif suf == ".html":
                entry = _index_html(fp)
            elif suf == ".js":
                entry = _index_js(fp)
            elif suf == ".css":
                entry = _index_css(fp)
            else:
                continue
            entry["mtime"] = mtime
            entry["size"]  = fp.stat().st_size
            if rel in existing_index:
                updated += 1
            else:
                added += 1
            index[rel] = entry
        except Exception as e:
            _log.debug("Index error for %s: %s", rel, e)

    for rel in list(index.keys()):
        if rel not in new_mtimes:
            del index[rel]

    return index, new_mtimes, {
        "total":     len(index),
        "added":     added,
        "updated":   updated,
        "unchanged": unchanged,
    }


# ─── Public Class ─────────────────────────────────────────────────────────────

class ProjectIndexer:
    """
    Phase 1 + Phase 10: Permanent, incremental project index with context routing.

    Context → file-pattern map (Telegram Priority Rule):
      telegram_bot  → bot.py, handlers/, support_bot/, workers/, middlewares/
      control_panel → control_panel/routers/, templates/, app.py, auth.py
      database      → database/, db.py
      frontend_layer→ static/css/, static/js/, templates/
      ai_layer      → ai_engine.py, context_engine.py, knowledge_graph.py, call_graph.py
      infrastructure→ config/settings.py, control_panel/config.py, scripts/
      support_system→ support_bot/
      deployment    → scripts/, .replit
    """

    CONTEXT_FILE_PATTERNS: dict = {
        "telegram_bot": [
            "bot.py",
            "handlers/",
            "support_bot/",
            "workers/",
            "middlewares/",
            "services/downloader",
        ],
        "control_panel": [
            "control_panel/routers/",
            "control_panel/templates/",
            "control_panel/app.py",
            "control_panel/auth.py",
            "control_panel/config.py",
        ],
        "database": [
            "database/",
            "db.py",
        ],
        "router_layer": [
            "control_panel/routers/",
        ],
        "api_layer": [
            "control_panel/routers/ai_workspace",
            "control_panel/routers/",
        ],
        "frontend_layer": [
            "control_panel/static/css/",
            "control_panel/static/js/",
            "control_panel/templates/",
        ],
        "infrastructure": [
            "config/settings.py",
            "control_panel/config.py",
            "scripts/",
        ],
        "ai_layer": [
            "control_panel/ai_engine.py",
            "control_panel/context_engine.py",
            "control_panel/knowledge_graph.py",
            "control_panel/call_graph.py",
            "control_panel/project_indexer.py",
        ],
        "support_system": [
            "support_bot/",
        ],
        "deployment": [
            "scripts/",
        ],
    }

    @classmethod
    def get(cls) -> dict:
        global _INDEX_CACHE, _INDEX_TS
        if time.time() - _INDEX_TS < _CACHE_TTL and _INDEX_CACHE:
            return _INDEX_CACHE

        existing_index  = _load_index()
        existing_mtimes = _load_mtimes()

        index, mtimes, stats = _build_or_update(existing_index, existing_mtimes)

        _save_index(index)
        _save_mtimes(mtimes)

        _INDEX_CACHE = index
        _INDEX_TS    = time.time()

        _log.info(
            "ProjectIndexer: %d files | +%d new | ~%d updated | =%d unchanged",
            stats["total"], stats["added"], stats["updated"], stats["unchanged"],
        )
        return _INDEX_CACHE

    @classmethod
    def get_file(cls, rel: str) -> dict:
        return cls.get().get(rel, {})

    @classmethod
    def search(cls, query: str, limit: int = 8) -> List[str]:
        """Score-ranked search across paths, classes, functions, routes, handlers."""
        q   = query.lower()
        idx = cls.get()
        scored: list = []
        for rel, entry in idx.items():
            score = 0
            if q in rel.lower():
                score += 3
            for fn in entry.get("functions", []) + entry.get("async_functions", []):
                if q in fn.lower():
                    score += 2
            for cls_name in entry.get("classes", []):
                if q in cls_name.lower():
                    score += 2
            for route in entry.get("routes", []):
                if q in route.get("path", "").lower():
                    score += 2
            for h in entry.get("handlers", []):
                if q in h.get("cmd", "").lower():
                    score += 3
            for imp in entry.get("imports", []):
                if q in imp.lower():
                    score += 1
            if score > 0:
                scored.append((score, rel))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]

    @classmethod
    def find_function(cls, name: str) -> List[tuple]:
        q = name.lower()
        return [
            (rel, entry.get("type", "python"))
            for rel, entry in cls.get().items()
            if any(q == f.lower()
                   for f in entry.get("functions", []) + entry.get("async_functions", []))
        ]

    @classmethod
    def find_class(cls, name: str) -> List[str]:
        q = name.lower()
        return [
            rel for rel, entry in cls.get().items()
            if any(q == c.lower() for c in entry.get("classes", []))
        ]

    @classmethod
    def find_route(cls, path: str) -> List[tuple]:
        q = path.lower().strip("/")
        out = []
        for rel, entry in cls.get().items():
            for route in entry.get("routes", []):
                if q in route.get("path", "").lower():
                    out.append((rel, route["method"], route["path"]))
        return out

    @classmethod
    def find_command(cls, cmd: str) -> List[str]:
        q = cmd.lower().lstrip("/")
        return [
            rel for rel, entry in cls.get().items()
            if any(h.get("type") == "command" and q == h.get("cmd", "").lower()
                   for h in entry.get("handlers", []))
        ]

    @classmethod
    def context_files(cls, context_name: str, limit: int = 6) -> List[str]:
        """
        Phase 10 — Telegram Priority Rule + context-based file selection.
        Returns files that belong to the given subsystem context.
        When context=telegram_bot, bot files are ALWAYS returned first.
        """
        patterns = cls.CONTEXT_FILE_PATTERNS.get(context_name, [])
        if not patterns:
            return []
        idx     = cls.get()
        matched = [rel for rel in idx if any(p in rel for p in patterns)]
        return matched[:limit]

    @classmethod
    def infrastructure_report(cls) -> dict:
        """
        Phase 19 — Agent Infrastructure Audit.
        Returns stats for every indexed system.
        """
        idx        = cls.get()
        py_files   = [r for r, e in idx.items() if e.get("type") == "python"]
        html_files = [r for r, e in idx.items() if e.get("type") == "html"]
        js_files   = [r for r, e in idx.items() if e.get("type") == "js"]
        css_files  = [r for r, e in idx.items() if e.get("type") == "css"]
        all_routes   = [r for e in idx.values() for r in e.get("routes", [])]
        all_handlers = [h for e in idx.values() for h in e.get("handlers", [])]
        all_classes  = [c for e in idx.values() for c in e.get("classes", [])]
        all_funcs    = [
            f for e in idx.values()
            for f in e.get("functions", []) + e.get("async_functions", [])
        ]
        bot_handlers  = [r for r in py_files if "handlers/" in r]
        bot_files     = [r for r in py_files if "bot.py" in r or "support_bot" in r]
        router_files  = [r for r in py_files if "routers/" in r]
        template_files = html_files
        db_files      = [r for r in py_files if "database/" in r]
        service_files = [r for r in py_files if "services/" in r]
        return {
            "total_files":    len(idx),
            "python":         len(py_files),
            "html":           len(html_files),
            "js":             len(js_files),
            "css":            len(css_files),
            "total_routes":   len(all_routes),
            "total_handlers": len(all_handlers),
            "total_classes":  len(all_classes),
            "total_functions": len(all_funcs),
            "bot_handlers":   len(bot_handlers),
            "bot_files":      len(bot_files),
            "router_files":   len(router_files),
            "template_files": len(template_files),
            "db_files":       len(db_files),
            "service_files":  len(service_files),
        }

    @classmethod
    def status(cls) -> dict:
        idx = cls.get()
        return {
            "total_files":   len(idx),
            "cache_age_s":   int(time.time() - _INDEX_TS),
            "cache_ttl_s":   int(_CACHE_TTL),
            "index_on_disk": _INDEX_FILE.exists(),
            "index_path":    str(_INDEX_FILE),
            "phase":         1,
        }

    @classmethod
    def invalidate(cls):
        """Force full rebuild on next get() call."""
        global _INDEX_CACHE, _INDEX_TS
        _INDEX_CACHE = {}
        _INDEX_TS    = 0.0
        try:
            if _INDEX_FILE.exists():
                _INDEX_FILE.unlink()
            if _MTIMES_FILE.exists():
                _MTIMES_FILE.unlink()
        except Exception:
            pass
