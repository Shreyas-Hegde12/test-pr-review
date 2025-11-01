import os
from pathlib import Path
from tree_sitter import Language, Parser

# Load languages once
LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "javascript",
    ".go": "go",
}
Language.build_library('build/languages.so', ['tree-sitter-python', 'tree-sitter-javascript', 'tree-sitter-go'])
PY = Language('build/languages.so', 'python')
JS = Language('build/languages.so', 'javascript')
GO = Language('build/languages.so', 'go')

def get_parser(ext):
    name = LANG_MAP.get(ext)
    if not name: return None
    return Parser(), getattr(globals()[name.upper()], None)

class DepGraph:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.imports = {}      # file → set(imported_paths)
        self.calls   = {}      # file → set(function_names)

    def _rel_path(self, p: Path) -> str:
        return str(p.relative_to(self.repo_root))

    def build(self):
        for path in self.repo_root.rglob("*"):
            if path.suffix not in LANG_MAP: continue
            parser, lang = get_parser(path.suffix)
            if not parser: continue
            parser.set_language(lang)
            with open(path, "rb") as f:
                tree = parser.parse(f.read())
            self._extract_imports(path, tree)
            self._extract_calls(path, tree)

    # ------------------------------------------------------------------
    # Language-specific extractors (Python example – add JS/Go similarly)
    # ------------------------------------------------------------------
    def _extract_imports(self, path: Path, tree):
        # Simplified: capture "import X" and "from X import Y"
        query = PY.query("""
        (import_statement name: (dotted_name) @imp)
        (import_from_statement module_name: (dotted_name) @imp)
        """)
        caps = query.captures(tree.root_node)
        imports = {c.node.text.decode() for _, c in caps}
        rel = self._rel_path(path)
        self.imports[rel] = imports

    def _extract_calls(self, path: Path, tree):
        # Capture function calls
        query = PY.query("(call function: (identifier) @call)")
        caps = query.captures(tree.root_node)
        calls = {c.node.text.decode() for _, c in caps}
        rel = self._rel_path(path)
        self.calls[rel] = calls

    # ------------------------------------------------------------------
    def dependents_of(self, files: set[str], depth: int = 1) -> set[str]:
        """Return files that import or call anything from `files` (recursive)."""
        result = set(files)
        for _ in range(depth):
            added = set()
            for f in result:
                for importer, imports in self.imports.items():
                    if any(imp.split('.')[0] in {p.split('.')[0] for p in result} for imp in imports):
                        added.add(importer)
                # call-based edges would be similar
            result.update(added)
        return result