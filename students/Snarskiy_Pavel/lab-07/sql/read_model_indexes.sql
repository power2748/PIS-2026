-- order_views: поиск по столику и статусу (карта зала)
CREATE INDEX CONCURRENTLY idx_order_views_table_status
    ON order_views (table_id, status)
    WHERE status NOT IN ('PAID', 'CANCELLED');
 
-- order_views: поиск активных заказов официанта
CREATE INDEX CONCURRENTLY idx_order_views_waiter_active
    ON order_views (waiter_id, created_at DESC)
    WHERE status NOT IN ('PAID', 'CANCELLED');
 
-- kitchen_dashboard_views: фильтр по станции и приоритету (KDS-дисплей)
CREATE INDEX CONCURRENTLY idx_kitchen_dashboard_station_priority
    ON kitchen_dashboard_views (station, priority DESC, created_at ASC)
    WHERE status = 'PENDING';
 
-- revenue_views: аналитика по дате
CREATE INDEX CONCURRENTLY idx_revenue_date_hour
    ON revenue_views (date, hour);
 
-- table_views: быстрый поиск свободных столиков
CREATE INDEX CONCURRENTLY idx_table_views_status
    ON table_views (status);