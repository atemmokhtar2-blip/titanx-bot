"""
call_graph.py — Function-level call graph for TitanX Engineering Agent.

Builds a static approximation of the function call graph by AST-parsing
every Python file in the project.

Graph model:
  Node: (relative_file, function_name)  stored as "file::func"
  Forward edge: A calls B
  Reverse edge: B is called by A

Key APIs:
  CallGraph.get()                     full graph dict (5-min TTL)
  CallGraph.who_calls(file, func)     (file, func) callers
  CallGraph.what_calls(file, func)    (file, func) callees
  CallGraph.who_calls_file(file)      cross-file callers of any function in file
  CallGraph.circular_imports()        detected circular import chains
  CallGraph.chain(file, func, depth)  BFS execution chain from entry point
  CallGraph.status()                  graph metrics
"""
import ast
import os
import time
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

_log = logging.getLogger("titanx.call_graph")

_HERE         = Path(__file__).parent
EXTRACTED_DIR = _HERE.parent

SKIP_DIRS = {"__pycache__", ".git", ".pythonlibs", "node_modules",
             ".venv", "venv", "temp", "backups", "logs", "hf_space"}

_CACHE:    dict  = {}
_CACHE_TS: float = 0.0
_CACHE_TTL       = 300.0


def _walk_py() -> list:
    files = []
    for root, dirs, fnames in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            if fn.endswith(".py"):
                fp = Path(root) / fn
                try:
                    files.append(str(fp.relative_to(EXTRACTED_DIR)))
                except ValueError:
                    pass
    return sorted(files)


def _safe_parse(rel: str) -> Optional[ast.Module]:
    fp = EXTRACTED_DIR / rel
    try:
        return ast.parse(fp.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def _extract_imports(tree: ast.Module, rel: str) -> dict:
    """
    Build alias→file table for this file.
    e.g. 'from database.db import get_user' → {'get_user': 'database/db.py'}
    """
    aliases: dict = {}
    parts = rel.replace("\\", "/").split("/")
    pkg   = parts[:-1]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                cand = alias.name.replace(".", "/") + ".py"
                key  = alias.asname or alias.name.split(".")[-1]
                aliases[key] = cand

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level  = node.level or 0
            if level > 0:
                base = pkg[:max(0, len(pkg) - (level - 1))]
                cand = ("/".join(base + module.split(".")) + ".py"
                        if module else "/".join(base) + ".py")
            else:
                cand = module.replace(".", "/") + ".py"
            for alias in node.names:
                key = alias.asname or alias.name
                aliases[key] = cand

    return aliases


def _detect_circular_imports(alias_map: dict) -> list:
    """DFS-based circular import detection on file import graph."""
    import_graph: dict = {}
    for src, imp in alias_map.items():
        import_graph[src] = list({v for v in imp.values() if v.endswith(".py")})

    visited:   set = set()
    rec_stack: set = set()
    cycles:   list = []

    def dfs(node: str, path: list):
        visited.add(node)
        rec_stack.add(node)
        for nb in import_graph.get(node, []):
            if nb not in visited:
                try:
                    dfs(nb, path + [nb])
                except RecursionError:
                    pass
            elif nb in rec_stack:
                try:
                    idx   = path.index(nb)
                    cycle = path[idx:] + [nb]
                    if len(cycle) >= 2:
                        cycles.append(cycle)
                except ValueError:
                    cycles.append([node, nb])
        rec_stack.discard(node)

    for node in list(import_graph)[:200]:
        if node not in visited:
            try:
                dfs(node, [node])
            except RecursionError:
                pass
        if len(cycles) >= 10:
            break

    seen: set = set()
    unique: list = []
    for c in cycles:
        key = "→".join(sorted(c))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:10]


def _build() -> dict:
    """
    Full call graph build.
    Pass 1: collect all function definitions + import aliases per file.
    Pass 2: for every function body, resolve ast.Call nodes to (file, func) pairs.
    """
    py_files = _walk_py()

    funcs:       dict = {}
    alias_map:   dict = {}
    name_to_files: dict = {}

    for rel in py_files:
        tree = _safe_parse(rel)
        if tree is None:
            continue
        fn_names = [
            n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        funcs[rel]      = fn_names
        alias_map[rel]  = _extract_imports(tree, rel)
        for fn in fn_names:
            name_to_files.setdefault(fn, []).append(rel)

    forward: dict = {}
    reverse: dict = {}

    for rel in py_files:
        tree = _safe_parse(rel)
        if tree is None:
            continue
        imp        = alias_map.get(rel, {})
        file_funcs = set(funcs.get(rel, []))

        for fdef in ast.walk(tree):
            if not isinstance(fdef, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            caller_key = f"{rel}::{fdef.name}"
            forward.setdefault(caller_key, [])

            for child in ast.walk(fdef):
                if not isinstance(child, ast.Call):
                    continue

                call_name: Optional[str] = None
                if isinstance(child.func, ast.Name):
                    call_name = child.func.id
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name):
                        call_name = f"{child.func.value.id}.{child.func.attr}"
                    else:
                        call_name = child.func.attr

                if not call_name:
                    continue

                callee_file: Optional[str] = None
                callee_func: Optional[str] = None

                if "." in call_name:
                    obj, method = call_name.split(".", 1)
                    if obj in imp:
                        callee_file = imp[obj]
                        callee_func = method
                    elif obj in name_to_files:
                        callee_file = name_to_files[obj][0]
                        callee_func = method
                else:
                    base = call_name
                    if base in file_funcs:
                        callee_file = rel
                        callee_func = base
                    elif base in imp:
                        callee_file = imp[base]
                        callee_func = base
                    elif base in name_to_files:
                        callee_file = name_to_files[base][0]
                        callee_func = base

                if callee_file and callee_func:
                    callee_key = f"{callee_file}::{callee_func}"
                    if callee_key not in forward[caller_key]:
                        forward[caller_key].append(callee_key)
                    reverse.setdefault(callee_key, [])
                    if caller_key not in reverse[callee_key]:
                        reverse[callee_key].append(caller_key)

    circulars    = _detect_circular_imports(alias_map)
    total_nodes  = sum(len(v) for v in funcs.values())
    total_edges  = sum(len(v) for v in forward.values())

    return {
        "forward":          forward,
        "reverse":          reverse,
        "funcs":            funcs,
        "circular_imports": circulars,
        "files_scanned":    len(py_files),
        "total_nodes":      total_nodes,
        "total_edges":      total_edges,
        "built_at":         datetime.now().isoformat(),
    }


class CallGraph:
    """Public interface to the function-level call graph (5-min TTL cache)."""

    @classmethod
    def get(cls) -> dict:
        global _CACHE, _CACHE_TS
        if time.time() - _CACHE_TS < _CACHE_TTL and _CACHE:
            return _CACHE
        try:
            _CACHE    = _build()
            _CACHE_TS = time.time()
            _log.info(
                "CallGraph built: %d files | %d funcs | %d edges | %d circular",
                _CACHE["files_scanned"], _CACHE["total_nodes"],
                _CACHE["total_edges"],   len(_CACHE["circular_imports"]),
            )
        except Exception as e:
            _log.warning("CallGraph build failed: %s", e)
            if not _CACHE:
                _CACHE = {
                    "forward": {}, "reverse": {}, "funcs": {},
                    "circular_imports": [], "files_scanned": 0,
                    "total_nodes": 0, "total_edges": 0,
                    "built_at": datetime.now().isoformat(),
                }
        return _CACHE

    @classmethod
    def who_calls(cls, rel_file: str, func_name: str) -> list:
        """(file, func) pairs that call this specific function."""
        key = f"{rel_file}::{func_name}"
        out = []
        for ck in cls.get().get("reverse", {}).get(key, []):
            parts = ck.rsplit("::", 1)
            if len(parts) == 2:
                out.append((parts[0], parts[1]))
        return out

    @classmethod
    def what_calls(cls, rel_file: str, func_name: str) -> list:
        """(file, func) pairs this function calls."""
        key = f"{rel_file}::{func_name}"
        out = []
        for ck in cls.get().get("forward", {}).get(key, []):
            parts = ck.rsplit("::", 1)
            if len(parts) == 2:
                out.append((parts[0], parts[1]))
        return out

    @classmethod
    def who_calls_file(cls, rel_file: str) -> list:
        """
        Cross-file callers of any function in rel_file.
        Returns [(caller_file, caller_func, callee_func), ...]
        """
        rev     = cls.get().get("reverse", {})
        results = []
        for key, callers in rev.items():
            if not key.startswith(rel_file + "::"):
                continue
            callee_func = key.rsplit("::", 1)[-1]
            for ck in callers[:5]:
                parts = ck.rsplit("::", 1)
                if len(parts) == 2 and parts[0] != rel_file:
                    results.append((parts[0], parts[1], callee_func))
        return results[:20]

    @classmethod
    def functions_in_file(cls, rel_file: str) -> list:
        return cls.get().get("funcs", {}).get(rel_file, [])

    @classmethod
    def circular_imports(cls) -> list:
        return cls.get().get("circular_imports", [])

    @classmethod
    def chain(cls, rel_file: str, func_name: str, depth: int = 4) -> list:
        """BFS execution chain starting from (rel_file, func_name)."""
        forward = cls.get().get("forward", {})
        start   = f"{rel_file}::{func_name}"
        visited: set = set()
        queue   = [(start, 0)]
        result: list = []
        while queue:
            node, d = queue.pop(0)
            if node in visited or d > depth:
                continue
            visited.add(node)
            result.append(node)
            for callee in forward.get(node, []):
                if callee not in visited:
                    queue.append((callee, d + 1))
        return result

    @classmethod
    def status(cls) -> dict:
        g = cls.get()
        return {
            "files_scanned":    g.get("files_scanned", 0),
            "total_nodes":      g.get("total_nodes", 0),
            "total_edges":      g.get("total_edges", 0),
            "circular_imports": len(g.get("circular_imports", [])),
            "built_at":         g.get("built_at", "never"),
            "cache_age_s":      int(time.time() - _CACHE_TS),
        }
