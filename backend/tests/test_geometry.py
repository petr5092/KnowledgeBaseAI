import unittest
import math
from app.services.geometry import GeometryEngine, ShapeConfig

class TestGeometryEngine(unittest.TestCase):
    def setUp(self):
        self.engine = GeometryEngine(canvas_width=500, canvas_height=500, min_distance=10, seed=42)

    def test_determinism(self):
        reqs = [ShapeConfig(type="rectangle") for _ in range(5)]
        
        engine1 = GeometryEngine(seed=123)
        shapes1, _ = engine1.generate_layout(reqs)
        
        engine2 = GeometryEngine(seed=123)
        shapes2, _ = engine2.generate_layout(reqs)
        
        self.assertEqual(len(shapes1), len(shapes2))
        for s1, s2 in zip(shapes1, shapes2):
            self.assertEqual(s1.center.x, s2.center.x)
            self.assertEqual(s1.center.y, s2.center.y)
            self.assertEqual(s1.dimensions, s2.dimensions)

    def test_no_overlap(self):
        # Generate dense layout
        reqs = [ShapeConfig(type="rectangle", min_width=20, max_width=40, min_height=20, max_height=40) for _ in range(20)]
        shapes, stats = self.engine.generate_layout(reqs)
        self.assertTrue(stats.success)
        
        # Check all pairs
        for i in range(len(shapes)):
            for j in range(i + 1, len(shapes)):
                s1 = shapes[i]
                s2 = shapes[j]
                
                # Check AABB overlap with padding
                padding = self.engine.min_distance
                b1 = s1.bbox
                b2 = s2.bbox
                
                # Manual check: if they overlap, fail
                # Overlap logic: NOT disjoint
                disjoint = (b1.max_x + padding < b2.min_x or 
                            b1.min_x - padding > b2.max_x or 
                            b1.max_y + padding < b2.min_y or 
                            b1.min_y - padding > b2.max_y)
                
                self.assertTrue(disjoint, f"Shapes {i} and {j} overlap or are too close")

    def test_proportionality(self):
        # Use smaller shapes to ensure they fit
        reqs = [ShapeConfig(type="rectangle", min_width=10, max_width=30, min_height=10, max_height=30) for _ in range(50)]
        shapes, stats = self.engine.generate_layout(reqs, enforce_proportionality=True)
        self.assertTrue(stats.success, f"Failed to place all shapes: {stats.error}")
        
        for s in shapes:
            if s.type == "rectangle":
                w = s.dimensions["width"]
                h = s.dimensions["height"]
                diff = abs(w - h)
                max_dim = max(w, h)
                ratio = diff / max_dim
                self.assertLessEqual(ratio, 0.2000001, f"Shape {s.id} violates proportionality: {w}x{h}")

    def test_stress_100_shapes(self):
        # 100 small shapes in 1000x1000 canvas
        engine = GeometryEngine(canvas_width=1000, canvas_height=1000, min_distance=5, seed=42)
        reqs = [ShapeConfig(type="circle", radius_min=5, radius_max=10) for _ in range(100)]
        shapes, stats = engine.generate_layout(reqs)
        self.assertTrue(stats.success)
        self.assertEqual(len(shapes), 100)
        self.assertLess(stats.time_ms, 1000) # Should be fast

    def test_boundary_limits(self):
        reqs = [ShapeConfig(type="circle", radius_min=10, radius_max=20) for _ in range(10)]
        shapes, stats = self.engine.generate_layout(reqs)
        
        for s in shapes:
            b = s.bbox
            self.assertGreaterEqual(b.min_x, 0)
            self.assertGreaterEqual(b.min_y, 0)
            self.assertLessEqual(b.max_x, self.engine.canvas_width)
            self.assertLessEqual(b.max_y, self.engine.canvas_height)

    def test_impossible_placement(self):
        # Shape larger than canvas
        reqs = [ShapeConfig(type="rectangle", min_width=600, min_height=600)]
        shapes, stats = self.engine.generate_layout(reqs)
        self.assertFalse(stats.success)
        self.assertIn("too large", stats.error)

    def test_repack_shapes(self):
        # Create two overlapping squares at (0,0)
        # Square 1: 0,0 to 10,10
        s1 = {"type": "rectangle", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}, {"x": 0, "y": 10}]}
        # Square 2: 5,5 to 15,15 (overlaps)
        s2 = {"type": "rectangle", "points": [{"x": 5, "y": 5}, {"x": 15, "y": 5}, {"x": 15, "y": 15}, {"x": 5, "y": 15}]}
        
        shapes = [s1, s2]
        
        repacked = self.engine.repack_shapes(shapes)
        self.assertEqual(len(repacked), 2)
        
        # Check they don't overlap now
        # Extract bboxes from result points
        def get_bbox(pts):
            xs = [p["x"] for p in pts]
            ys = [p["y"] for p in pts]
            return min(xs), max(xs), min(ys), max(ys)
            
        min_x1, max_x1, min_y1, max_y1 = get_bbox(repacked[0]["points"])
        min_x2, max_x2, min_y2, max_y2 = get_bbox(repacked[1]["points"])
        
        # Check overlap
        padding = self.engine.min_distance
        overlap = not (max_x1 + padding < min_x2 or 
                       min_x1 - padding > max_x2 or 
                       max_y1 + padding < min_y2 or 
                       min_y1 - padding > max_y2)
                       
        self.assertFalse(overlap, "Repacked shapes should not overlap")
        
        # Check dimensions preserved
        w1 = max_x1 - min_x1
        h1 = max_y1 - min_y1
        self.assertAlmostEqual(w1, 10.0)
        self.assertAlmostEqual(h1, 10.0)

if __name__ == '__main__':
    unittest.main()
