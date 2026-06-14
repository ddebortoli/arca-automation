# arca-automation

Automates MercadoPago income → AFIP Factura C invoicing, with optional Telegram approval and pluggable logging backends.

## Quick start

```bash
uv sync
cp .env.example .env   # configure credentials
uv run main.py
```

## Environment variables

```env
# MercadoPago
MP_ACCESS_TOKEN=
MP_USER_ID=

# AFIP
AFIP_CUIT=
AFIP_CERT_PATH=certs/cert.crt
AFIP_KEY_PATH=certs/private.key

# Approval (optional)
APPROVAL_MODE=auto          # auto | telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Observability (optional — defaults to stdout)
OBSERVABILITY_BACKEND=stdio # stdio | logfire | sentry
SERVICE_NAME=arca-automation
LOG_LEVEL=INFO
LOGFIRE_TOKEN=              # required if backend=logfire
SENTRY_DSN=                 # required if backend=sentry
```

## Running

| Command | Purpose |
|---|---|
| `uv run main.py` | Sync MP payments and invoice (or send for approval) |
| `uv run telegram_bot.py` | Approval worker (required when `APPROVAL_MODE=telegram`) |

Cron example:

```cron
0 2 * * * cd /path/to/arca-automation && uv run main.py >> logs/cron.log 2>&1
```

## Observability

Logging uses Python's stdlib `logging` throughout. The backend is chosen once at startup via `OBSERVABILITY_BACKEND` — no code changes needed to switch providers.

| Backend | Config | Install |
|---|---|---|
| `stdio` (default) | No extra vars | `uv sync` |
| `logfire` | `LOGFIRE_TOKEN` | `uv sync --extra logfire` |
| `sentry` | `SENTRY_DSN` | `uv sync --extra sentry` |

### Examples

**Logfire:**

```env
OBSERVABILITY_BACKEND=logfire
LOGFIRE_TOKEN=your-write-token
SERVICE_NAME=arca-automation
```

**Stdout only (no external provider):**

```env
OBSERVABILITY_BACKEND=stdio
```

Or omit `OBSERVABILITY_BACKEND` entirely — stdout is the default.

**Sentry:**

```env
OBSERVABILITY_BACKEND=sentry
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
```

Both `main.py` and `telegram_bot.py` call `configure_observability()` at startup.

## Payment statuses

| Status | Meaning |
|---|---|
| `fetched` | New from MP, awaiting processing |
| `pending_approval` | Telegram message sent |
| `issued` | Invoiced with CAE |
| `failed` | AFIP error (retries) |
| `rejected` | User rejected (terminal) |

## Testing

```bash
uv run pytest
```
