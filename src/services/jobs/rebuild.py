import threading
import time
from typing import Dict
from src.services.graph.utils import sync_from_jsonl, analyze_knowledge, compute_static_weights, add_prereqs_heuristic

_jobs: Dict[str, Dict] = {}

def _run_job(job_id: str):
    _jobs[job_id] = {"status": "running", "stages": []}
    try:
        _jobs[job_id]["stages"].append("import_jsonl")
        stats = sync_from_jsonl()
        _jobs[job_id]["sync_stats"] = stats
        _jobs[job_id]["stages"].append("compute_static_weights")
        sw = compute_static_weights()
        _jobs[job_id]["static_weights"] = sw
        _jobs[job_id]["stages"].append("add_prereqs_heuristic")
        pr = add_prereqs_heuristic()
        _jobs[job_id]["prereqs_added"] = pr
        _jobs[job_id]["stages"].append("analysis")
        metrics = analyze_knowledge()
        _jobs[job_id]["metrics"] = metrics
        warnings = []
        if metrics.get('topics_without_targets'):
            warnings.append('topics_without_targets')
        if metrics.get('skills_without_methods'):
            warnings.append('skills_without_methods')
        if metrics.get('orphan_sections'):
            warnings.append('orphan_sections')
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["ok"] = True
        _jobs[job_id]["warnings"] = warnings
    except Exception as e:
        _jobs[job_id] = {"status": "error", "error": str(e), "ok": False}

def start_rebuild_async() -> Dict:
    job_id = str(int(time.time() * 1000))
    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
    return {"job_id": job_id}

def get_job_status(job_id: str) -> Dict:
    return _jobs.get(job_id, {"status": "unknown"})

