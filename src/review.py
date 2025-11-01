import os
import json
import openai
from github import Github
from pathlib import Path
import subprocess
from src.graph import DepGraph

event_path = os.getenv("GITHUB_EVENT_PATH")
repo_name = os.getenv("GITHUB_REPOSITORY")
token = os.getenv("GITHUB_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

event = json.load(open(event_path))
pr_number = event["pull_request"]["number"]
head_sha = event["pull_request"]["head"]["sha"]

g = Github(token)
repo = g.get_repo(repo_name)
pull = repo.get_pull(pr_number)

# Fetch changed files with context
diff = subprocess.check_output(["git", "diff", "--unified=3", "origin/main...HEAD"], text=True)

graph = DepGraph("src")  # or root dir if needed

prompt_template = Path("src/prompt.txt").read_text()

def call_ai_review(file, code, deps):
    prompt = prompt_template.format(file=file, code=code, deps=deps)
    completion = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert code reviewer."},
            {"role": "user", "content": prompt}
        ]
    )
    return completion.choices[0].message["content"]

comments = []

for file in pull.get_files():
    filename = file.filename
    if not filename.endswith((".py", ".js", ".go", ".ts")):
        continue

    deps = graph.get_dependencies(filename)
    patch = file.patch or ""
    if not patch.strip():
        continue

    review = call_ai_review(filename, patch, deps)
    comments.append((filename, review))

body = "\n\n".join([f"### `{f}`\n{r}" for f, r in comments])
pull.create_issue_comment(f"🤖 **AI Review Summary**\n\n{body}")
