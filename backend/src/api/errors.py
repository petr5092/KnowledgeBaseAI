import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("errors")

def http_error_response(status_code: int, message: str, details: any = None):
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_code,
            "message": message,
            "details": details
        }
    )

def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning(f"HTTPException: {exc.detail}")
    return http_error_response(exc.status_code, exc.detail)

def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error", exc_info=True)
    return http_error_response(422, "Validation error", details=exc.errors())

def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return http_error_response(500, "Internal server error", details=str(exc))
