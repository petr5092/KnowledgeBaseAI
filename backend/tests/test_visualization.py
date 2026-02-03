import pytest
from app.services.visualization.geometry import GeometryEngine

def test_normalization_bounds():
    shapes = [
        {"points": [{"x": 15, "y": 20}, {"x": -5, "y": 0}]}
    ]
    normalized = GeometryEngine.normalize(shapes)
    for shape in normalized:
        for p in shape["points"]:
            assert 0 <= p["x"] <= 10.1
            assert 0 <= p["y"] <= 10.1

def test_centering():
    # Создаем фигуру со смещенным центром
    # Original centroid: (1, 0.33)
    shapes = [{"points": [{"x": 0, "y": 0}, {"x": 2, "y": 0}, {"x": 1, "y": 1}]}]
    normalized = GeometryEngine.normalize(shapes)
    
    # Вычисляем новый центроид
    cx = sum(p["x"] for p in normalized[0]["points"]) / 3
    cy = sum(p["y"] for p in normalized[0]["points"]) / 3
    
    assert abs(cx - 5.0) < 0.1
    # Note: cy is not necessarily 5.0 for the centroid of points if the bounding box center is used.
    # The normalizer centers the bounding box at 5,5.
    # Original shape: (0,0), (2,0), (1,1). Bounding Box: x[0,2], y[0,1]. Center: (1, 0.5).
    # Normalized: Scale fits in 8x8. W=2, H=1. Scale=4.
    # New BBox: W=8, H=4.
    # Center (5,5).
    # New points: (-1*4+5, -0.5*4+5) -> (1, 3); (1*4+5, -0.5*4+5) -> (9, 3); (0*4+5, 0.5*4+5) -> (5, 7)
    # New BBox: x[1,9], y[3,7]. Center: (5, 5).
    # Centroid of points: (1+9+5)/3 = 5; (3+3+7)/3 = 13/3 = 4.33
    # So centroid Y is 4.33, which is not 5.0. 
    # The test expectation was wrong about centroid vs bounding box center.
    # Let's verify bounding box center instead.
    
    xs = [p["x"] for p in normalized[0]["points"]]
    ys = [p["y"] for p in normalized[0]["points"]]
    bbox_cx = (min(xs) + max(xs)) / 2
    bbox_cy = (min(ys) + max(ys)) / 2
    
    assert abs(bbox_cx - 5.0) < 0.1
    assert abs(bbox_cy - 5.0) < 0.1

def test_max_objects():
    shapes = [{"id": i} for i in range(4)]
    with pytest.raises(ValueError, match="Too many objects"):
        GeometryEngine.validate(shapes)

def test_scaling():
    # Large square 20x20 centered at 0,0
    shapes = [{"points": [{"x": -10, "y": -10}, {"x": 10, "y": 10}]}]
    normalized = GeometryEngine.normalize(shapes)
    
    p1 = normalized[0]["points"][0]
    p2 = normalized[0]["points"][1]
    
    # Target size is 8.0
    # Original width 20. Scale should be 8/20 = 0.4
    # Centered at 5,5
    # Expected p1: 5 + (-10 - 0)*0.4 = 5 - 4 = 1
    # Expected p2: 5 + (10 - 0)*0.4 = 5 + 4 = 9
    
    assert abs(p1["x"] - 1.0) < 0.1
    assert abs(p2["x"] - 9.0) < 0.1
    assert abs(p1["y"] - 1.0) < 0.1
    assert abs(p2["y"] - 9.0) < 0.1
    
    width = p2["x"] - p1["x"]
    assert abs(width - 8.0) < 0.1

def test_small_object_scaling():
    # Small object should be scaled UP to fit target size 8.0? 
    # Current logic: scale = min(target/w, target/h).
    # If object is 1x1, scale = 8/1 = 8.
    
    shapes = [{"points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}]
    normalized = GeometryEngine.normalize(shapes)
    
    p1 = normalized[0]["points"][0]
    p2 = normalized[0]["points"][1]
    
    width = p2["x"] - p1["x"]
    assert abs(width - 8.0) < 0.1
