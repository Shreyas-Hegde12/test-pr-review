import os
import json
import openai
from github import Github
from pathlib import Path
import subprocess
from src.graph import DepGraph
# ADD: Dummy import to test dependency graph functionality.
# Ensure a file named 'src/utils.py' is created in your PR for this test.
import utils 

event_path = os.getenv("GITHUB_EVENT_PATH")
repo_name = os.getenv("GITHUB_REPOSITORY")
token = os.getenv("GITHUB_TOKEN")
# ... (rest of the file) ...

comments = []

for file in pull.get_files():
    filename = file.filename
    if not filename.endswith((".py", ".js", ".go", ".ts")):
        continue

    # MODIFIED BLOCK: Fetch dependencies and snippets for context
    dependency_snippets = graph.get_dependencies_with_snippets(filename)
    
    # Format the dictionary of snippets into a string for the prompt
    formatted_deps = ""
    if dependency_snippets:
        formatted_deps = "\n\n--- Relevant Dependency Context ---\n"
        for dep_file, snippet in dependency_snippets.items():
            formatted_deps += f"\nFile: `{dep_file}`\n---\n{snippet}\n---\n"

    patch = file.patch or ""
    if not patch.strip():
        continue

    # Pass the formatted string (formatted_deps) to the review function
    review = call_ai_review(filename, patch, formatted_deps)
    comments.append((filename, review))

body = "\n\n".join([f"### `{f}`\n{r}" for f, r in comments])
pull.create_issue_comment(f"🤖 **AI Review Summary**\n\n{body}")
