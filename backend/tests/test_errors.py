import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, EmailStr

from src.api.errors import (
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler
)
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

app = FastAPI(debug=False)  

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

class User(BaseModel):
    email: EmailStr

@app.get("/http-error")
def http_error():
    raise HTTPException(status_code=401, detail="invalid credentials")

@app.post("/validation-error")
def validation_error(user: User):
    return {"ok": True}

@app.get("/unexpected-error")
async def unexpected_error():
    raise RuntimeError("boom")

@app.get("/forbidden")
def forbidden():
    raise HTTPException(status_code=403, detail="forbidden")

@app.get("/unavailable")
def unavailable():
    raise HTTPException(status_code=503, detail="postgres not configured")

client = TestClient(app)

def test_http_exception():
    resp = client.get("/http-error")
    assert resp.status_code == 401
    assert resp.json() == {
        "status": 401,
        "message": "invalid credentials",
        "details": None
    }

def test_validation_exception():
    resp = client.post("/validation-error", json={"email": "not-an-email"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == 422
    assert body["message"] == "Validation error"
    assert isinstance(body["details"], list)

def test_unexpected_exception():
    resp = client.get("/unexpected-error")
    assert resp.status_code == 500
    assert resp.json() == {
        "status": 500,
        "message": "Internal server error",
        "details": "boom"
    }

def test_not_found():
    resp = client.get("/not-found")
    assert resp.status_code == 404
    assert resp.json() == {
        "status": 404,
        "message": "Not Found",
        "details": None
    }

def test_forbidden():
    resp = client.get("/forbidden")
    assert resp.status_code == 403
    assert resp.json() == {
        "status": 403,
        "message": "forbidden",
        "details": None
    }

def test_service_unavailable():
    resp = client.get("/unavailable")
    assert resp.status_code == 503
    assert resp.json() == {
        "status": 503,
        "message": "postgres not configured",
        "details": None
    }
