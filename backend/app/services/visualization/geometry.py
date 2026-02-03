import math
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class GeometryEngine:
    CANVAS_MIN = -5.0
    CANVAS_MAX = 5.0
    CANVAS_SIZE = 10.0
    CENTER = 0.0
    MAX_OBJECTS = 3
    MIN_DISTANCE = 1.0
    TARGET_SIZE = 8.0  # Leave 1.0 margin on each side

    @staticmethod
    def validate(shapes: List[Dict[str, Any]]):
        if len(shapes) > GeometryEngine.MAX_OBJECTS:
            raise ValueError(f"Too many objects: {len(shapes)} > {GeometryEngine.MAX_OBJECTS}")
        
        # Additional validation can be added here
        for i, shape in enumerate(shapes):
            points = shape.get("points", shape.get("coordinates", []))
            
            # Allow single point defined with x, y directly
            if not points and "x" in shape and "y" in shape:
                continue
                
            if not points:
                logger.warning(f"Shape {i} has no points")

    @staticmethod
    def normalize(shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Scales and centers the entire scene (collection of shapes) to fit within the 10x10 canvas.
        Preserves relative positions of shapes within the scene.
        """
        if not shapes:
            return []

        # 1. Collect all points to find bounding box of the entire scene
        all_points = []
        for shape in shapes:
            points = shape.get("points", shape.get("coordinates", []))
            # Handle flat point
            if not points and "x" in shape and "y" in shape:
                points = [{"x": shape["x"], "y": shape["y"]}]
            all_points.extend(points)
        
        if not all_points:
            return shapes

        min_x = min(p["x"] for p in all_points)
        max_x = max(p["x"] for p in all_points)
        min_y = min(p["y"] for p in all_points)
        max_y = max(p["y"] for p in all_points)

        width = max_x - min_x
        height = max_y - min_y

        # 2. Calculate scale to fit in TARGET_SIZE x TARGET_SIZE
        # Avoid division by zero
        scale_x = GeometryEngine.TARGET_SIZE / width if width > 1e-6 else 1.0
        scale_y = GeometryEngine.TARGET_SIZE / height if height > 1e-6 else 1.0
        
        # Use the smaller scale to fit both dimensions (uniform scaling)
        # If one dimension is 0 (e.g. horizontal line), use the other scale
        if width <= 1e-6:
            scale = scale_y
        elif height <= 1e-6:
            scale = scale_x
        else:
            scale = min(scale_x, scale_y)
            
        # If both are 0 (single point), scale doesn't matter, set to 1
        if width <= 1e-6 and height <= 1e-6:
            scale = 1.0

        # 3. Calculate current centroid of the bounding box
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        # 4. Transform points
        normalized_shapes = []
        for shape in shapes:
            # Deep copy to avoid modifying original
            new_shape = shape.copy()
            if "params" in shape:
                new_shape["params"] = shape["params"].copy()
                
            new_points = []
            points_source = shape.get("points", shape.get("coordinates", []))
            is_flat_point = False
            
            if not points_source and "x" in shape and "y" in shape:
                points_source = [{"x": shape["x"], "y": shape["y"]}]
                is_flat_point = True
            
            for p in points_source:
                # Translate to 0,0 relative to bbox center, then scale, then translate to canvas center
                nx = (p["x"] - center_x) * scale + GeometryEngine.CENTER
                ny = (p["y"] - center_y) * scale + GeometryEngine.CENTER
                
                # Clamp to [-5, 5] just in case of float errors, though logic should keep it inside [-4, 4]
                nx = max(GeometryEngine.CANVAS_MIN, min(GeometryEngine.CANVAS_MAX, nx))
                ny = max(GeometryEngine.CANVAS_MIN, min(GeometryEngine.CANVAS_MAX, ny))
                
                new_points.append({"x": nx, "y": ny})
            
            # Update the shape with new points using the same key as found
            if is_flat_point and new_points:
                new_shape["x"] = new_points[0]["x"]
                new_shape["y"] = new_points[0]["y"]
            elif "points" in shape:
                new_shape["points"] = new_points
            else:
                new_shape["coordinates"] = new_points
                
            normalized_shapes.append(new_shape)
            
        return normalized_shapes

    @staticmethod
    def check_collisions(shapes: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
        """
        Returns a list of pairs of indices of shapes that overlap or are too close.
        Uses bounding boxes for simplicity.
        """
        conflicts = []
        bboxes = []
        
        for i, shape in enumerate(shapes):
            points = shape.get("points", shape.get("coordinates", []))
            if not points:
                bboxes.append(None)
                continue
            
            xs = [p["x"] for p in points]
            ys = [p["y"] for p in points]
            bboxes.append({
                "min_x": min(xs), "max_x": max(xs),
                "min_y": min(ys), "max_y": max(ys)
            })
            
        for i in range(len(bboxes)):
            if bboxes[i] is None: continue
            for j in range(i + 1, len(bboxes)):
                if bboxes[j] is None: continue
                
                b1 = bboxes[i]
                b2 = bboxes[j]
                
                # Check for overlap with margin
                margin = GeometryEngine.MIN_DISTANCE / 2
                
                overlap_x = (b1["min_x"] - margin < b2["max_x"] + margin) and \
                            (b1["max_x"] + margin > b2["min_x"] - margin)
                
                overlap_y = (b1["min_y"] - margin < b2["max_y"] + margin) and \
                            (b1["max_y"] + margin > b2["min_y"] - margin)
                            
                if overlap_x and overlap_y:
                    conflicts.append((i, j))
                    
        return conflicts
