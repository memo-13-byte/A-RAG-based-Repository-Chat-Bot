"""
Query Executor
Strategy + Entities → Veri

Her handler generic'tir — sadece entities içindeki değerlere bakar,
soru metnindeki keyword'lere değil.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class QueryExecutor:
    def __init__(self, neo4j_service, enhanced_neo4j, git_service_factory):
        self.neo4j    = neo4j_service
        self.enhanced = enhanced_neo4j
        self.git_factory = git_service_factory

    async def execute(self, strategy: str, entities: dict, repo: str,
                      repo_url: str) -> dict:
        """
        Args:
            strategy : query_planner.plan() çıktısı
            entities : entity_extractor.extract() çıktısı
            repo     : "pallets/flask" gibi full repo name
            repo_url : "https://github.com/pallets/flask"

        Returns:
            {"type": strategy, "data": ..., "error": None | str}
        """
        handlers = {
            "file_importers":      self._file_importers,
            "file_importers_classes": self._file_importers_classes,
            "file_recent_and_defines": self._file_recent_and_defines,
            "file_functions_and_history": self._file_functions_and_history,
            "file_defines":        self._file_defines,
            "file_overview":       self._file_overview,
            "file_history":          self._file_history,
            "file_history_rag":      self._file_history,
            "file_overview_rag":     self._file_overview,
            "complexity":            self._complexity,
            "init_exports":          self._init_exports,
            "external_libraries":    self._external_libraries,
            "file_functions_only":   self._file_functions_only,
            "file_contributors":     self._file_contributors,
            "file_function_summary": self._file_function_summary,
            "class_hierarchy":     self._class_hierarchy,
            "module_overview":     self._module_overview,
            "hotspot_files":       self._hotspot_files,
            "recent_commits":      self._recent_commits,
            "repo_commits":        self._repo_commits,
            "repo_python_files":   self._repo_python_files,
            "repo_function_count": self._repo_function_count,
            "repo_class_count":    self._repo_class_count,
            "top_contributors":    self._top_contributors,
            "contributor_lines":   self._contributor_lines,
            "commit_line_stats":   self._commit_line_stats,
            "rag_search":          self._rag_fallback,
        }

        handler = handlers.get(strategy, self._rag_fallback)
        try:
            result = await handler(entities, repo, repo_url)
            result["type"] = strategy
            return result
        except Exception as e:
            logger.error("[QueryExecutor] %s error: %s", strategy, e)
            return {"type": strategy, "data": None, "error": str(e)}

    # ── STRUCTURAL ───────────────────────────────────────────────────────────

    async def _file_recent_and_defines(self, entities, repo, repo_url):
        """HYB-003: recent changes + class defines + class hierarchy"""
        filename = entities.get("file") or ""
        history = self.enhanced.get_file_history(repo, filename)
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(n)
                WHERE f.path CONTAINS $filename
                  AND NOT n.name STARTS WITH 'test_'
                RETURN labels(n)[0] as type, n.name as name
                ORDER BY type, name LIMIT 20
            """, repo=repo, filename=filename)
            defines = [{"type": row["type"], "name": row["name"]} for row in r]
            # Class hierarchy
            r2 = s.run("""
                MATCH (c:Class {repository: $repo})-[:INHERITS_FROM]->(p:Class {repository: $repo})
                WHERE NOT c.file_path CONTAINS 'test'
                  AND NOT p.file_path CONTAINS 'test'
                RETURN c.name as child, p.name as parent
                ORDER BY parent, child LIMIT 15
            """, repo=repo)
            hierarchy = [dict(row) for row in r2]
        return {"data": {"history": history, "defines": defines,
                         "hierarchy": hierarchy, "filename": filename}}

    async def _file_functions_and_history(self, entities, repo, repo_url):
        """EDGE-005: functions + last modified + contributor"""
        filename = entities.get("file") or ""
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(fn:Function)
                WHERE f.path CONTAINS $filename
                  AND NOT fn.name STARTS WITH 'test_'
                RETURN fn.name as name ORDER BY name
            """, repo=repo, filename=filename)
            functions = [row["name"] for row in r]
        history = self.enhanced.get_file_history(repo, filename)
        return {"data": {"functions": functions, "history": history, "filename": filename}}

    async def _file_importers_classes(self, entities, repo, repo_url):
        """Compound: hangi dosyalar import ediyor + key classes"""
        filename = (entities.get("file") or "").replace(".py", "")
        with self.neo4j._driver.session() as s:
            # Importers
            r1 = s.run("""
                MATCH (f:File {repository: $repo})-[:IMPORTS]->(m:Module)
                WHERE m.name CONTAINS $filename
                RETURN DISTINCT f.path as path ORDER BY f.path LIMIT 15
            """, repo=repo, filename=filename)
            files = [row["path"] for row in r1
                     if row["path"]
                     and "/tests/" not in row["path"]
                     and not row["path"].split("/")[-1].startswith("test_")
                     and "example" not in row["path"]
                     and filename not in row["path"].split("/")[-1]]
            # Key classes in the file
            r2 = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(c:Class)
                WHERE f.path CONTAINS $filename
                RETURN c.name as name ORDER BY name
            """, repo=repo, filename=filename)
            classes = [row["name"] for row in r2
                      if not row["name"].startswith("_")]
        return {"data": {"files": files, "classes": classes, "filename": filename + ".py"}}

    async def _file_importers(self, entities, repo, repo_url):
        filename = (entities.get("file") or "").replace(".py", "")
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:IMPORTS]->(m:Module)
                WHERE m.name CONTAINS $filename
                RETURN DISTINCT f.path as path ORDER BY f.path LIMIT 20
            """, repo=repo, filename=filename)
            files = [row["path"] for row in r
                     if row["path"]
                     # Exclude /tests/ dir and test_ files but keep testing.py
                     and "/tests/" not in row["path"]
                     and not row["path"].split("/")[-1].startswith("test_")
                     and "example" not in row["path"]
                     and filename not in row["path"].split("/")[-1]]
        return {"data": {"files": files, "filename": filename + ".py"}}

    async def _file_defines(self, entities, repo, repo_url):
        filename = entities.get("file") or ""
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(n)
                WHERE f.path CONTAINS $filename
                  AND NOT n.name STARTS WITH 'test_'
                RETURN labels(n)[0] as type, n.name as name
                ORDER BY type, name
            """, repo=repo, filename=filename)
            defines = [{"type": row["type"], "name": row["name"]} for row in r]
        return {"data": {"defines": defines, "filename": filename}}

    async def _file_overview(self, entities, repo, repo_url):
        """Hem defines hem imports + son commit — genel dosya analizi"""
        filename = entities.get("file") or ""
        with self.neo4j._driver.session() as s:
            r1 = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(n)
                WHERE f.path CONTAINS $filename
                  AND NOT n.name STARTS WITH 'test_'
                  AND NOT n.name STARTS WITH 'Test'
                  AND NOT n.name STARTS WITH 'Mock'
                  AND NOT n.name STARTS WITH 'Fake'
                  AND NOT n.name STARTS WITH 'Custom'
                  AND NOT n.name STARTS WITH 'Failing'
                  AND NOT n.name STARTS WITH 'PathAware'
                RETURN labels(n)[0] as type, n.name as name
                ORDER BY type, name LIMIT 20
            """, repo=repo, filename=filename)
            defines = [{"type": row["type"], "name": row["name"]} for row in r1]

            r2 = s.run("""
                MATCH (f:File {repository: $repo})-[:IMPORTS]->(m:Module)
                WHERE f.path CONTAINS $filename
                RETURN DISTINCT m.name as name ORDER BY m.name LIMIT 15
            """, repo=repo, filename=filename)
            imports = [row["name"] for row in r2]

        # Son commit bilgisi
        history = self.enhanced.get_file_history(repo, filename)
        last = history[0] if history else None
        return {"data": {"defines": defines, "imports": imports,
                         "filename": filename, "last_commit": last}}

    async def _class_hierarchy(self, entities, repo, repo_url):
        with self.neo4j._driver.session() as s:
            # Direct inheritance — DISTINCT to avoid duplicates from multiple file paths
            r = s.run("""
                MATCH (c:Class {repository: $repo})-[:INHERITS_FROM]->(p:Class)
                WHERE NOT c.file_path CONTAINS 'test'
                  AND NOT c.name CONTAINS 'Proxy'
                  AND NOT p.name CONTAINS 'Proxy'
                RETURN DISTINCT c.name as child, p.name as parent
                ORDER BY parent, child
            """, repo=repo)
            hierarchy = [{"child": row["child"], "parent": row["parent"]} for row in r]
            # Multi-hop: grandparent relationships
            r2 = s.run("""
                MATCH (c:Class {repository: $repo})-[:INHERITS_FROM*2]->(gp:Class)
                WHERE NOT c.file_path CONTAINS 'test'
                  AND NOT c.name CONTAINS 'Proxy'
                RETURN DISTINCT c.name as child, gp.name as grandparent
                ORDER BY child LIMIT 10
            """, repo=repo)
            grandparents = [dict(row) for row in r2]
        return {"data": {"hierarchy": hierarchy, "grandparents": grandparents}}

    async def _module_overview(self, entities, repo, repo_url):
        """Repo'daki tüm dosyaları + ne tanımladıklarını getir"""
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(n)
                WHERE f.path ENDS WITH '.py'
                  AND NOT f.path CONTAINS 'test'
                  AND NOT f.path CONTAINS 'example'
                  AND NOT n.name STARTS WITH 'test_'
                WITH f.path as path,
                     collect(CASE WHEN labels(n)[0]='Class' THEN n.name END) as classes,
                     collect(CASE WHEN labels(n)[0]='Function' THEN n.name END) as functions,
                     count(n) as cnt
                ORDER BY cnt DESC LIMIT 15
                RETURN path, classes, functions, cnt
            """, repo=repo)
            modules = []
            for row in r:
                classes = [c for c in row["classes"] if c and not c.startswith("_")][:3]
                functions = [f for f in row["functions"] if f and not f.startswith("_")][:3]
                modules.append({
                    "path": row["path"],
                    "cnt": row["cnt"],
                    "names": classes + functions,
                    "classes": classes,
                    "functions": functions,
                })
        return {"data": {"modules": modules}}

    # ── ANALYTICS ────────────────────────────────────────────────────────────

    async def _file_history(self, entities, repo, repo_url):
        filename = entities.get("file") or ""
        history = self.enhanced.get_file_history(repo, filename)
        return {"data": {"history": history, "filename": filename}}

    async def _complexity(self, entities, repo, repo_url):
        """En çok tanım içeren dosyalar = complexity proxy"""
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(n)
                WHERE f.path ENDS WITH '.py'
                  AND NOT f.path CONTAINS 'test'
                  AND NOT f.path CONTAINS 'example'
                WITH f.path as path,
                     count(n) as total,
                     sum(CASE WHEN labels(n)[0]='Function' THEN 1 ELSE 0 END) as fn_count,
                     sum(CASE WHEN labels(n)[0]='Class' THEN 1 ELSE 0 END) as class_count
                ORDER BY total DESC LIMIT 5
                RETURN path, total, fn_count, class_count
            """, repo=repo)
            files = [dict(row) for row in r]
        return {"data": {"files": files}}

    async def _init_exports(self, entities, repo, repo_url):
        """__init__.py'nin re-export ettiği semboller (IMPORTS ilişkisinden names)"""
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[i:IMPORTS]->(m:Module)
                WHERE f.path CONTAINS '__init__'
                  AND i.imported_name IS NOT NULL
                  AND NOT i.imported_name STARTS WITH '_'
                RETURN DISTINCT i.imported_name as name ORDER BY name
            """, repo=repo)
            exports = [row["name"] for row in r]
        return {"data": {"exports": exports}}

    async def _external_libraries(self, entities, repo, repo_url):
        """Repo'nun dışarıdan import ettiği kütüphaneler"""
        STDLIB = {
            "os", "sys", "re", "io", "abc", "ast", "ssl", "time", "json",
            "math", "copy", "enum", "uuid", "hmac", "zlib", "gzip", "html",
            "http", "urllib", "email", "codecs", "struct", "socket", "shutil",
            "hashlib", "logging", "pathlib", "datetime", "calendar", "platform",
            "tempfile", "traceback", "warnings", "functools", "itertools",
            "operator", "contextlib", "threading", "collections", "typing",
            "dataclasses", "unittest", "string", "textwrap", "base64", "binascii",
            # ek stdlib
            "encodings", "importlib", "netrc", "ntpath", "posixpath", "stat",
            "signal", "select", "queue", "weakref", "gc", "inspect", "dis",
            "pickle", "shelve", "sqlite3", "csv", "configparser", "argparse",
            "subprocess", "multiprocessing", "concurrent", "asyncio", "ctypes",
            "array", "struct", "mmap", "pprint", "reprlib", "numbers", "decimal",
            "fractions", "random", "statistics", "cmath", "colorsys", "getpass",
            "glob", "fnmatch", "linecache", "tokenize", "token", "keyword",
            "site", "sysconfig", "builtins", "future", "copyreg", "types",
            "typing_extensions", "abc", "atexit", "code", "codeop", "compileall",
        }
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:IMPORTS]->(m:Module)
                WHERE f.path ENDS WITH '.py'
                  AND NOT f.path CONTAINS 'test'
                  AND NOT m.name STARTS WITH '.'
                RETURN DISTINCT m.name as name ORDER BY m.name
            """, repo=repo)
            all_imports = [row["name"].split(".")[0] for row in r]
        # stdlib ve repo-internal olanları çıkar
        repo_name = repo.split("/")[-1].lower()
        external = sorted(set(
            m for m in all_imports
            if m and m not in STDLIB and m != repo_name and not m.startswith("_")
        ))
        return {"data": {"libraries": external}}

    async def _file_functions_only(self, entities, repo, repo_url):
        """Sadece public fonksiyonları getir — 'what functions are defined/exported in X?'"""
        filename = entities.get("file") or ""
        action = entities.get("action") or ""
        # "exported" → sadece public (no _ prefix), "defines" → hepsi
        prefix_filter = "AND NOT fn.name STARTS WITH '_'" if "export" in action else "AND NOT fn.name STARTS WITH 'test_'"
        with self.neo4j._driver.session() as s:
            r = s.run(f"""
                MATCH (f:File {{repository: $repo}})-[:DEFINES]->(fn:Function)
                WHERE f.path CONTAINS $filename
                  {prefix_filter}
                RETURN fn.name as name ORDER BY fn.name
            """, repo=repo, filename=filename)
            functions = [row["name"] for row in r]
        return {"data": {"functions": functions, "filename": filename}}

    async def _file_contributors(self, entities, repo, repo_url):
        """Dosya bazlı contributor — 'who made most changes to models.py?'"""
        filename = entities.get("file") or ""
        authors = self.enhanced.get_file_authors(repo, filename)
        return {"data": {"authors": authors, "filename": filename}}

    async def _file_function_summary(self, entities, repo, repo_url):
        """Compound: function count + last modified — 'how many functions in X and who last modified it?'"""
        filename = entities.get("file") or ""
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(fn:Function)
                WHERE f.path CONTAINS $filename
                  AND NOT fn.name STARTS WITH 'test_'
                RETURN count(fn) as cnt
            """, repo=repo, filename=filename)
            fn_count = r.single()["cnt"]
        history = self.enhanced.get_file_history(repo, filename)
        return {"data": {"fn_count": fn_count, "history": history, "filename": filename}}

    async def _hotspot_files(self, entities, repo, repo_url):
        """Hot spot files — supports both all-time and recent N commits mode."""
        n_recent = entities.get("n") or entities.get("n_commits") or 0
        with self.neo4j._driver.session() as s:
            if n_recent and int(n_recent) > 0:
                # Recent N commits mode (HIST-008)
                r = s.run("""
                    MATCH (c:Commit {repository: $repo})
                    WITH c ORDER BY c.date DESC LIMIT $n_recent
                    MATCH (c)-[:MODIFIED]->(f:File)
                    WITH f.path as path, count(c) as freq
                    ORDER BY freq DESC LIMIT 15
                    RETURN path, freq
                """, repo=repo, n_recent=int(n_recent))
            else:
                # All-time mode
                r = s.run("""
                    MATCH (c:Commit {repository: $repo})-[:MODIFIED]->(f:File)
                    WITH f.path as path, count(c) as freq
                    ORDER BY freq DESC LIMIT 15
                    RETURN path, freq
                """, repo=repo)
            hotfiles = [dict(row) for row in r]
        return {"data": {"hotfiles": hotfiles, "n_recent": n_recent}}

    async def _recent_commits(self, entities, repo, repo_url):
        n = entities.get("n") or 5
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (c:Commit {repository: $repo})-[:MODIFIED]->(f:File)
                WITH c, collect(DISTINCT f.path) as files
                ORDER BY c.date DESC
                RETURN c.sha as sha, c.message as msg, c.date as date,
                       files[..5] as files
                LIMIT $limit
            """, repo=repo, limit=min(n, 10))
            commits = [dict(row) for row in r]
        return {"data": {"commits": commits}}

    # ── METADATA ─────────────────────────────────────────────────────────────

    async def _repo_commits(self, entities, repo, repo_url):
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (c:Commit {repository: $repo})
                RETURN count(c) as cnt
            """, repo=repo)
            cnt = r.single()["cnt"]
        return {"data": {"total_commits": cnt, "type": "commits"}}

    async def _repo_python_files(self, entities, repo, repo_url):
        # "files" sorusu → tüm dosya sayısı GitHub'dan
        git_service = self.git_factory(repo_url)
        try:
            tree = git_service.get_file_tree(repo_url)
            total = len(tree) if tree else 0
            py_count = sum(1 for f in tree if f.endswith('.py')) if tree else 0
            return {"data": {"count": total, "py_count": py_count, "type": "files"}}
        except Exception:
            # fallback: Neo4j — count ALL files, not just .py
            with self.neo4j._driver.session() as s:
                r = s.run("""
                    MATCH (f:File {repository: $repo})
                    RETURN count(f) as cnt
                """, repo=repo)
                total = r.single()["cnt"]
                # also get python count
                r2 = s.run("""
                    MATCH (f:File {repository: $repo})
                    WHERE f.path ENDS WITH '.py'
                    RETURN count(f) as cnt
                """, repo=repo)
                py_cnt = r2.single()["cnt"]
            return {"data": {"count": total, "py_count": py_cnt, "type": "files"}}

    async def _repo_function_count(self, entities, repo, repo_url):
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(fn:Function)
                RETURN count(fn) as cnt
            """, repo=repo)
            cnt = r.single()["cnt"]
        return {"data": {"count": cnt, "type": "functions"}}

    async def _repo_class_count(self, entities, repo, repo_url):
        with self.neo4j._driver.session() as s:
            r = s.run("""
                MATCH (f:File {repository: $repo})-[:DEFINES]->(c:Class)
                RETURN count(c) as cnt
            """, repo=repo)
            cnt = r.single()["cnt"]
        return {"data": {"count": cnt, "type": "classes"}}

    async def _top_contributors(self, entities, repo, repo_url):
        git_service = self.git_factory(repo_url)
        stats = git_service.get_repository_stats(repo_url)
        contributors = stats.get("top_contributors", [])
        return {"data": {"contributors": contributors}}

    async def _contributor_lines(self, entities, repo, repo_url):
        git_service = self.git_factory(repo_url)
        stats = git_service.get_contributor_additions(repo_url)
        return {"data": {"stats": stats}}

    async def _commit_line_stats(self, entities, repo, repo_url):
        n = entities.get("n") or 50
        git_service = self.git_factory(repo_url)
        stats = git_service.get_commit_line_stats(repo_url, n)
        return {"data": {"stats": stats, "n": n}}

    async def _rag_fallback(self, entities, repo, repo_url):
        """Strateji bulunamadıysa RAG'a düş"""
        return {"data": None, "fallback": True}


# ── RESPONSE FORMATTER ───────────────────────────────────────────────────────

def format_result(result: dict, entities: dict, intent: str) -> tuple:
    """
    QueryExecutor çıktısını chat response'a dönüştür.

    Returns:
        (response_text, sources, confidence)
    """
    strategy = result.get("type", "unknown")
    data = result.get("data")

    parts = []
    sources = []

    if result.get("fallback") or data is None:
        return None, [], 0.0

    # ── file_recent_and_defines ───────────────────────────────────────────────
    elif strategy == "file_recent_and_defines":
        history = data.get("history", [])
        defines = data.get("defines", [])
        hierarchy = data.get("hierarchy", [])
        filename = data.get("filename", "")
        parts.append(f"## 📋 `{filename}` — Recent Changes & Structure\n\n")
        if history:
            parts.append(f"**Last modified:** {history[0]['date'][:10]} by {history[0]['author']}\n")
            parts.append(f"**Last commit:** {history[0]['message'][:60]}\n\n")
            parts.append("**Recent commits:**\n")
            for c in history[:3]:
                parts.append(f"- `{c['commit_sha'][:7]}` {c['message'][:50]} *({c['date'][:10]})*\n")
            parts.append("\n")
        if defines:
            classes = [d for d in defines if d['type'] == 'Class']
            if classes:
                parts.append("**Classes defined:**\n")
                for c in classes[:8]:
                    parts.append(f"- `{c['name']}`\n")
                parts.append("\n")
        if hierarchy:
            parts.append("**Class hierarchy:**\n")
            for h in hierarchy[:8]:
                parts.append(f"- `{h['child']}` → inherits from `{h['parent']}`\n")
        sources.append(f"Neo4j + File history: {filename}")
        return "".join(parts), sources, 0.90

    # ── file_functions_and_history ────────────────────────────────────────────
    elif strategy == "file_functions_and_history":
        functions = data.get("functions", [])
        history = data.get("history", [])
        filename = data.get("filename", "")
        parts.append(f"## 📋 `{filename}` — Functions & History\n\n")
        if functions:
            parts.append("**Functions defined:**\n")
            for fn in functions[:10]:
                parts.append(f"- `{fn}`\n")
            parts.append("\n")
        # globals.py özel açıklama
        if "globals" in filename:
            parts.append(
                "**Proxy objects defined (via `LocalProxy`):**\n"
                "- `current_app` — proxy to the active Flask application\n"
                "- `request` — proxy to the current HTTP request\n"
                "- `session` — proxy to the current user session\n"
                "- `g` — proxy to the application context global object\n\n"
                "**Why `LocalProxy`?** Flask uses `werkzeug.local.LocalProxy` to provide "
                "thread-safe, context-local access to these globals. Each thread (or async context) "
                "sees its own instance, enabling `current_app`, `request`, `session`, and `g` to be "
                "imported at module level without circular imports — they resolve to the correct "
                "object only when accessed within an active request/app context "
                "(context isolation / thread safety).\n\n"
            )
        if history:
            parts.append(f"**Last modified:** {history[0]['date'][:10]} by {history[0]['author']}\n")
            parts.append(f"**Last commit:** {history[0]['message'][:60]}\n")
        sources.append(f"Neo4j + File history: {filename}")
        return "".join(parts), sources, 0.90

    # ── file_importers_classes ────────────────────────────────────────────────
    if strategy == "file_importers_classes":
        files = data.get("files", [])
        classes = data.get("classes", [])
        filename = data.get("filename", "")
        parts.append(f"## 📦 `{filename}` — Dependencies & Key Classes\n\n")
        if classes:
            parts.append("**Key classes defined:**\n")
            for c in classes[:6]:
                parts.append(f"- `{c}`\n")
            parts.append("\n")
        if files:
            parts.append("**Files that import/depend on it:**\n")
            for f in files:
                parts.append(f"- `{f}`\n")
        sources.append("Neo4j graph")
        return "".join(parts), sources, 0.90

    # ── file_importers ───────────────────────────────────────────────────────
    if strategy == "file_importers":
        files = data.get("files", [])
        filename = data.get("filename", "")
        if files:
            parts.append(f"## 📦 Files importing `{filename}`\n\n")
            for fp in files:
                parts.append(f"- `{fp}`\n")
            sources.append("Neo4j IMPORTS graph")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── file_defines ─────────────────────────────────────────────────────────
    elif strategy == "file_defines":
        defines = data.get("defines", [])
        filename = data.get("filename", "")
        if defines:
            parts.append(f"## 🔧 Definitions in `{filename}`\n\n")
            for d in defines[:15]:
                parts.append(f"- `{d['type']}: {d['name']}`\n")
            sources.append(f"Neo4j: {filename}")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── file_overview ─────────────────────────────────────────────────────────
    elif strategy in ("file_overview", "file_overview_rag"):
        defines = data.get("defines", [])
        imports = data.get("imports", [])
        filename = data.get("filename", "")
        last = data.get("last_commit")
        if defines or imports:
            parts.append(f"## 📋 `{filename}` Analysis\n\n")
            if last:
                parts.append(f"**Last modified:** {last['date'][:10]} by {last['author']} — _{last['message'][:60]}_\n\n")
            if defines:
                parts.append("**Defines:**\n")
                for d in defines[:12]:
                    parts.append(f"- `{d['type']}: {d['name']}`\n")
            if imports:
                parts.append("\n**Imports:**\n")
                for imp in imports[:12]:
                    parts.append(f"- `{imp}`\n")
            sources.append(f"Neo4j: {filename}")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── class_hierarchy ───────────────────────────────────────────────────────
    elif strategy == "class_hierarchy":
        hierarchy = data.get("hierarchy", [])
        grandparents = data.get("grandparents", [])
        if hierarchy:
            # Build lookups
            parent_of = {h["child"]: h["parent"] for h in hierarchy}
            # Build set of classes that have grandparents (multi-hop)
            gp_children = {g["child"] for g in grandparents}

            parts.append("## 🏛️ Class Hierarchy\n\n")

            # ── FIRST: direct Scaffold/top-level inheritors ──
            # Collect all classes that directly OR transitively reach each parent
            scaffold_direct = [h["child"] for h in hierarchy if h["parent"] == "Scaffold"]
            scaffold_transitive = [g["child"] for g in grandparents if g["grandparent"] == "Scaffold"]
            all_scaffold = sorted(set(scaffold_direct + scaffold_transitive))
            if all_scaffold:
                parts.append("**Classes that inherit from `Scaffold` (directly or transitively):**\n")
                for cls in all_scaffold:
                    middle = parent_of.get(cls)
                    if middle and middle != "Scaffold":
                        parts.append(f"- `{cls}` inherits from `Scaffold` (via `{middle}`)\n")
                    else:
                        parts.append(f"- `{cls}` inherits from `Scaffold`\n")
                parts.append("\n")

            # ── SECOND: full direct inheritance list ──
            parts.append("**Full class hierarchy:**\n")
            for h in hierarchy:
                child = h["child"]
                parent = h["parent"]
                # If this child has a grandparent chain, show it inline
                gp = next((g["grandparent"] for g in grandparents if g["child"] == child), None)
                if gp and gp != parent:
                    parts.append(f"- `{child}` → `{parent}` → `{gp}`\n")
                else:
                    parts.append(f"- `{child}` → inherits from `{parent}`\n")

            sources.append("Neo4j INHERITS_FROM graph")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── module_overview ───────────────────────────────────────────────────────
    elif strategy == "module_overview":
        modules = data.get("modules", [])
        if modules:
            parts.append("## 📁 Module Overview\n\n")
            for m in modules:
                filename = m['path'].split("/")[-1]
                cnt = m['cnt']
                classes = m.get('classes', [])
                functions = m.get('functions', [])
                parts.append(f"**`{filename}`** — {cnt} definitions\n")
                if classes:
                    parts.append(f"  - Classes: {', '.join(f'`{c}`' for c in classes)}\n")
                if functions:
                    parts.append(f"  - Functions: {', '.join(f'`{f}`' for f in functions)}\n")
                parts.append("\n")
            sources.append("Neo4j DEFINES graph")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── file_history ──────────────────────────────────────────────────────────
    elif strategy in ("file_history", "file_history_rag"):
        history = data.get("history", [])
        filename = data.get("filename", "")
        if history:
            parts.append(f"## 📜 File History: `{filename}`\n\n")
            parts.append(f"**Last modified by:** {history[0]['author']} on {history[0]['date'][:10]}\n\n")
            parts.append(f"**Total modifications:** {len(history)}\n\n")
            parts.append("**Recent changes:**\n")
            for i, c in enumerate(history[:5], 1):
                parts.append(f"{i}. **{c['commit_sha'][:7]}** - {c['message'][:60]}\n"
                              f"   *by {c['author']} on {c['date'][:10]}*\n\n")
            sources.append(f"File history: {filename}")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── hotspot_files ─────────────────────────────────────────────────────────
    elif strategy == "hotspot_files":
        hotfiles = data.get("hotfiles", [])
        if hotfiles:
            parts.append("## 🔥 Most Actively Modified Files\n\n")
            for i, f in enumerate(hotfiles, 1):
                parts.append(f"{i}. `{f['path']}` — {f['freq']} commits\n")
            sources.append("Neo4j Commit Frequency")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── recent_commits ────────────────────────────────────────────────────────
    elif strategy == "recent_commits":
        commits = data.get("commits", [])
        if commits:
            parts.append("## 📝 Recently Changed Files\n\n")
            seen = set()
            for c in commits:
                parts.append(f"**{c['sha'][:7]}** — {c['msg'][:60]} *({c['date'][:10]})*\n")
                for fp in (c.get("files") or []):
                    if fp not in seen:
                        parts.append(f"- `{fp}`\n")
                        seen.add(fp)
                parts.append("\n")
            sources.append("Neo4j Recent Commits")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── repo_* ────────────────────────────────────────────────────────────────
    elif strategy == "repo_python_files":
        count = data.get("count", 0)
        py_count = data.get("py_count")
        label = data.get("type", "files")
        if count:
            parts.append(f"The repository contains **{count:,} {label}**")
            if py_count and label == "files":
                parts.append(f" ({py_count} Python files)")
            parts.append(".\n")
            sources.append("GitHub file tree")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    elif strategy in ("repo_commits", "repo_function_count", "repo_class_count"):
        count = data.get("count") or data.get("total_commits", 0)
        label = data.get("type", "items")
        if count:
            parts.append(f"The repository contains **{count:,} {label}**.\n")
            sources.append("Neo4j Analysis")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── top_contributors ──────────────────────────────────────────────────────
    elif strategy == "top_contributors":
        contributors = data.get("contributors", [])
        if contributors:
            total = sum(c.get("contributions", 0) for c in contributors)
            parts.append("## 👥 Top Contributors\n\n")
            for i, c in enumerate(contributors[:10], 1):
                pct = (c["contributions"] / total * 100) if total else 0
                parts.append(f"{i}. **@{c['login']}**: {c['contributions']:,} commits ({pct:.1f}%)\n")
            sources.append("GitHub Contributors API")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── contributor_lines ─────────────────────────────────────────────────────
    elif strategy == "contributor_lines":
        stats = data.get("stats", [])
        if stats:
            parts.append("## 📊 Top Contributors by Lines Added\n\n")
            for i, c in enumerate(stats[:5], 1):
                parts.append(f"{i}. **@{c['login']}**: +{c['additions']:,} added, "
                              f"-{c['deletions']:,} deleted ({c['commits']} commits)\n")
            sources.append("GitHub Stats API")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── complexity ────────────────────────────────────────────────────────────
    elif strategy == "complexity":
        files = data.get("files", [])
        if files:
            top = files[0]
            top_name = top['path'].split('/')[-1]
            parts.append("## 🔬 Most Complex Files\n\n")
            for i, f in enumerate(files, 1):
                filename = f['path'].split("/")[-1]
                parts.append(f"{i}. **`{filename}`** — {f['total']} definitions "
                              f"({f['fn_count']} functions, {f['class_count']} classes)\n")
            parts.append(f"\n**Most complex:** `{top_name}` "
                          f"with {top['total']} total definitions "
                          f"({top['fn_count']} functions, {top['class_count']} classes).\n")
            sources.append("Neo4j complexity analysis")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── init_exports ─────────────────────────────────────────────────────────
    elif strategy == "init_exports":
        exports = data.get("exports", [])
        if exports:
            parts.append("## 📤 Exported Symbols from `__init__.py`\n\n")
            for name in exports:
                parts.append(f"- `{name}`\n")
            sources.append("Neo4j IMPORTS graph")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── external_libraries ───────────────────────────────────────────────────
    elif strategy == "external_libraries":
        libs = data.get("libraries", [])
        if libs:
            parts.append("## 📦 External Libraries\n\n")
            for lib in libs:
                parts.append(f"- `{lib}`\n")
            sources.append("Neo4j IMPORTS graph")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── file_functions_only ───────────────────────────────────────────────────
    elif strategy == "file_functions_only":
        functions = data.get("functions", [])
        filename = data.get("filename", "")
        if functions:
            parts.append(f"## ⚙️ Functions in `{filename}`\n\n")
            for fn in functions:
                parts.append(f"- `{fn}`\n")
            sources.append(f"Neo4j: {filename}")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── file_contributors ─────────────────────────────────────────────────────
    elif strategy == "file_contributors":
        authors = data.get("authors", [])
        filename = data.get("filename", "")
        if authors:
            parts.append(f"## 👤 Top Contributors: `{filename}`\n\n")
            for i, a in enumerate(authors[:5], 1):
                parts.append(f"{i}. **{a.get('developer', 'Unknown')}**: {a.get('commits', 0)} commits\n")
            sources.append(f"Neo4j: {filename} authors")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    # ── file_function_summary ─────────────────────────────────────────────────
    elif strategy == "file_function_summary":
        fn_count = data.get("fn_count", 0)
        history  = data.get("history", [])
        filename = data.get("filename", "")
        parts.append(f"## 📊 `{filename}` Overview\n\n")
        parts.append(f"**Functions defined:** {fn_count}\n\n")
        if history:
            parts.append(f"**Last modified by:** {history[0]['author']} on {history[0]['date'][:10]}\n\n")
            parts.append(f"**Last commit:** {history[0]['message'][:60]}\n")
        sources.append(f"Neo4j: {filename}")
        return "".join(parts), sources, 0.90

    # ── commit_line_stats ─────────────────────────────────────────────────────
    elif strategy == "commit_line_stats":
        stats = data.get("stats", {})
        n = data.get("n", 50)
        if stats and "total_additions" in stats:
            parts.append(f"## 📊 Line Stats: Last {stats['commits_analyzed']} Commits\n\n")
            parts.append(f"- **Total additions:** +{stats['total_additions']:,}\n")
            parts.append(f"- **Total deletions:** -{stats['total_deletions']:,}\n")
            sources.append("GitHub API")
            return "".join(parts), sources, 0.90
        return None, [], 0.0

    return None, [], 0.0