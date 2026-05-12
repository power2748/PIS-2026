-- Сводка зала: свободные / занятые / ожидающие оплаты столики
CREATE MATERIALIZED VIEW hall_summary AS
SELECT
    t.table_id,
    t.table_label,
    t.capacity,
    t.status,
    t.active_order_id,
    t.guests,
    t.occupied_since,
    EXTRACT(EPOCH FROM (NOW() - t.occupied_since)) / 60 AS occupied_minutes,
    ov.total_amount,
    ov.items_count,
    ov.status_label,
    ov.eta_minutes
FROM table_views t
LEFT JOIN order_views ov
    ON t.active_order_id = ov.order_id
ORDER BY t.table_id;
 
-- Уникальный индекс для REFRESH CONCURRENTLY
CREATE UNIQUE INDEX ON hall_summary (table_id);
 
-- Обновлять каждые 30 секунд (pg_cron или application scheduler)
-- SELECT cron.schedule('refresh-hall', '30 seconds', 'REFRESH MATERIALIZED VIEW CONCURRENTLY hall_summary');
```