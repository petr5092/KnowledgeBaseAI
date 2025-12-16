from src.core.math import w_edge, ema

def test_w_edge_clip_bounds():
    assert w_edge(100, 100, 100, 0.0) == 10.0
    assert w_edge(0, 0, 0, 1.0) == 0.1

def test_ema_stability():
    prev = 0.5
    v = 0.7
    e = ema(prev, v, 0.3)
    assert 0.5 < e < 0.7
