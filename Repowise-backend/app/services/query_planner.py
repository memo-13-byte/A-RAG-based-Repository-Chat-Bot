"""
Query Planner
Intent + Entity → Execution Strategy

Keyword hardcoding'i tamamen kaldırır.
Yeni bir soru tipi eklemek için sadece STRATEGY_MAP'e satır ekle.
"""

import logging

logger = logging.getLogger(__name__)

# ── STRATEGY MAP ─────────────────────────────────────────────────────────────
# (intent, action, has_file, metric) → strategy
# None = "umursamıyorum"
# Önce daha spesifik key'ler gelir, fallback sonra

STRATEGY_MAP = [
    # ── STRUCTURAL ───────────────────────────────────────────────────────────
    (("semantic",   "structured",   False, None), "module_overview"),
    (("semantic",   "organized",    False, None), "module_overview"),
    # Circular imports → RAG
    (("structural", "circular",     False, None), "rag_search"),
    (("structural", "circular",     True,  None), "rag_search"),
    (("semantic",   "circular",     False, None), "rag_search"),
    # External libraries
    (("structural", "imports",      False, None), "external_libraries"),
    (("structural", "importing",    False, None), "external_libraries"),
    (("metadata",   "imports",      False, None), "external_libraries"),
    # Dosya bağımlılıkları
    (("structural", "imports",      True,  None), "file_importers"),
    (("structural", "import_from",  True,  None), "file_importers"),
    (("structural", "importing",    True,  None), "file_importers"),
    # depend_on + metric=classes → compound (genel kuraldan ÖNCE gelmeli)
    (("structural", "depend_on",    True,  "classes"),      "file_importers_classes"),
    (("structural", "depends_on",   True,  "classes"),      "file_importers_classes"),
    (("structural", "depends",      True,  "classes"),      "file_importers_classes"),
    (("structural", "depends_on",   True,  None), "file_importers"),
    (("structural", "depend_on",    True,  None), "file_importers"),
    (("structural", "depends",      True,  None), "file_importers"),

    # Compound: functions + history (ÖNCE gelmeli)
    (("structural", "modified",     True,  "functions"), "file_functions_and_history"),
    (("structural", "changed",      True,  "functions"), "file_functions_and_history"),
    # Recent changes + defines compound
    (("structural", "changed",      True,  None), "file_recent_and_defines"),
    # __init__.py exports özel case
    (("structural", "exports",      True,  None), "init_exports"),
    (("structural", "exported",     True,  None), "init_exports"),
    # Dosya tanımları — functions only (action=None ama metric=functions + file var)
    (("structural", None,           True,  "functions"), "file_functions_only"),
    (("structural", "defines",      True,  "functions"), "file_functions_only"),
    (("structural", "define",       True,  "functions"), "file_functions_only"),
    # Dosya tanımları
    (("structural", "defines",      True,  None), "file_defines"),
    (("structural", "define",       True,  None), "file_defines"),
    (("structural", "exports",      True,  None), "file_defines"),
    (("structural", "exported",     True,  None), "file_defines"),

    # Genel dosya analizi (hem defines hem imports)
    (("structural", "overview",     True,  None), "file_overview"),
    (("structural", "overview",     False, None), "module_overview"),
    (("structural", "organized",    False, None), "module_overview"),
    (("structural", "structured",   False, None), "module_overview"),

    # Sınıf hiyerarşisi
    (("structural", "hierarchy",    False, None), "class_hierarchy"),
    (("structural", "inherits",     False, None), "class_hierarchy"),
    (("structural", "inherit",      False, None), "class_hierarchy"),

    # Genel structural → dosya analizi
    (("structural", None,           True,  None), "file_overview"),
    (("structural", None,           False, None), "module_overview"),

    # ── ANALYTICS ────────────────────────────────────────────────────────────
    # Dosya bazlı contributor
    (("analytics",  "changed",      True,  None), "file_history"),
    (("analytics",  "modified",     False, None), "file_contributors"),
    (("analytics",  None,           True,  "contributors"), "file_contributors"),
    (("analytics",  None,           True,  "contributor"),  "file_contributors"),

    # Compound: function count + last modified
    (("analytics",  None,           True,  "functions"), "file_function_summary"),

    # Dosya geçmişi
    (("analytics",  "history",      True,  None), "file_history"),
    (("analytics",  "modified",     True,  None), "file_history"),
    (("analytics",  None, False, "lines_added"),            "contributor_lines"),
    (("analytics",  None, False, "lines_added_and_deleted"), "commit_line_stats"),
    (("analytics",  None, False, "additions"),              "contributor_lines"),
    (("analytics",  None, False, "contributors"),           "top_contributors"),
    (("analytics",  None, False, "contributor"),            "top_contributors"),

    # Sık değişen dosyalar
    (("analytics",  None, False, "hot_spots"),              "hotspot_files"),
    (("analytics",  None, False, "hot_spot"),               "hotspot_files"),
    (("analytics",  None, True,  None),                     "file_history"),

    # ── METADATA ─────────────────────────────────────────────────────────────
    (("metadata",   None, False, "complexity"),             "complexity"),
    (("metadata",   None, False, "most_complex"),           "complexity"),
    (("hybrid",     None, False, "complexity"),             "complexity"),
    (("hybrid",     None, False, "most_complex"),           "complexity"),
    (("structural", None, False, "complexity"),             "complexity"),
    (("semantic",   None, False, "complexity"),             "complexity"),
    (("semantic",   None, False, "most_complex"),           "complexity"),
    # depend_on + metric=classes → compound
    (("structural", "depend_on",    True,  "classes"),      "file_importers_classes"),
    (("structural", "depends_on",   True,  "classes"),      "file_importers_classes"),
    (("structural", "depends",      True,  "classes"),      "file_importers_classes"),
    (("metadata",   None, False, "commit_count"),           "repo_commits"),
    (("metadata",   None, False, "number_of_commits"),      "repo_commits"),
    (("metadata",   None, False, "how_many_commits"),       "repo_commits"),
    (("metadata",   None, False, "python_files"),           "repo_python_files"),
    (("metadata",   None, False, "functions"),              "repo_function_count"),
    (("metadata",   None, False, "classes"),                "repo_class_count"),
    # structural intent ile de class/function count (dosya yok)
    (("structural", None, False,  "classes"),               "repo_class_count"),
    (("structural", None, False,  "functions"),             "repo_function_count"),
    (("metadata",   None, False, "contributors"),           "top_contributors"),
    (("metadata",   None, False, "contributor"),            "top_contributors"),
    (("metadata",   None, False, "lines_added"),            "contributor_lines"),
    (("metadata",   None, False, "additions"),              "contributor_lines"),
    (("metadata",   None, False, "lines_added_and_deleted"), "commit_line_stats"),
    (("metadata",   None, True,  None),                     "file_overview"),

    # ── HYBRID ───────────────────────────────────────────────────────────────
    (("hybrid",     "depends_on",   True,  None), "file_importers_classes"),
    (("hybrid",     "depends",      True,  None), "file_importers_classes"),
    (("hybrid",     "imports",      True,  None), "file_importers_classes"),
    # recent changes + file defines
    (("hybrid",     "changed",      True,  None), "file_recent_and_defines"),
    (("structural", "changed",      True,  None), "file_recent_and_defines"),
    # functions + history compound
    (("structural", "modified",     True,  "functions"), "file_functions_and_history"),
    (("hybrid",     "modified",     True,  "functions"), "file_functions_and_history"),
    (("hybrid",     "history",      True,  None), "file_history_rag"),
    (("hybrid",     "modified",     True,  None), "file_history_rag"),
    (("hybrid",     "changed",      True,  None), "file_history_rag"),
    (("hybrid",     "overview",     True,  None), "file_overview_rag"),
    (("hybrid",     None,           True,  None), "file_overview_rag"),
    (("hybrid",     None,           False, None), "rag_search"),

    # ── COMMIT ───────────────────────────────────────────────────────────────
    (("commit",     "history",      False, None), "recent_commits"),
    (("commit",     "modified",     False, None), "recent_commits"),
    (("commit",     "changed",      False, None), "recent_commits"),
    (("commit",     None,           False, None), "recent_commits"),
]

# Timeframe'e özel overrides (timeframe varsa öncelik kazanır)
TIMEFRAME_OVERRIDES = {
    "most_actively_modified": "hotspot_files",
    "most_frequently":        "hotspot_files",
    "over_time":              "file_history",
}

# Intent'e göre son fallback
INTENT_FALLBACK = {
    "structural": "rag_search",
    "analytics":  "rag_search",
    "metadata":   "rag_search",
    "hybrid":     "rag_search",
    "semantic":   "rag_search",
    "commit":     "recent_commits",
}


def plan(intent: str, entities: dict) -> str:
    """
    Intent + entity → execution strategy

    Args:
        intent: "structural" | "analytics" | "metadata" | "hybrid" | "semantic" | "commit"
        entities: EntityExtractor.extract() çıktısı

    Returns:
        Strategy string — query_executor.execute() buna bakarak doğru query'i çalıştırır
    """
    action    = entities.get("action")
    metric    = entities.get("metric", "").replace(" ", "_") if entities.get("metric") else None
    timeframe = entities.get("timeframe", "").replace(" ", "_") if entities.get("timeframe") else None
    has_file  = entities.get("file") is not None

    # Timeframe override
    if timeframe and timeframe in TIMEFRAME_OVERRIDES:
        strategy = TIMEFRAME_OVERRIDES[timeframe]
        logger.debug("[QueryPlanner] timeframe override → %s", strategy)
        return strategy

    # Commit line stats: "last N commits" + lines
    if entities.get("n") and metric and "line" in metric:
        logger.debug("[QueryPlanner] commit_line_stats (n=%d)", entities["n"])
        return "commit_line_stats"

    # Recent commits: timeframe + no file
    if timeframe and not has_file and intent in ("analytics", "commit", "metadata"):
        if "last" in timeframe or "recent" in timeframe or "latest" in timeframe:
            logger.debug("[QueryPlanner] recent_commits")
            return "recent_commits"

    # Strategy map lookup
    for (key_intent, key_action, key_has_file, key_metric), strategy in STRATEGY_MAP:
        intent_ok  = (key_intent == intent)
        action_ok  = (key_action is None) or (action == key_action)
        file_ok    = (key_has_file == has_file)
        metric_ok  = (key_metric is None) or (metric == key_metric)

        if intent_ok and action_ok and file_ok and metric_ok:
            logger.debug("[QueryPlanner] (%s, %s, %s, %s) → %s",
                         intent, action, has_file, metric, strategy)
            return strategy

    # Fallback
    fallback = INTENT_FALLBACK.get(intent, "rag_search")
    logger.debug("[QueryPlanner] fallback → %s", fallback)
    return fallback