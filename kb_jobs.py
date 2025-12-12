import threading
import time
from typing import Dict

from neo4j_utils import sync_from_jsonl, analyze_knowledge

_jobs: Dict[str, Dict] = {}


def _run_job(job_id: str):
    _jobs[job_id] = {"status": "running"}
    try:
        stats = sync_from_jsonl()
        metrics = analyze_knowledge()
        _jobs[job_id] = {"status": "done", "stats": stats, "metrics": metrics}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "error": str(e)}


def start_rebuild_async() -> Dict:
    job_id = str(int(time.time() * 1000))
    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
    return {"job_id": job_id}


def get_job_status(job_id: str) -> Dict:
    return _jobs.get(job_id, {"status": "unknown"})

