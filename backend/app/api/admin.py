from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPBearer
from app.api.deps import require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin), Security(HTTPBearer())], tags=["Админка"])

# Endpoints moved to other modules or deprecated.
