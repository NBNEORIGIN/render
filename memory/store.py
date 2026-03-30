"""
Render project memory store — hybrid BM25 + cosine similarity search.

Memories are markdown files in memory/memories/*.md
The SQLite DB (render_memory.db) is built from those files and gitignored.
Rebuild it any time by running: python store.py --rebuild

Requires: rank-bm25, numpy, openai, python-dotenv
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

MEMORY_DIR = Path(__file__).parent / "memories"
DB_PATH = Path(__file__).parent / "render_memory.db"
EMBED_MODEL = "text-embedding-3-small"


def _load_env():
    """Load .env from project root so OPENAI_API_KEY is available."""
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        pass


def _embed(text: str) -> np.ndarray:
    import openai
    _load_env()
    client = openai.OpenAI()
    resp = client.embeddings.create(model=EMBED_MODEL, input=text[:8000])
    return np.array(resp.data[0].embedding, dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def _parse_memory(path: Path) -> dict:
    """Parse a memory markdown file into {title, tags, body}."""
    text = path.read_text(encoding="utf-8").strip()
    lines = text.split("\n")
    title = lines[0].lstrip("#").strip() if lines else path.stem
    # Look for a Tags: line in the first 10 lines
    tags = path.stem.replace("_", " ")
    for line in lines[1:10]:
        if line.lower().startswith("tags:"):
            tags = line.split(":", 1)[1].strip()
            break
    return {"file": path.name, "title": title, "tags": tags, "body": text}


class MemoryStore:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id       INTEGER PRIMARY KEY,
                file     TEXT UNIQUE NOT NULL,
                title    TEXT,
                tags     TEXT,
                body     TEXT,
                embedding BLOB,
                indexed_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self.conn.commit()

    def _needs_index(self, file_name: str, mtime: float) -> bool:
        row = self.conn.execute(
            "SELECT indexed_at FROM memories WHERE file=?", (file_name,)
        ).fetchone()
        if not row:
            return True
        # Re-index if file is newer than what's stored (rough check)
        return False  # mtime comparison left to --rebuild flag

    def ingest(self, force: bool = False):
        """Ingest / update all markdown files from memories/."""
        MEMORY_DIR.mkdir(exist_ok=True)
        files = sorted(MEMORY_DIR.glob("*.md"))
        if not files:
            print("No memory files found in", MEMORY_DIR)
            return

        for f in files:
            exists = self.conn.execute(
                "SELECT id FROM memories WHERE file=?", (f.name,)
            ).fetchone()
            if exists and not force:
                continue

            print(f"  Indexing {f.name}…", end=" ", flush=True)
            m = _parse_memory(f)
            emb = _embed(m["body"])

            if exists:
                self.conn.execute(
                    "UPDATE memories SET title=?, tags=?, body=?, embedding=?, indexed_at=datetime('now') WHERE file=?",
                    (m["title"], m["tags"], m["body"], emb.tobytes(), f.name),
                )
            else:
                self.conn.execute(
                    "INSERT INTO memories (file, title, tags, body, embedding) VALUES (?,?,?,?,?)",
                    (f.name, m["title"], m["tags"], m["body"], emb.tobytes()),
                )
            self.conn.commit()
            print("done")

    def search(self, query: str, k: int = 5, alpha: float = 0.5) -> list[dict]:
        """
        Hybrid search: alpha * BM25 + (1-alpha) * cosine similarity.
        Returns up to k results sorted by combined score descending.
        """
        rows = self.conn.execute(
            "SELECT id, file, title, body, embedding FROM memories"
        ).fetchall()
        if not rows:
            return []

        ids, files, titles, bodies, emb_blobs = zip(*rows)

        # BM25
        tokenized = [b.lower().split() for b in bodies]
        bm25 = BM25Okapi(tokenized)
        bm25_scores = np.array(bm25.get_scores(query.lower().split()), dtype=np.float64)

        # Cosine similarity
        query_emb = _embed(query)
        embeddings = np.array(
            [np.frombuffer(e, dtype=np.float32) for e in emb_blobs]
        )
        norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_emb) + 1e-8
        cosine_scores = (embeddings @ query_emb) / norms

        # Normalise both to [0, 1] then combine
        def _norm(arr):
            lo, hi = arr.min(), arr.max()
            return (arr - lo) / (hi - lo + 1e-8)

        combined = alpha * _norm(bm25_scores) + (1 - alpha) * _norm(cosine_scores)
        top_k_idx = np.argsort(combined)[::-1][:k]

        return [
            {
                "id": ids[i],
                "file": files[i],
                "title": titles[i],
                "body": bodies[i],
                "score": float(combined[i]),
                "bm25": float(bm25_scores[i]),
                "cosine": float(cosine_scores[i]),
            }
            for i in top_k_idx
        ]

    def list_all(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, file, title, tags, indexed_at FROM memories ORDER BY id"
        ).fetchall()
        return [
            {"id": r[0], "file": r[1], "title": r[2], "tags": r[3], "indexed_at": r[4]}
            for r in rows
        ]

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv
    print(f"{'Re-indexing' if rebuild else 'Syncing'} memory store…")
    store = MemoryStore()
    store.ingest(force=rebuild)
    memories = store.list_all()
    print(f"\n{len(memories)} memories indexed:")
    for m in memories:
        print(f"  [{m['id']:03d}] {m['title']}  ({m['file']})")
    store.close()
