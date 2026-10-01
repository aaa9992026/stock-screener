from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, ensure_schema_compatibility
from .models import Base
from .api.market import router as market_router
from .api.companies import router as companies_router
from .services.scheduler import start_scheduler
from .services.company_sync import bootstrap_companies_from_stored_data
from .database import SessionLocal


Base.metadata.create_all(bind=engine)
ensure_schema_compatibility()

app = FastAPI(title="Stock Screener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router)
app.include_router(companies_router)

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Stock Screener API is running"
    }

@app.on_event("startup")
def startup_event():
    # Recover the visible screener universe immediately from data already in
    # PostgreSQL; external symbol-master sync continues in the background.
    db = SessionLocal()
    try:
        bootstrap_companies_from_stored_data(db)
    except Exception:
        db.rollback()
    finally:
        db.close()
    start_scheduler()