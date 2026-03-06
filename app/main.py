from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.limiter import limiter
from app.auth.router import router as auth_router
from app.blocks.router import router as blocks_router
from app.sections.router import router as sections_router

is_prod = settings.environment == "production"

# SEC-006: deshabilitar /docs y /redoc en producción
app = FastAPI(
    title="Blogs Backend API",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not is_prod else [
        "https://johannesta.com",
        "https://admin.johannesta.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(blocks_router)
app.include_router(sections_router)


@app.get("/health")
def health():
    return {"status": "ok"}
