from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from application.service.kitchen_service import KitchenService
from infrastructure.config.dependency_injection import get_kitchen_service
 
router = APIRouter()
 
 
@router.get("/tickets")
def list_active_tickets(service: KitchenService = Depends(get_kitchen_service)):
    return service.list_active_tickets()
 
 
@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, service: KitchenService = Depends(get_kitchen_service)):
    result = service.get_ticket(ticket_id)
    if not result:
        raise HTTPException(404, f"Тикет {ticket_id} не найден")
    return result
 
 
@router.get("/stations/{station}/queue")
def station_queue(station: str, service: KitchenService = Depends(get_kitchen_service)):
    """Очередь блюд для конкретной станции (GRILL, PASTA, DESSERT, BAR)"""
    return service.get_station_queue(station)
 
 
@router.post("/tickets/{ticket_id}/start")
def start_cooking(ticket_id: str, service: KitchenService = Depends(get_kitchen_service)):
    service.start_cooking(ticket_id)
    return {"status": "IN_PROGRESS"}
 
 
@router.post("/tickets/{ticket_id}/items/{dish_id}/done")
def mark_item_done(ticket_id: str, dish_id: str,
                   service: KitchenService = Depends(get_kitchen_service)):
    service.mark_item_done(ticket_id, dish_id)
    return {"status": "done"}
 
 
@router.post("/tickets/{ticket_id}/complete")
def complete_ticket(ticket_id: str, service: KitchenService = Depends(get_kitchen_service)):
    service.complete_ticket(ticket_id)
    return {"status": "DONE"}
 
 
@router.get("/health")
def health():
    return {"service": "kitchen-service", "status": "ok"}