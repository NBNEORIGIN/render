"""
Render project memory search — CLI.

Usage:
    python search.py <query>
    python search.py "how does authentication work"
    python search.py --list          # list all indexed memories
    python search.py --rebuild       # re-embed everything then search

Options:
    -k N        Return top N results (default: 5)
    --alpha F   BM25 weight 0-1 (default: 0.5, balanced)
    --body      Print full body of each result
"""
import sys
from store import MemoryStore

USAGE = "Usage: python search.py <query>  [-k N] [--alpha F] [--body] [--rebuild] [--list]"


def main():
    args = sys.argv[1:]
    if not args:
        print(USAGE)
        return

    list_mode   = "--list"    in args
    rebuild     = "--rebuild" in args
    show_body   = "--body"    in args
    k           = 5
    alpha       = 0.5
    query_parts = []

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--list", "--rebuild", "--body"):
            pass
        elif a == "-k" and i + 1 < len(args):
            k = int(args[i + 1]); i += 1
        elif a == "--alpha" and i + 1 < len(args):
            alpha = float(args[i + 1]); i += 1
        else:
            query_parts.append(a)
        i += 1

    store = MemoryStore()

    if rebuild:
        print("Rebuilding index…")
        store.ingest(force=True)

    if list_mode:
        memories = store.list_all()
        print(f"{len(memories)} memories:\n")
        for m in memories:
            print(f"  [{m['id']:03d}] {m['title']}")
            print(f"        {m['file']}  |  indexed {m['indexed_at']}")
        store.close()
        return

    # Auto-sync any new files that aren't in the DB yet
    store.ingest(force=False)

    query = " ".join(query_parts)
    if not query:
        print(USAGE)
        store.close()
        return

    print(f'\nSearching: "{query}"  (k={k}, alpha={alpha})\n')
    results = store.search(query, k=k, alpha=alpha)

    if not results:
        print("No results found. Try --rebuild if you've added new memory files.")
        store.close()
        return

    for r in results:
        bar = "█" * int(r["score"] * 20)
        print(f"[{r['score']:.3f}] {bar}")
        print(f"  {r['title']}")
        print(f"  {r['file']}  |  bm25={r['bm25']:.3f}  cosine={r['cosine']:.4f}")
        if show_body:
            print()
            print(r["body"])
        else:
            # Print first 300 chars of body
            preview = r["body"].replace("\n", " ")[:300]
            print(f"  {preview}…" if len(r["body"]) > 300 else f"  {preview}")
        print()

    store.close()


if __name__ == "__main__":
    main()
