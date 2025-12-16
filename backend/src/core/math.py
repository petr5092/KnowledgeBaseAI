def clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def w_edge(w_static: float, g_diff: float, decay: float, u_conf: float, lo: float = 0.1, hi: float = 10.0) -> float:
    return clip((w_static * g_diff) * (1.0 + decay * (1.0 - u_conf)), lo, hi)

def ema(prev: float, value: float, alpha: float = 0.3) -> float:
    return alpha * value + (1.0 - alpha) * prev
