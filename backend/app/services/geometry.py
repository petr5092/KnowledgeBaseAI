import random
import math
import logging
import time
from typing import List, Dict, Optional, Tuple, Union, Literal
from pydantic import BaseModel, Field

# Setup logging
logger = logging.getLogger(__name__)
# Avoid adding handler if already exists to prevent dupes in reload
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

class Point(BaseModel):
    x: float
    y: float

class BoundingBox(BaseModel):
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

class ShapeConfig(BaseModel):
    type: Literal["rectangle", "circle", "polygon"]
    min_width: float = 10.0
    max_width: float = 50.0
    min_height: float = 10.0
    max_height: float = 50.0
    radius_min: float = 5.0
    radius_max: float = 25.0
    num_vertices: int = 3

class PlacedShape(BaseModel):
    id: str
    type: str
    center: Point
    dimensions: Dict[str, float]
    coordinates: List[Dict[str, float]]
    bbox: BoundingBox

class GenerationStats(BaseModel):
    total_shapes: int
    attempts: int
    time_ms: float
    success: bool
    error: Optional[str] = None

class GeometryEngine:
    def __init__(self, 
                 canvas_width: float = 400.0, 
                 canvas_height: float = 400.0, 
                 min_distance: float = 10.0,
                 seed: Optional[int] = None):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.min_distance = min_distance
        self.seed = seed
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.placed_shapes: List[PlacedShape] = []
        logger.info(f"Initialized GeometryEngine: {canvas_width}x{canvas_height}, seed={seed}")

    def _get_random_float(self, low: float, high: float) -> float:
        return self.rng.uniform(low, high)

    def _create_bbox_rect(self, cx: float, cy: float, w: float, h: float) -> BoundingBox:
        return BoundingBox(
            min_x=cx - w/2,
            max_x=cx + w/2,
            min_y=cy - h/2,
            max_y=cy + h/2
        )

    def _create_bbox_circle(self, cx: float, cy: float, r: float) -> BoundingBox:
        return BoundingBox(
            min_x=cx - r,
            max_x=cx + r,
            min_y=cy - r,
            max_y=cy + r
        )

    def _check_collision(self, shape1: PlacedShape, shape2: PlacedShape, padding: float) -> bool:
        # AABB Check with padding
        b1 = shape1.bbox
        b2 = shape2.bbox
        
        # Effective padding is shared, so use full padding check?
        # Requirement: "Strict observance of minimum distances"
        # If min_distance is D, then shapes must be at least D apart.
        # So we expand each bbox by D/2? Or check if dist(bbox1, bbox2) < D?
        # Simplest: Expand both by D/2. Overlap means distance < D in L-infinity norm.
        # For strict Euclidean distance, we need more complex checks, but AABB is safe upper bound.
        
        # Expand b1 by padding
        if (b1.max_x + padding < b2.min_x or 
            b1.min_x - padding > b2.max_x or 
            b1.max_y + padding < b2.min_y or 
            b1.min_y - padding > b2.max_y):
            return False # No collision
        
        return True # Collision

    def repack_shapes(self, shapes: List[Dict], max_attempts: int = 100) -> List[Dict]:
        """
        Repack existing shapes to avoid overlap, preserving their local geometry.
        Input: List of dicts, each like {"type": "...", "points": [...], "label": ...}
        Output: List of dicts with updated "points".
        """
        self.placed_shapes = []
        result_shapes = []
        
        for i, shape_data in enumerate(shapes):
            s_type = shape_data.get("type", "polygon")
            points = shape_data.get("points", [])
            
            # 1. Calculate BBox and Dimensions from current points
            if not points:
                result_shapes.append(shape_data) # Cannot process empty
                continue
                
            xs = [p["x"] for p in points if "x" in p]
            ys = [p["y"] for p in points if "y" in p]
            
            if not xs or not ys:
                 result_shapes.append(shape_data)
                 continue

            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            w = max_x - min_x
            h = max_y - min_y
            
            # Local centered coordinates
            orig_cx = (min_x + max_x) / 2
            orig_cy = (min_y + max_y) / 2
            
            local_points = []
            for p in points:
                local_points.append({
                    "x": p.get("x", 0) - orig_cx,
                    "y": p.get("y", 0) - orig_cy,
                    "label": p.get("label"), # Preserve other fields if needed
                })

            # 2. Try to place in new location
            placed = False
            
            # Determine placement bounds
            min_cx = w/2
            max_cx = self.canvas_width - w/2
            min_cy = h/2
            max_cy = self.canvas_height - h/2
            
            # If shape is larger than canvas, just center it and give up on non-overlap
            if min_cx > max_cx or min_cy > max_cy:
                cx, cy = self.canvas_width/2, self.canvas_height/2
                placed = True # Force placement
            
            if not placed:
                for _ in range(max_attempts):
                    cx = self._get_random_float(min_cx, max_cx)
                    cy = self._get_random_float(min_cy, max_cy)
                    
                    # Create candidate
                    bbox = self._create_bbox_rect(cx, cy, w, h)
                    
                    # Reconstruct absolute points for checking/result
                    abs_points = []
                    for lp in local_points:
                        new_p = {"x": lp["x"] + cx, "y": lp["y"] + cy}
                        if lp.get("label"): new_p["label"] = lp["label"]
                        abs_points.append(new_p)

                    candidate = PlacedShape(
                        id=f"repack_{i}",
                        type=s_type,
                        center=Point(x=cx, y=cy),
                        dimensions={"width": w, "height": h},
                        coordinates=abs_points,
                        bbox=bbox
                    )
                    
                    # Check collision
                    collision = False
                    for existing in self.placed_shapes:
                        if self._check_collision(candidate, existing, self.min_distance):
                            collision = True
                            break
                    
                    if not collision:
                        self.placed_shapes.append(candidate)
                        
                        # Update original shape data with new points
                        new_shape_data = shape_data.copy()
                        new_shape_data["points"] = abs_points
                        result_shapes.append(new_shape_data)
                        placed = True
                        break
            
            if not placed:
                # Fallback: keep original or place at random?
                # If we fail to place, we append original to avoid losing data, 
                # but it might overlap.
                result_shapes.append(shape_data)
                
        return result_shapes

    def generate_layout(self, requests: List[ShapeConfig], max_attempts_per_shape: int = 100, enforce_proportionality: bool = True) -> Tuple[List[PlacedShape], GenerationStats]:
        start_time = time.time()
        self.placed_shapes = []
        total_attempts = 0
        
        logger.info(f"Starting layout generation for {len(requests)} shapes")
        
        for i, req in enumerate(requests):
            placed = False
            shape_attempts = 0
            
            # Diagnostic for impossible requests
            if req.type == "rectangle" and (req.min_width > self.canvas_width or req.min_height > self.canvas_height):
                 return self.placed_shapes, GenerationStats(
                    total_shapes=len(self.placed_shapes),
                    attempts=total_attempts,
                    time_ms=(time.time() - start_time) * 1000,
                    success=False,
                    error=f"Shape {i} too large for canvas"
                )

            for attempt in range(max_attempts_per_shape):
                shape_attempts += 1
                total_attempts += 1
                candidate: Optional[PlacedShape] = None
                
                # 1. Generate Dimensions & Position
                if req.type == "rectangle":
                    # Generate W/H
                    w = self._get_random_float(req.min_width, req.max_width)
                    h = self._get_random_float(req.min_height, req.max_height)
                    
                    # Proportionality Check: abs(w-h)/max(w,h) <= 0.2
                    if enforce_proportionality:
                        diff = abs(w - h)
                        max_dim = max(w, h)
                        if max_dim > 0 and (diff / max_dim) > 0.2:
                            # Try to adjust one to match? Or just retry?
                            # Retry is safer for distribution
                            continue
                            
                    # Position
                    min_cx = w/2
                    max_cx = self.canvas_width - w/2
                    min_cy = h/2
                    max_cy = self.canvas_height - h/2
                    
                    if min_cx > max_cx or min_cy > max_cy:
                        continue # Should not happen if size check passed, but floating point..

                    cx = self._get_random_float(min_cx, max_cx)
                    cy = self._get_random_float(min_cy, max_cy)
                    
                    bbox = self._create_bbox_rect(cx, cy, w, h)
                    coords = [
                        {"x": cx - w/2, "y": cy - h/2},
                        {"x": cx + w/2, "y": cy - h/2},
                        {"x": cx + w/2, "y": cy + h/2},
                        {"x": cx - w/2, "y": cy + h/2}
                    ]
                    
                    candidate = PlacedShape(
                        id=f"shape_{i}",
                        type="rectangle",
                        center=Point(x=cx, y=cy),
                        dimensions={"width": w, "height": h},
                        coordinates=coords,
                        bbox=bbox
                    )

                elif req.type == "circle":
                    r = self._get_random_float(req.radius_min, req.radius_max)
                    
                    min_cx = r
                    max_cx = self.canvas_width - r
                    min_cy = r
                    max_cy = self.canvas_height - r
                    
                    if min_cx > max_cx or min_cy > max_cy:
                        continue
                        
                    cx = self._get_random_float(min_cx, max_cx)
                    cy = self._get_random_float(min_cy, max_cy)
                    
                    bbox = self._create_bbox_circle(cx, cy, r)
                    coords = [{"x": cx, "y": cy, "r": r}]
                    
                    candidate = PlacedShape(
                        id=f"shape_{i}",
                        type="circle",
                        center=Point(x=cx, y=cy),
                        dimensions={"radius": r},
                        coordinates=coords,
                        bbox=bbox
                    )
                
                elif req.type == "polygon":
                    r = self._get_random_float(req.radius_min, req.radius_max)
                    min_cx = r
                    max_cx = self.canvas_width - r
                    min_cy = r
                    max_cy = self.canvas_height - r
                    
                    if min_cx > max_cx or min_cy > max_cy:
                        continue
                        
                    cx = self._get_random_float(min_cx, max_cx)
                    cy = self._get_random_float(min_cy, max_cy)
                    
                    vertices = []
                    angle_step = 2 * math.pi / req.num_vertices
                    start_angle = self._get_random_float(0, 2 * math.pi)
                    
                    for v in range(req.num_vertices):
                        angle = start_angle + v * angle_step
                        vx = cx + r * math.cos(angle)
                        vy = cy + r * math.sin(angle)
                        vertices.append({"x": vx, "y": vy})
                        
                    bbox = self._create_bbox_circle(cx, cy, r)
                    candidate = PlacedShape(
                        id=f"shape_{i}",
                        type="polygon",
                        center=Point(x=cx, y=cy),
                        dimensions={"radius": r},
                        coordinates=vertices,
                        bbox=bbox
                    )

                if candidate:
                    # Check collisions
                    collision = False
                    for existing in self.placed_shapes:
                        if self._check_collision(candidate, existing, self.min_distance):
                            collision = True
                            break
                    
                    if not collision:
                        self.placed_shapes.append(candidate)
                        placed = True
                        break
            
            if not placed:
                msg = f"Failed to place shape {i} ({req.type}) after {shape_attempts} attempts"
                logger.error(msg)
                return self.placed_shapes, GenerationStats(
                    total_shapes=len(self.placed_shapes),
                    attempts=total_attempts,
                    time_ms=(time.time() - start_time) * 1000,
                    success=False,
                    error=msg
                )

        logger.info(f"Successfully generated {len(self.placed_shapes)} shapes in {total_attempts} attempts")
        return self.placed_shapes, GenerationStats(
            total_shapes=len(self.placed_shapes),
            attempts=total_attempts,
            time_ms=(time.time() - start_time) * 1000,
            success=True
        )
