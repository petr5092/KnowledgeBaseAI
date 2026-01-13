import sys
from src.services.kb.builder import build_mathematics_ontology, enrich_all_topics
from src.services.kb.jsonl_io import normalize_kb
from src.services.graph.utils import sync_from_jsonl

def main() -> int:
    res1 = build_mathematics_ontology()
    res2 = enrich_all_topics()
    normalize_kb()
    res3 = sync_from_jsonl()
    ok = bool(res1.get("ok")) and bool(res2.get("ok")) and bool(res3.get("ok"))
    print({"ontology": res1, "enrich": res2, "import": res3})
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
