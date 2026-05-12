from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from infrastructure.adapter.in_.order_controller import router as order_router
from infrastructure.config.database import engine
from domain.db_models import Base
 
app = FastAPI(title="Order Service", version="1.0.0")
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
 
Base.metadata.create_all(bind=engine)
app.include_router(order_router, prefix="/orders")
 
 
@app.get("/health")
def health():
    return {"service": "order-service", "status": "ok"}