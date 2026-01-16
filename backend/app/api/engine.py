from fastapi import APIRouter
from app.api.ingestion import router as ingestion_router
from app.api.curriculum import router as curriculum_router
from app.api.graph import router as graph_router
from app.api.assistant import router as assistant_router
from app.api.analytics import router as analytics_router
from app.api.ws import router as ws_router
from app.api.admin import router as admin_router
from app.api.admin_curriculum import router as admin_curriculum_router
from app.api.admin_graph import router as admin_graph_router
from app.api.maintenance import router as maintenance_router
from app.api.proposals import router as proposals_router
from app.api.knowledge import router as knowledge_router
from app.api.assessment import router as assessment_router
from app.api.reasoning import router as reasoning_router

router = APIRouter()

# Core Services
router.include_router(graph_router)
router.include_router(assistant_router)
router.include_router(curriculum_router)
router.include_router(ingestion_router)
router.include_router(knowledge_router)
router.include_router(assessment_router)
router.include_router(reasoning_router)

# Support Services
router.include_router(analytics_router)
router.include_router(ws_router)
router.include_router(proposals_router)

# Administration
router.include_router(admin_router)
router.include_router(admin_curriculum_router)
router.include_router(admin_graph_router)
router.include_router(maintenance_router)
