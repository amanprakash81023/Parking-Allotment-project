from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import engine, Base
from app.exceptions import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)
from app.routers import slots, vehicles, allocations


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is initialized
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Parking Allotment API",
    version="1.0.0",
    description="Production-ready REST API for managing parking slot allocation, vehicle registration, and occupancy.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Exception handlers enforcing §5.8 error envelope
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Register routers
app.include_router(slots.router)
app.include_router(vehicles.router)
app.include_router(allocations.router)


@app.get("/health", tags=["Health"], summary="Health check endpoint")
def health_check():
    return {"status": "ok"}
