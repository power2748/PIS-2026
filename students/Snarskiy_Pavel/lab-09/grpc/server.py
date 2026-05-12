import grpc
import time
import queue
from concurrent import futures
from datetime import datetime
 
# Сгенерированные protobuf-классы
from grpc.generated import order_service_pb2 as pb
from grpc.generated import order_service_pb2_grpc as pb_grpc
from grpc.generated import kitchen_service_pb2 as kitchen_pb
from grpc.generated import kitchen_service_pb2_grpc as kitchen_pb_grpc
 
from application.command.create_order_command import CreateOrderCommand, OrderItemData
from application.command.handlers.create_order_handler import CreateOrderHandler
from application.query.get_order_by_id_query import GetOrderByIdQuery
from application.query.handlers.get_order_by_id_handler import GetOrderByIdHandler
from infrastructure.config.dependency_injection import (
    build_create_order_handler,
    build_get_order_by_id_handler,
    build_mark_order_ready_handler,
)
 
 
# ── Хранилище подписчиков для streaming ───────────────────────────
# В продакшне — Redis Pub/Sub или RabbitMQ
_order_update_subscribers: list[queue.Queue] = []
 
 
class OrderServicer(pb_grpc.OrderServiceServicer):
    """
    gRPC-сервер Order Service.
    Делегирует вызовы в Application Layer (Command/Query Handlers).
    Реализует unary и server-side streaming RPC.
    """
 
    # ── Unary RPC: CreateOrder ─────────────────────────────────────
 
    def CreateOrder(self, request: pb.CreateOrderRequest, context):
        """
        Unary RPC: создать заказ.
        Принимает protobuf-сообщение, конвертирует в Command, вызывает handler.
        """
        try:
            handler: CreateOrderHandler = build_create_order_handler()
 
            command = CreateOrderCommand(
                table_id=request.table_id,
                guests=request.guests,
                items=[
                    OrderItemData(
                        dish_id=i.dish_id,
                        dish_name=i.dish_name,
                        quantity=i.quantity,
                        price=i.price,
                        station=i.station,
                        comment=i.comment or None,
                    )
                    for i in request.items
                ],
                comment=request.comment or None,
                idempotency_key=request.idempotency_key or None,
            )
 
            order_id = handler.handle(command)
 
            return pb.CreateOrderResponse(
                order_id=order_id,
                status="NEW",
                total=sum(i.price * i.quantity for i in request.items),
                currency="RUB",
            )
 
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb.CreateOrderResponse()
 
    # ── Unary RPC: GetOrder ────────────────────────────────────────
 
    def GetOrder(self, request: pb.GetOrderRequest, context):
        """Unary RPC: получить заказ по ID"""
        handler: GetOrderByIdHandler = build_get_order_by_id_handler()
 
        try:
            dto = handler.handle(GetOrderByIdQuery(order_id=request.order_id))
        except Exception as e:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(str(e))
            return pb.OrderDto()
 
        return pb.OrderDto(
            order_id=dto.order_id,
            table_id=dto.table_id,
            guests=dto.guests,
            status=dto.status,
            status_label=dto.status,
            total=dto.total,
            currency=dto.currency,
            version=dto.version,
            comment=dto.comment or "",
            items=[
                pb.OrderItemProto(
                    dish_id=i.dish_id,
                    dish_name=i.dish_name,
                    quantity=i.quantity,
                    price=i.unit_price,
                    station=i.station,
                    comment=i.comment or "",
                )
                for i in dto.items
            ],
            ticket_id=dto.kitchen_ticket.ticket_id if dto.kitchen_ticket else "",
            payment_id=dto.payment.payment_id if dto.payment else "",
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )
 
    # ── Unary RPC: MarkOrderReady ──────────────────────────────────
 
    def MarkOrderReady(self, request: pb.MarkOrderReadyRequest, context):
        """
        Unary RPC: пометить заказ готовым.
        Вызывается Kitchen Service после завершения тикета.
        """
        try:
            handler = build_mark_order_ready_handler()
            handler.handle(request.order_id, request.ticket_id)
 
            # Уведомляем всех streaming-подписчиков об изменении
            _notify_subscribers(request.order_id)
 
            return pb.MarkOrderReadyResponse(
                order_id=request.order_id,
                status="READY",
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb.MarkOrderReadyResponse()
 
    # ── Server-Side Streaming: StreamActiveOrders ──────────────────
 
    def StreamActiveOrders(self, request: pb.ListActiveOrdersRequest, context):
        """
        Server-side streaming RPC: подписка на обновления активных заказов.
        Используется менеджером зала для real-time карты столиков.
 
        Клиент вызывает один раз → сервер отправляет обновления
        каждый раз, когда меняется статус любого активного заказа.
        Поток закрывается при отключении клиента.
        """
        handler: GetOrderByIdHandler = build_get_order_by_id_handler()
 
        # 1. Сначала отправляем текущее состояние всех активных заказов
        from application.query.list_active_orders_query import ListActiveOrdersQuery
        from application.query.handlers.list_active_orders_handler import ListActiveOrdersHandler
        from infrastructure.config.dependency_injection import build_list_active_orders_handler
 
        list_handler: ListActiveOrdersHandler = build_list_active_orders_handler()
        summaries = list_handler.handle(
            ListActiveOrdersQuery(page=request.page or 1,
                                  page_size=request.page_size or 50)
        )
 
        for summary in summaries:
            if context.is_active():
                dto = handler.handle(GetOrderByIdQuery(summary.order_id))
                yield _dto_to_proto(dto)
 
        # 2. Регистрируем подписчика на обновления
        update_queue: queue.Queue = queue.Queue()
        _order_update_subscribers.append(update_queue)
 
        try:
            while context.is_active():
                try:
                    # Ждём обновления (таймаут 1 сек чтобы проверять is_active)
                    order_id = update_queue.get(timeout=1.0)
                    dto = handler.handle(GetOrderByIdQuery(order_id))
                    yield _dto_to_proto(dto)
                except queue.Empty:
                    continue
        finally:
            _order_update_subscribers.remove(update_queue)
            print(f"[OrderServicer] Client disconnected from StreamActiveOrders")
 
 
def _notify_subscribers(order_id: str):
    """Рассылает order_id всем активным streaming-подписчикам"""
    for q in _order_update_subscribers:
        try:
            q.put_nowait(order_id)
        except queue.Full:
            pass
 
 
def _dto_to_proto(dto) -> pb.OrderDto:
    return pb.OrderDto(
        order_id=dto.order_id,
        table_id=dto.table_id,
        guests=dto.guests,
        status=dto.status,
        status_label=dto.status,
        total=dto.total,
        currency=dto.currency,
        version=dto.version,
        comment=dto.comment or "",
        items=[
            pb.OrderItemProto(
                dish_id=i.dish_id, dish_name=i.dish_name,
                quantity=i.quantity, price=i.unit_price,
                station=i.station, comment=i.comment or "",
            )
            for i in dto.items
        ],
        ticket_id=dto.kitchen_ticket.ticket_id if dto.kitchen_ticket else "",
        payment_id=dto.payment.payment_id if dto.payment else "",
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )
 
 
# ── Kitchen Service gRPC Server ────────────────────────────────────
 
class KitchenServicer(kitchen_pb_grpc.KitchenServiceServicer):
    """
    gRPC-сервер Kitchen Service.
    Создаёт тикеты, управляет станциями, стримит обновления на KDS.
    """
 
    # Очереди обновлений для каждой станции (station → list[Queue])
    _station_subscribers: dict[str, list[queue.Queue]] = {}
 
    def CreateTicket(self, request: kitchen_pb.CreateTicketRequest, context):
        from infrastructure.config.dependency_injection import build_create_ticket_handler
        from application.command.create_ticket_command import CreateTicketCommand
 
        try:
            handler = build_create_ticket_handler()
            command = CreateTicketCommand(
                ticket_id=request.ticket_id,
                order_id=request.order_id,
                table_number=request.table_number,
                items=[
                    {"dish_id": i.dish_id, "dish_name": i.dish_name,
                     "quantity": i.quantity, "station": i.station,
                     "comment": i.comment}
                    for i in request.items
                ],
            )
            handler.handle(command)
 
            # Уведомляем KDS-подписчиков по станциям
            stations = {i.station for i in request.items}
            for station in stations:
                self._notify_station(station, {
                    "event_type":   "TICKET_CREATED",
                    "ticket_id":    request.ticket_id,
                    "order_id":     request.order_id,
                    "table_number": request.table_number,
                    "station":      station,
                })
 
            # ETA: максимум по станциям
            ETA = {"GRILL": 20, "PASTA": 15, "DESSERT": 10, "BAR": 5, "COLD": 5}
            eta = max((ETA.get(i.station, 15) for i in request.items), default=15)
 
            return kitchen_pb.CreateTicketResponse(
                ticket_id=request.ticket_id,
                status="PENDING",
                eta_minutes=eta,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return kitchen_pb.CreateTicketResponse()
 
    def GetStationQueue(self, request: kitchen_pb.StationQueueRequest, context):
        from infrastructure.config.dependency_injection import build_station_queue_handler
        tickets = build_station_queue_handler().handle(request.station)
        return kitchen_pb.StationQueueResponse(
            tickets=[
                kitchen_pb.TicketDto(
                    ticket_id=t.ticket_id,
                    order_id=t.order_id,
                    table_number=t.table_number,
                    status=t.status,
                )
                for t in tickets
            ]
        )
 
    def StreamStationUpdates(self, request: kitchen_pb.StationQueueRequest, context):
        """
        Server-side streaming: KDS-дисплей конкретной станции подписывается
        на обновления (TICKET_CREATED, ITEM_DONE, TICKET_COMPLETED).
        Поток непрерывный — пока клиент подключён.
        """
        station = request.station
        update_queue: queue.Queue = queue.Queue()
 
        if station not in self._station_subscribers:
            self._station_subscribers[station] = []
        self._station_subscribers[station].append(update_queue)
 
        print(f"[KitchenServicer] KDS subscribed to station: {station}")
 
        try:
            while context.is_active():
                try:
                    event = update_queue.get(timeout=1.0)
                    yield kitchen_pb.KitchenUpdateEvent(
                        event_type=event["event_type"],
                        ticket_id=event["ticket_id"],
                        order_id=event["order_id"],
                        table_number=event["table_number"],
                        station=event.get("station", station),
                        dish_id=event.get("dish_id", ""),
                        timestamp=datetime.now().isoformat(),
                    )
                except queue.Empty:
                    continue
        finally:
            self._station_subscribers[station].remove(update_queue)
 
    def _notify_station(self, station: str, event: dict):
        for q in self._station_subscribers.get(station, []):
            try:
                q.put_nowait(event)
            except queue.Full:
                pass
 
 
# ── Запуск серверов ───────────────────────────────────────────────
 
def serve_order_service(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_OrderServiceServicer_to_server(OrderServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[OrderService] gRPC server started on port {port}")
    server.wait_for_termination()
 
 
def serve_kitchen_service(port: int = 50052):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    kitchen_pb_grpc.add_KitchenServiceServicer_to_server(KitchenServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[KitchenService] gRPC server started on port {port}")
    server.wait_for_termination()