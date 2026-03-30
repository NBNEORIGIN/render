"""
Add a new memory to the Render project memory store.

Usage (interactive):
    python ingest.py

Usage (piped / scripted):
    python ingest.py --title "Title" --tags "tag1 tag2" --file path/to/content.md
    echo "Body text" | python ingest.py --title "My memory" --tags "auth"

The memory is saved as a numbered markdown file in memory/memories/
and immediately embedded into the vector DB.
"""
import sys
import re
from datetime import datetime
from pathlib import Path
from store import MemoryStore, MEMORY_DIR

MEMORY_DIR.mkdir(exist_ok=True)


def _next_filename() -> str:
    existing = sorted(MEMORY_DIR.glob("*.md"))
    if not existing:
        return "001_memory.md"
    last = existing[-1].stem
    m = re.match(r"^(\d+)", last)
    n = int(m.group(1)) + 1 if m else len(existing) + 1
    return f"{n:03d}_memory.md"


def _slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug[:40]


def _interactive() -> dict:
    print("=== Add memory to Render project ===\n")
    title = input("Title: ").strip()
    if not title:
        print("Title required.")
        sys.exit(1)
    tags = input("Tags (space separated, optional): ").strip()
    print("Body (paste content, end with a line containing only '---'):")
    lines = []
    while True:
        line = input()
        if line.strip() == "---":
            break
        lines.append(line)
    body = "\n".join(lines).strip()
    if not body:
        print("Body required.")
        sys.exit(1)
    return {"title": title, "tags": tags, "body": body}


def main():
    args = sys.argv[1:]
    title = None
    tags = ""
    source_file = None

    i = 0
    while i < len(args):
        if args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]; i += 2
        elif args[i] == "--tags" and i + 1 < len(args):
            tags = args[i + 1]; i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            source_file = Path(args[i + 1]); i += 2
        else:
            i += 1

    if not sys.stdin.isatty() or (title and source_file):
        # Scripted / piped mode
        if not title:
            print("--title required in scripted mode")
            sys.exit(1)
        if source_file:
            body = source_file.read_text(encoding="utf-8").strip()
        else:
            body = sys.stdin.read().strip()
    elif title and not source_file:
        # Partial scripted — title given, prompt for body
        print(f"Title: {title}")
        print("Body (end with '---'):")
        lines = []
        while True:
            line = input()
            if line.strip() == "---":
                break
            lines.append(line)
        body = "\n".join(lines).strip()
    else:
        data = _interactive()
        title = data["title"]
        tags = data["tags"]
        body = data["body"]

    # Build the memory file
    slug = _slugify(title)
    existing = sorted(MEMORY_DIR.glob("*.md"))
    n = len(existing) + 1
    filename = f"{n:03d}_{slug}.md"
    date = datetime.now().strftime("%Y-%m-%d")

    content = f"# {title}\n"
    if tags:
        content += f"Tags: {tags}\n"
    content += f"Date: {date}\n\n{body}\n"

    dest = MEMORY_DIR / filename
    dest.write_text(content, encoding="utf-8")
    print(f"Saved: {dest}")

    # Embed and index
    print("Embedding and indexing…")
    store = MemoryStore()
    store.ingest(force=False)
    store.close()
    print("Done.")


if __name__ == "__main__":
    main()
