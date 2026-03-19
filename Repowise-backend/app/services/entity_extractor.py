"""
Entity Extractor — spaCy SpanRuler tabanlı
Keyword hardcoding yerine NLP ile entity çıkarımı yapar.

Çıkardığı entity'ler:
  file      → sessions.py, models.py gibi dosya adları
  action    → imports, defines, exports, depends_on, hierarchy, history, modified
  metric    → lines_added, commit_count, functions, classes, hot_spots, complexity
  timeframe → recent, last_N, over_time, actively_modified
  n         → "last 50 commits" → 50
"""

import re
import logging

logger = logging.getLogger(__name__)

# Singleton — bir kez yükle
_extractor = None


class EntityExtractor:
    def __init__(self):
        try:
            import spacy
            # POS + dependency yeterli, ner/lemmatizer'a gerek yok
            self.nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
        except OSError:
            # Model yoksa blank pipeline kullan
            import spacy
            self.nlp = spacy.blank("en")
            logger.warning("en_core_web_sm bulunamadı, blank pipeline kullanılıyor")

        ruler = self.nlp.add_pipe("span_ruler", config={"spans_key": "sc"})

        patterns = [
            # ── FILE ──────────────────────────────────────────────
            {"label": "FILE", "pattern": [{"TEXT": {"REGEX": r"[\w\-]+\.py"}}]},

            # ── ACTION ────────────────────────────────────────────
            {"label": "ACTION", "pattern": [{"LOWER": "imports"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "import"}, {"LOWER": "from"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "importing"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "defines"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "define"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "exports"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "exported"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "depends"}, {"LOWER": "on"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "depend"}, {"LOWER": "on"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "depends"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "hierarchy"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "inherits"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "inherit"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "history"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "modified"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "changed"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "organized"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "structured"}]},
            {"label": "ACTION", "pattern": [{"LOWER": "overview"}]},

            # ── METRIC ────────────────────────────────────────────
            {"label": "METRIC", "pattern": [{"LOWER": "lines"}, {"LOWER": "added"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "lines"}, {"LOWER": "added"}, {"LOWER": "and"}, {"LOWER": "deleted"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "additions"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "commit"}, {"LOWER": "count"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "number"}, {"LOWER": "of"}, {"LOWER": "commits"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "how"}, {"LOWER": "many"}, {"LOWER": "commits"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "functions"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "classes"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "hot"}, {"LOWER": "spots"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "hot"}, {"LOWER": "spot"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "complexity"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "most"}, {"LOWER": "complex"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "python"}, {"LOWER": "files"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "contributors"}]},
            {"label": "METRIC", "pattern": [{"LOWER": "contributor"}]},

            # ── TIMEFRAME ─────────────────────────────────────────
            {"label": "TIMEFRAME", "pattern": [{"LOWER": "recent"}]},
            {"label": "TIMEFRAME", "pattern": [{"LOWER": "recently"}]},
            {"label": "TIMEFRAME", "pattern": [{"LOWER": "latest"}]},
            {"label": "TIMEFRAME", "pattern": [{"LOWER": "last"}, {"IS_DIGIT": True}, {"LOWER": {"IN": ["commits", "commit"]}}]},
            {"label": "TIMEFRAME", "pattern": [{"LOWER": "over"}, {"LOWER": "time"}]},
            {"label": "TIMEFRAME", "pattern": [{"LOWER": "most"}, {"LOWER": "actively"}, {"LOWER": "modified"}]},
            {"label": "TIMEFRAME", "pattern": [{"LOWER": "most"}, {"LOWER": "frequently"}]},
        ]

        ruler.add_patterns(patterns)
        logger.info("[EntityExtractor] ✅ Ready — %d patterns loaded", len(patterns))

    def extract(self, text: str) -> dict:
        """
        Sorudan entity'leri çıkar.

        Returns:
            {
                "file": "sessions.py" | None,
                "action": "imports" | "defines" | ... | None,
                "metric": "lines_added" | "functions" | ... | None,
                "timeframe": "recent" | "last_N" | "over_time" | None,
                "n": 50 | None,
            }
        """
        doc = self.nlp(text.lower())

        entities = {
            "file": None,
            "action": None,
            "metric": None,
            "timeframe": None,
            "n": None,
        }

        for span in doc.spans.get("sc", []):
            label = span.label_
            val = span.text.strip()

            if label == "FILE" and not entities["file"]:
                entities["file"] = val

            elif label == "ACTION" and not entities["action"]:
                # normalize: "import from" → "import_from"
                entities["action"] = val.replace(" ", "_")

            elif label == "METRIC" and not entities["metric"]:
                entities["metric"] = val.replace(" ", "_")

            elif label == "TIMEFRAME" and not entities["timeframe"]:
                entities["timeframe"] = val

                # "last N commits" → n
                n_match = re.search(r'last\s+(\d+)', val)
                if n_match:
                    entities["n"] = int(n_match.group(1))

        # Backup: __init__.py özel case — spaCy "init__.py" verir, düzelt
        if entities["file"] and entities["file"].endswith("init__.py"):
            entities["file"] = "__init__.py"
        elif not entities["file"]:
            if '__init__' in text.lower():
                entities["file"] = "__init__.py"

        # Backup: regex ile dosya adı yakala (spaCy tokenizer bazen böler)
        if not entities["file"]:
            file_match = re.search(r'([\w\-]+\.py)', text, re.IGNORECASE)
            if file_match:
                entities["file"] = file_match.group(1).lower()

        # Backup: "last N commits" regex
        if not entities["n"]:
            n_match = re.search(r'last\s+(\d+)\s+commits?', text, re.IGNORECASE)
            if n_match:
                entities["n"] = int(n_match.group(1))
                if not entities["timeframe"]:
                    entities["timeframe"] = f"last_{entities['n']}"

        # Backup: "circular imports" → RAG'a bırak (implement edilmemiş)
        if re.search(r'circular import', text, re.IGNORECASE):
            entities["action"] = "circular"

        # Backup: "what does X define and depend on / import" → action=overview
        if entities.get("file") and entities.get("action") in (None, "define", "defines"):
            if re.search(r'(define).+(depend|import)|(depend|import).+(define)', text, re.IGNORECASE):
                entities["action"] = "overview"

        # Backup: "external libraries / imports" (no file) → action=imports
        if not entities.get("file") and not entities.get("action"):
            if re.search(r'external.{0,10}(librar|import|depend)|what.{0,10}(librar|import).{0,20}(use|import)', text, re.IGNORECASE):
                entities["action"] = "imports"
        if not entities["timeframe"]:
            if re.search(r'modified the most|most modified|most frequently modified', text, re.IGNORECASE):
                entities["timeframe"] = "most_actively_modified"

        # Backup: "lines added / code contributed" → metric
        if not entities["metric"]:
            if re.search(r'lines added|code.*contribut|contribut.*code|most code', text, re.IGNORECASE):
                entities["metric"] = "lines_added"
        if not entities["metric"]:
            if re.search(r'how many classes|number of classes|total classes', text, re.IGNORECASE):
                entities["metric"] = "classes"
            elif re.search(r'how many functions|number of functions|total functions', text, re.IGNORECASE):
                entities["metric"] = "functions"
            elif re.search(r'how many commits|number of commits|total commits', text, re.IGNORECASE):
                entities["metric"] = "commit_count"
            elif re.search(r'how many files|number of files|total files|file count', text, re.IGNORECASE):
                entities["metric"] = "python_files"

        # Backup: "what X are defined / where are X defined" → file=X.py (dosya adı tahmin et)
        # Örnek: "exceptions defined in requests" → exceptions.py
        # Örnek: "errors defined in which file" → errors.py
        # Örnek: "handlers defined in flask" → handlers.py
        if not entities.get("file"):
            m = re.search(
                r'what\s+(\w+)\s+are\s+(?:defined|declared|located)'
                r'|where\s+(?:are\s+)?(\w+)\s+(?:defined|declared|located)'
                r'|(\w+)\s+(?:defined|declared)\s+in\s+which\s+file'
                r'|in\s+which\s+file\s+(?:are\s+)?(\w+)\s+(?:defined|declared)',
                text, re.IGNORECASE
            )
            if m:
                # İlk match eden grubu al
                concept = next(g for g in m.groups() if g)
                # Bilinen stop word'leri filtrele
                stop = {'the', 'a', 'an', 'they', 'these', 'those', 'it', 'file', 'files', 'module', 'library', 'repo'}
                if concept.lower() not in stop:
                    candidate = concept.lower() + ".py"
                    entities["file"] = candidate
                    if not entities.get("action"):
                        entities["action"] = "defines"

        logger.debug("[EntityExtractor] %s → %s", text[:60], entities)
        return entities


def get_extractor() -> EntityExtractor:
    """Singleton erişimi"""
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor