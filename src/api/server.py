import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pathlib import Path

from src.config import CORS_ORIGINS, validate_config, FRONTEND_DIR
from src.api.routes import router
from src.api.limiter import limiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    # Validate config before starting
    validate_config()
    
    app = FastAPI(
        title="Mutual Fund FAQ Assistant API",
        description="RAG-based API for answering Mutual Fund FAQs",
        version="1.0.0"
    )

    # Attach rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Apply rate limiter to router endpoints (except health/schemes if we wanted, but we'll rate limit router)
    # Slowapi requires `@limiter.limit` on specific routes, we can just apply it in routes.py 
    # OR we can add a middleware, but slowapi doesn't work perfectly as a global middleware for FastAPI without 
    # route-level injection. For now, let's just use it on specific routes or globally via dependency.

    # Since phase 6 requires slowapi rate limit, we will decorate the chat route in a wrapper or register globally
    
    app.include_router(router)
    
    # Mount static files if directory exists
    if Path(FRONTEND_DIR).exists():
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")

    return app

app = create_app()
