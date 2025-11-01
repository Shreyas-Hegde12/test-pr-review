import os
from pathlib import Path
from collections import defaultdict

class DepGraph:
    """
    Improved dependency graph:
    - Tracks imports and reverse imports
    - Tracks function and class calls
    - Provides code snippets from dependent files for AI context
    """

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.imports = defaultdict(set)       # file -> imported modules/files
        self.reverse_imports = defaultdict(set)  # file -> files importing it
        self.calls = defaultdict(set)         # file -> functions or classes called
        self.code_cache = {}                  # file -> file content lines
        self.build()

    # ------------------------------
    def _rel_path(self, path: Path) -> str:
        return str(path.relative_to(self.repo_root))

    # ------------------------------
    def build(self):
        """
        Walk all Python files and extract imports and calls.
        Cache code content for snippet extraction.
        """
        for path in self.repo_root.rglob("*.py"):
            rel_path = self._rel_path(path)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    self.code_cache[rel_path] = lines
            except Exception:
                continue

            imported_files = set()
            called_names = set()

            for line in lines:
                line_strip = line.strip()
                # Simple import detection
                if line_strip.startswith("import "):
                    for part in line_strip[len("import "):].split(","):
                        imported_files.add(part.strip().split(".")[0])
                elif line_strip.startswith("from "):
                    parts = line_strip.split()
                    if len(parts) >= 4:
                        module = parts[1].split(".")[0]
                        imported_files.add(module)

                # Simple function/class call detection
                if "(" in line_strip and ")" in line_strip and not line_strip.startswith("#"):
                    name = line_strip.split("(")[0].strip()
                    if name.isidentifier():
                        called_names.add(name)
                elif line_strip.startswith("class "):
                    name = line_strip.split()[1].split("(")[0]
                    called_names.add(name)
                elif line_strip.startswith("def "):
                    name = line_strip.split()[1].split("(")[0]
                    called_names.add(name)

            self.imports[rel_path] = imported_files
            self.calls[rel_path] = called_names

        # Build reverse import map
        for f, imps in self.imports.items():
            for imp in imps:
                self.reverse_imports[imp].add(f)

    # ------------------------------
    def dependents_of(self, files: set[str], depth: int = 2) -> set[str]:
        """
        Return files that are:
        - Imported by given files
        - Or import given files (reverse)
        Recursively up to 'depth'.
        """
        result = set(files)
        for _ in range(depth):
            new = set()
            for f in result:
                if f in self.imports:
                    new.update(self.imports[f])
                if f in self.reverse_imports:
                    new.update(self.reverse_imports[f])
            result.update(new)
        return result

    # ------------------------------
    def get_dependencies_with_snippets(self, file: str, depth: int = 2, max_lines=50) -> dict[str,str]:
        """
        Return a dict: {dep_file: snippet_str} for AI context
        - Includes dependent files (import or reverse import)
        - Takes up to max_lines from start and end of file if too long
        """
        deps = self.dependents_of({file}, depth)
        deps.discard(file)
        snippets = {}
        for d in deps:
            lines = self.code_cache.get(d, [])
            if not lines:
                continue
            if len(lines) > max_lines:
                snippet = "".join(lines[:max_lines//2] + ["\n... (truncated) ...\n"] + lines[-max_lines//2:])
            else:
                snippet = "".join(lines)
            snippets[d] = snippet
        return snippets
