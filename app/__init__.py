from fastapi import FastAPI
from app.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Bouncer")
    app.include_router(router)
    return app
