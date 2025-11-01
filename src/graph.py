import os
from pathlib import Path
from collections import defaultdict

class DepGraph:
# ... existing __init__ and _rel_path ...

    # ------------------------------
    def build(self):
        """
        Walk all Python files and extract imports and calls.
        Cache code content for snippet extraction.
        """
        # ADD: Debugging log to confirm graph construction start
        print(f"Starting to build dependency graph from {self.repo_root}...") 

        for path in self.repo_root.rglob("*.py"):
            rel_path = self._rel_path(path)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    self.code_cache[rel_path] = lines
            except Exception:
                continue
            # ... (rest of the logic for imports/calls) ...
            
            self.imports[rel_path] = imported_files
            self.calls[rel_path] = called_names

        # Build reverse import map
        for f, imps in self.imports.items():
            for imp in imps:
                # Basic check to map module name (e.g., 'utils') back to a relative file path (e.g., 'src/utils.py')
                # This helps ensure local file dependencies are tracked correctly.
                possible_file_path = str(self.repo_root / f"{imp}.py").replace(str(self.repo_root) + "/", "")
                if possible_file_path in self.code_cache:
                    self.reverse_imports[possible_file_path].add(f)
                else:
                    # Fallback for external modules
                    self.reverse_imports[imp].add(f)
        
        # ADD: Debugging log to confirm graph construction end and show size
        print(f"Dependency graph build complete. Tracked {len(self.code_cache)} files.") 
        # ADD: Print a sample dependency to check if the graph is populated
        print(f"Example reverse imports (files importing others): {dict(self.reverse_imports)}")


    # ------------------------------
    # ... (rest of the file) ...
