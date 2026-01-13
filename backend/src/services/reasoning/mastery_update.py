from typing import Dict

def update_mastery(prior_mastery: float, score: float, confidence: float | None = None) -> Dict:
    pm = max(0.0, min(1.0, float(prior_mastery)))
    sc = max(0.0, min(1.0, float(score)))
    conf = float(confidence) if confidence is not None else 0.7
    alpha = 0.4 * conf
    new_m = pm + alpha * (sc - pm)
    new_m = max(0.0, min(1.0, new_m))
    return {"new_mastery": new_m, "delta": new_m - pm, "confidence": conf}

