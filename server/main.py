"""FastAPI application entry point."""
from fastapi import FastAPI
from server.container import Container

app = FastAPI(
    title="TermPilot",
    description="Remote terminal control system",
    version="0.1.0",
)

container = Container()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}

@app.on_event("startup")
async def startup():
    """Application startup handler."""
    # Initialize container
    container.init_resources()

@app.on_event("shutdown")
async def shutdown():
    """Application shutdown handler."""
    # Cleanup resources
    pass
