# Pendientes

## Seguridad / Integridad (AFIP + Telegram)

- [ ] Modo Telegram: evitar duplicación de emisión
  - Asegurar que exista **una sola instancia** del `telegram_bot.py` por ejecución (lock/PID file).
  - Endurecer `mark_issued` / flujo de emisión para que la transición desde `pending_approval` sea atómica (ideal: `UPDATE ... WHERE status='pending_approval'` y manejar `rowcount==0`).

