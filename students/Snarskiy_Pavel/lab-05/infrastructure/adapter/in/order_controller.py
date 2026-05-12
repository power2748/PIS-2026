from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from typing import List, Optional
 
from application.command.create_order_command import CreateOrderCommand, OrderItemData
from application.command.send_to_kitchen_command import SendToKitchenCommand
from application.command.initiate_payment_command import InitiatePaymentCommand
from application.command.complete_payment_command import CompletePaymentCommand
from application.command.cancel_order_command import CancelOrderCommand
from application.query.get_order_by_id_query import GetOrderByIdQuery
from application.query.list_active_orders_query import ListActiveOrdersQuery
from application.service.order_service import OrderService
from domain.exceptions.domain_exception import (
    OrderNotFoundException, TableOccupiedException,
    DishUnavailableException, InvalidOrderStateException,
)
from infrastructure.config.dependency_injection import get_order_service
 
router = APIRouter(prefix="/api/orders", tags=["Orders"])
 
 
# ── Request/Response Pydantic-схемы ───────────────────────────────
 
class OrderItemRequest(BaseModel):
    dish_id: str   = Field(..., min_length=1)
    dish_name: str = Field(..., min_length=1)
    quantity: int  = Field(..., gt=0)
    price: float   = Field(..., ge=0)
    station: str   = Field(..., pattern="^(GRILL|PASTA|DESSERT|BAR|COLD)$")
    comment: Optional[str] = None
 
class CreateOrderRequest(BaseModel):
    table_id: int          = Field(..., gt=0, le=999)
    guests: int            = Field(..., gt=0)
    items: List[OrderItemRequest] = Field(..., min_length=1)
    comment: Optional[str] = None
 
class SendToKitchenRequest(BaseModel):
    waiter_id: str = Field(..., min_length=1)
 
class InitiatePaymentRequest(BaseModel):
    payment_method: str = Field(..., pattern="^(CARD|CASH|QR)$")
    tip: float          = Field(default=0.0, ge=0)
 
class ConfirmPaymentRequest(BaseModel):
    payment_id: str    = Field(..., min_length=1)
    transaction_id: str = Field(..., min_length=1)
 
class CancelOrderRequest(BaseModel):
    reason: Optional[str] = ""
 
class OrderIdResponse(BaseModel):
    order_id: str
 
class TicketIdResponse(BaseModel):
    ticket_id: str
 
class PaymentIdResponse(BaseModel):
    payment_id: str
 
 
# ── Endpoints ─────────────────────────────────────────────────────
 
@router.post("", status_code=status.HTTP_201_CREATED, response_model=OrderIdResponse)
def create_order(
    body: CreateOrderRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    service: OrderService = Depends(get_order_service),
):
    """Создать новый заказ для столика"""
    try:
        command = CreateOrderCommand(
            table_id=body.table_id,
            guests=body.guests,
            items=[
                OrderItemData(
                    dish_id=i.dish_id, dish_name=i.dish_name,
                    quantity=i.quantity, price=i.price,
                    station=i.station, comment=i.comment,
                )
                for i in body.items
            ],
            comment=body.comment,
            idempotency_key=idempotency_key,
        )
        order_id = service.create_order(command)
        return OrderIdResponse(order_id=order_id)
 
    except TableOccupiedException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DishUnavailableException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
 
 
@router.post("/{order_id}/send", response_model=TicketIdResponse)
def send_to_kitchen(
    order_id: str,
    body: SendToKitchenRequest,
    service: OrderService = Depends(get_order_service),
):
    """Отправить заказ на кухню"""
    try:
        command = SendToKitchenCommand(order_id=order_id, waiter_id=body.waiter_id)
        ticket_id = service.send_to_kitchen(command)
        return TicketIdResponse(ticket_id=ticket_id)
    except OrderNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidOrderStateException as e:
        raise HTTPException(status_code=409, detail=str(e))
 
 
@router.post("/{order_id}/pay", response_model=PaymentIdResponse)
def initiate_payment(
    order_id: str,
    body: InitiatePaymentRequest,
    service: OrderService = Depends(get_order_service),
):
    """Инициировать оплату заказа"""
    try:
        command = InitiatePaymentCommand(
            order_id=order_id,
            payment_method=body.payment_method,
            tip=body.tip,
        )
        payment_id = service.initiate_payment(command)
        return PaymentIdResponse(payment_id=payment_id)
    except OrderNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidOrderStateException as e:
        raise HTTPException(status_code=409, detail=str(e))
 
 
@router.post("/payments/{payment_id}/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_payment(
    payment_id: str,
    body: ConfirmPaymentRequest,
    service: OrderService = Depends(get_order_service),
):
    """Подтвердить успешное списание от эквайринга (вызывает PaymentWorker)"""
    try:
        command = CompletePaymentCommand(
            payment_id=payment_id,
            transaction_id=body.transaction_id,
        )
        service.complete_payment(command)
    except OrderNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
 
 
@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_order(
    order_id: str,
    body: CancelOrderRequest,
    service: OrderService = Depends(get_order_service),
):
    """Отменить заказ"""
    try:
        service.cancel_order(CancelOrderCommand(order_id=order_id, reason=body.reason))
    except OrderNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidOrderStateException as e:
        raise HTTPException(status_code=409, detail=str(e))
 
 
@router.get("/{order_id}")
def get_order(
    order_id: str,
    service: OrderService = Depends(get_order_service),
):
    """Получить заказ по ID"""
    try:
        return service.get_order_by_id(GetOrderByIdQuery(order_id=order_id))
    except OrderNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
 
 
@router.get("")
def list_active_orders(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    service: OrderService = Depends(get_order_service),
):
    """Список активных заказов в зале с пагинацией"""
    query = ListActiveOrdersQuery(
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )
    return service.list_active_orders(query)