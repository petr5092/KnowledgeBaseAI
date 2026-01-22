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
        
        # Expand b1 by padding
        if (b1.max_x + padding < b2.min_x or 
            b1.min_x - padding > b2.max_x or 
            b1.max_y + padding < b2.min_y or 
            b1.min_y - padding > b2.max_y):
            return False # No collision
        
        return True # Collision

    def _get_intersection_area(self, b1: BoundingBox, b2: BoundingBox) -> float:
        x_overlap = max(0, min(b1.max_x, b2.max_x) - max(b1.min_x, b2.min_x))
        y_overlap = max(0, min(b1.max_y, b2.max_y) - max(b1.min_y, b2.min_y))
        return x_overlap * y_overlap

    def _get_area(self, b: BoundingBox) -> float:
        return (b.max_x - b.min_x) * (b.max_y - b.min_y)

    def _is_layout_valid(self, shapes: List[Dict]) -> bool:
        """
        Check if the layout is valid (no significant overlap between same-type shapes).
        Returns True if valid, False if needs scattering.
        """
        # Parse shapes into temp objects with bboxes
        parsed = []
        for s in shapes:
            points = s.get("points", [])
            if not points: continue
            xs = [p["x"] for p in points]
            ys = [p["y"] for p in points]
            if not xs: continue
            bbox = BoundingBox(min_x=min(xs), max_x=max(xs), min_y=min(ys), max_y=max(ys))
            parsed.append({"type": s.get("type", "polygon"), "bbox": bbox})

        # Check pairs
        for i in range(len(parsed)):
            for j in range(i + 1, len(parsed)):
                s1 = parsed[i]
                s2 = parsed[j]
                
                # If types are different (e.g. Line vs Polygon), allow overlap
                if s1["type"] != s2["type"]:
                    continue
                
                # If types are same, check IoU or simple Intersection
                # We want to detect "Stacked" shapes
                area1 = self._get_area(s1["bbox"])
                area2 = self._get_area(s2["bbox"])
                intersection = self._get_intersection_area(s1["bbox"], s2["bbox"])
                
                if intersection > 0:
                    # If overlap is significant (> 10% of smaller shape), invalid
                    min_area = min(area1, area2)
                    if min_area > 0 and (intersection / min_area) > 0.1:
                        return False
        return True

    def _scale_and_center(self, shapes: List[Dict]) -> List[Dict]:
        """
        Normalize shapes to origin (Top-Left).
        If shapes are small (logical coordinates like 0-15), PRESERVE SCALE.
        Only scale if they are very large or tiny (normalized 0..1).
        """
        # 1. Calculate Global BBox
        all_points = []
        for s in shapes:
            all_points.extend(s.get("points", []))
            
        if not all_points: return shapes

        xs = [p.get("x", 0) for p in all_points]
        ys = [p.get("y", 0) for p in all_points]
        
        if not xs: return shapes
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        w = max_x - min_x
        h = max_y - min_y
        
        # Avoid division by zero
        if w == 0: w = 1.0
        if h == 0: h = 1.0
        
        # 2. Determine Scale Factor
        scale = 1.0
        
        # Case A: Logical coordinates (e.g., width=10, height=5)
        # If the shape fits within a small grid (e.g. 50x50), assume it's logical and KEEP IT.
        # But if it's TINY (e.g. 0.0 to 1.0), it might need scaling up?
        # User requested: "return simple coordinates in integers from 0 to 15"
        # So if we have 0..15 range, we keep it.
        
        # Heuristic:
        # If max dimension > canvas_width -> Scale Down (it's too big)
        # If max dimension < 1.0 -> Scale Up (it's normalized)
        # Else -> Keep scale = 1.0 (Assume logical units)
        
        max_dim = max(w, h)
        
        padding = 0.0 # No padding for logical coords if we are just shifting
        
        if max_dim > self.canvas_width:
             # Too big, fit to canvas
             scale = (self.canvas_width - 40) / max_dim
             padding = 20.0
        elif max_dim < 2.0:
             # Too small (normalized?), scale to decent size? 
             # Or maybe user WANTS 0..1? 
             # Let's assume if it's < 2, it's normalized, scale to 10?
             # But let's be safe. If user gives 0.5, maybe it's 0.5 units.
             # Given the "0 to 15" request, 0.5 is valid.
             pass
             
        # 3. Align to Origin (Top-Left)
        # Just shift so min_x, min_y becomes 0 (or padding)
        
        result_shapes = []
        for s in shapes:
            new_s = s.copy()
            new_points = []
            for p in s.get("points", []):
                new_p = p.copy()
                # Shift to 0, scale
                new_p["x"] = (p["x"] - min_x) * scale + padding
                new_p["y"] = (p["y"] - min_y) * scale + padding
                new_points.append(new_p)
            new_s["points"] = new_points
            result_shapes.append(new_s)
            
        return result_shapes

    def repack_shapes(self, shapes: List[Dict], max_attempts: int = 100) -> List[Dict]:
        """
        Smart repack:
        1. Try to Normalize (Scale & Center) the whole group.
        2. Check if the result is valid (no bad overlaps).
        3. If invalid, fallback to Scattering.
        """
        if not shapes: return []
        
        # 1. Scale & Center (Normalize)
        scaled = self._scale_and_center(shapes)
        
        # 2. Check Validity
        if self._is_layout_valid(scaled):
            logger.info("Layout valid after scaling. Preserving relative positions.")
            return scaled
            
        # 3. Fallback
        logger.info("Layout invalid (overlap detected). Scattering shapes.")
        scattered = self._scatter_shapes(shapes, max_attempts)
        return scattered

    def _scatter_shapes(self, shapes: List[Dict], max_attempts: int) -> List[Dict]:
        """
        Scatter shapes to avoid overlap.
        Uses the standard generate_layout logic but tries to preserve shape dimensions.
        """
        # 1. Extract dimensions and types
        reqs = []
        for s in shapes:
            # Estimate dimensions from points
            points = s.get("points", [])
            if not points:
                reqs.append(ShapeConfig(type=s.get("type", "polygon")))
                continue
                
            xs = [p["x"] for p in points]
            ys = [p["y"] for p in points]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            
            # Map types
            stype = s.get("type", "polygon")
            if stype == "vector": stype = "line" # Treat vector as line for layout
            if stype not in ["rectangle", "circle", "polygon"]: stype = "polygon"
            
            reqs.append(ShapeConfig(
                type=stype,
                min_width=w, max_width=w,
                min_height=h, max_height=h,
                radius_min=w/2, radius_max=w/2 # Approx for circle
            ))
            
        # 2. Generate new layout
        new_shapes, stats = self.generate_layout(reqs)
        
        if not stats.success:
            # If failed to scatter, return original (maybe scaled)
            return self._scale_and_center(shapes)
            
        # 3. Map original shapes to new positions
        result = []
        for i, placed in enumerate(new_shapes):
            if i >= len(shapes): break
            original = shapes[i]
            
            # Original bounds
            orig_points = original.get("points", [])
            if not orig_points:
                result.append(original)
                continue
                
            oxs = [p["x"] for p in orig_points]
            oys = [p["y"] for p in orig_points]
            min_x, min_y = min(oxs), min(oys)
            
            # New position (top-left of bbox)
            new_x = placed.bbox.min_x
            new_y = placed.bbox.min_y
            
            # Shift
            dx = new_x - min_x
            dy = new_y - min_y
            
            new_s = original.copy()
            new_pts = []
            for p in orig_points:
                new_pts.append({
                    "x": p["x"] + dx,
                    "y": p["y"] + dy
                })
            new_s["points"] = new_pts
            result.append(new_s)
            
        return result


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
