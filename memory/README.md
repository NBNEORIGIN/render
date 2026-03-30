# Render project memory

Hybrid **BM25 + cosine similarity** search over project development history.

Memory files live in `memories/*.md` and are committed to git.
The SQLite vector DB (`render_memory.db`) is gitignored and rebuilt locally.

## Quick start

```bash
cd D:\render\memory

# Install deps (one-time)
pip install rank-bm25 numpy openai python-dotenv

# Search
python search.py "how does authentication work"
python search.py "deployment docker" -k 3
python search.py "blanks system" --body        # print full body

# List all memories
python search.py --list

# Add a new memory (interactive)
python ingest.py

# Add a memory (scripted)
python ingest.py --title "My decision" --tags "auth db" --file notes.md

# Re-embed everything (after editing memory files)
python store.py --rebuild
```

## Memory file format

```markdown
# Title of the memory
Tags: space separated tags
Date: YYYY-MM-DD

Body text — as much or as little as needed.
Markdown is fine.
```

## How it works

1. **BM25** (keyword) scores each memory against the query tokens
2. **Cosine similarity** (semantic) scores using OpenAI `text-embedding-3-small` embeddings
3. Both scores are normalised to [0, 1] then combined: `0.5 * bm25 + 0.5 * cosine`
4. Top-k results returned sorted by combined score

Adjust `--alpha` to weight BM25 vs cosine (0 = pure cosine, 1 = pure BM25).

## Adding memories from Claude sessions

After each significant session, create a new memory file:

```bash
python ingest.py --title "Session YYYY-MM-DD" --tags "session history"
# paste the session summary, end with ---
```

Or write the file directly to `memories/NNN_slug.md` and run `python store.py`.
