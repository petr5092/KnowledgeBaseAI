import math
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class GeometryEngine:
    CANVAS_MIN = 0.0
    CANVAS_MAX = 10.0
    CANVAS_SIZE = 10.0
    CENTER = 5.0
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
        Transforms coordinates from a logical Cartesian system [-5, 5] to the canvas system [0, 10].
        Logical (0,0) maps to Canvas (5,5).
        Preserves the aspect ratio and integer nature of coordinates where possible.
        """
        if not shapes:
            return []

        # 1. Collect all points to check bounds
        all_points = []
        for shape in shapes:
            points = shape.get("points", shape.get("coordinates", []))
            # Handle flat point
            if not points and "x" in shape and "y" in shape:
                points = [{"x": shape["x"], "y": shape["y"]}]
            all_points.extend(points)
        
        if not all_points:
            return shapes

        # 2. Determine Scale
        # We want to map logical [-5, 5] to canvas [0, 10].
        # If points exceed [-5, 5], we scale them down to fit.
        # If they are within range, we keep scale = 1.0 to preserve "integer-ness" as requested.
        max_abs_coord = 0.0
        for p in all_points:
            max_abs_coord = max(max_abs_coord, abs(p["x"]), abs(p["y"]))
        
        # Default logical limit is 5.0. If points go beyond (e.g. 10), we scale down.
        # We allow a small epsilon for floating point noise.
        limit = 5.0
        scale = 1.0
        if max_abs_coord > limit + 0.01:
            scale = limit / max_abs_coord
            
        # 3. Transform
        # Formula: physical = logical * scale + center_offset
        center_offset = GeometryEngine.CENTER # 5.0

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
                # Apply transformation: Logical (0,0) -> Physical (5,5)
                # Note: We do NOT flip Y here. We assume the frontend handles coordinate systems (or Y is up).
                # If Y needs to be flipped for standard screen coords (y-down), it should be done here:
                # ny = center_offset - (p["y"] * scale)
                # But usually math graphs assume Y-up. Let's stick to simple translation for now unless broken.
                
                nx = (p["x"] * scale) + center_offset
                ny = (p["y"] * scale) + center_offset
                
                # Clamp to [CANVAS_MIN, CANVAS_MAX]
                nx = max(GeometryEngine.CANVAS_MIN, min(GeometryEngine.CANVAS_MAX, nx))
                ny = max(GeometryEngine.CANVAS_MIN, min(GeometryEngine.CANVAS_MAX, ny))
                
                # Round to nearest integer (or 0.5) as requested
                # User wants integers mostly.
                # If we didn't scale (scale=1), we try to round to int/0.5
                if scale > 0.99:
                     nx = round(nx * 2) / 2.0
                     ny = round(ny * 2) / 2.0
                     if abs(nx - round(nx)) < 0.01: nx = int(round(nx))
                     if abs(ny - round(ny)) < 0.01: ny = int(round(ny))
                
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
