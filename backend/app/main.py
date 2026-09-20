from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from .models import Base
from .api.market import router as market_router
from .api.companies import router as companies_router
from .services.scheduler import start_scheduler


Base.metadata.create_all(bind=engine)

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
    start_scheduler()