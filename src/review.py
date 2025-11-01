import os
import json
import textwrap
from pathlib import Path
from typing import List, Dict
import openai
from github import Github
from graph import DepGraph

openai.api_key = os.getenv("OPENAI_API_KEY")   # or set base_url for other providers

CONTEXT_LINES = 30          # lines before/after each hunk
MAX_TOKENS = 3500           # safe for gpt-4o-mini

# ------------------------------------------------------------------
def load_prompt() -> str:
    return (Path(__file__).parent / "prompt.txt").read_text()

PROMPT_TEMPLATE = load_prompt()

# ------------------------------------------------------------------
def get_diff_hunks(repo_path: Path) -> List[Dict]:
    import subprocess, re
    result = subprocess.run(
        ["git", "diff", "-U0", "HEAD^", "HEAD"],
        cwd=repo_path, capture_output=True, text=True, check=True
    )
    hunks = []
    current_file = None
    for line in result.stdout.splitlines():
        if line.startswith("diff --git"):
            current_file = line.split()[-1][2:]   # a/path/to/file.py
        elif line.startswith("@@"):
            m = re.search(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
            if not m: continue
            old_start, old_len, new_start, new_len = m.groups()
            old_start, new_start = int(old_start), int(new_start)
            old_len = int(old_len or 1)
            new_len = int(new_len or 1)
            hunks.append({
                "file": current_file,
                "new_start": new_start,
                "new_lines": new_len,
            })
    return hunks

# ------------------------------------------------------------------
def read_file_context(repo_path: Path, file: str, start: int, lines: int) -> str:
    path = repo_path / file
    if not path.exists(): return ""
    content = path.read_text().splitlines(keepends=True)
    before = max(0, start - CONTEXT_LINES - 1)
    after  = start + lines + CONTEXT_LINES
    return "".join(content[before:after])

# ------------------------------------------------------------------
def build_prompt(hunk: Dict, full_context: str, deps: set[str], dep_snippets: Dict[str,str]) -> str:
    dep_block = "\n".join(
        f"--- {f} ---\n{snippet}"
        for f, snippet in dep_snippets.items()
    )
    return PROMPT_TEMPLATE.format(
        file=hunk["file"],
        start=hunk["new_start"],
        code=full_context,
        deps=dep_block or "(none)",
    )

# ------------------------------------------------------------------
def call_llm(prompt: str) -> str:
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",      # change to claude-3.5-sonnet, etc.
        messages=[{"role": "system", "content": "You are a senior code reviewer."},
                  {"role": "user",   "content": prompt}],
        temperature=0.2,
        max_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content.strip()

# ------------------------------------------------------------------
def post_review(gh_repo, pr_number: int, reviews: List[Dict]):
    gh = Github(os.getenv("GITHUB_TOKEN"))
    repo = gh.get_repo(gh_repo)
    pull = repo.get_pull(pr_number)

    # Group by file → list of (line, comment)
    comments = {}
    for r in reviews:
        comments.setdefault(r["file"], []).append((r["line"], r["body"]))

    for file, items in comments.items():
        path = file
        body = "\n".join(f"**L{r[0]}**: {r[1]}" for r in items)
        pull.create_review_comment(body, commit=None, path=path, line=items[0][0])

    # Optional: top-level summary
    summary = "\n".join(f"- {r['summary']}" for r in reviews if "summary" in r)
    if summary:
        pull.create_issue_comment("## AI Review Summary\n" + summary)

# ------------------------------------------------------------------
def main():
    repo_path = Path(os.environ["GITHUB_WORKSPACE"])
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    pr_number = event["pull_request"]["number"]
    gh_repo = os.environ["GITHUB_REPOSITORY"]

    # 1. Build dependency graph (cached)
    graph_path = repo_path / ".ai_review_graph.json"
    graph = DepGraph(repo_path)
    if graph_path.exists():
        data = json.loads(graph_path.read_text())
        graph.imports = data["imports"]
        graph.calls   = data["calls"]
    else:
        graph.build()
        graph_path.write_text(json.dumps({"imports": graph.imports, "calls": graph.calls}))

    # 2. Get diff hunks
    hunks = get_diff_hunks(repo_path)

    reviews = []
    for hunk in hunks:
        file = hunk["file"]
        context = read_file_context(repo_path, file, hunk["new_start"], hunk["new_lines"])

        # 3. Find dependent files
        deps = graph.dependents_of({file}, depth=2) - {file}
        dep_snippets = {}
        for d in deps:
            dpath = repo_path / d
            if dpath.exists():
                snippet = dpath.read_text()
                if len(snippet) > 2000:
                    snippet = snippet[:1000] + "\n... (truncated) ...\n" + snippet[-1000:]
                dep_snippets[d] = snippet

        prompt = build_prompt(hunk, context, deps, dep_snippets)
        llm_out = call_llm(prompt)

        # Simple parsing of LLM output – expect:
        #   <comment line=X>…</comment>
        #   <summary>…</summary>
        import re
        comment = re.search(r"<comment line=(\d+)>(.*?)</comment>", llm_out, re.S)
        summary = re.search(r"<summary>(.*?)</summary>", llm_out, re.S)

        review = {
            "file": file,
            "line": int(comment.group(1)) if comment else hunk["new_start"],
            "body": (comment.group(2) if comment else llm_out).strip(),
        }
        if summary:
            review["summary"] = summary.group(1).strip()
        reviews.append(review)

    post_review(gh_repo, pr_number, reviews)

if __name__ == "__main__":
    main()