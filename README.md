# arca-automation — Project Documentation
Automates invoicing for MercadoPago income payments through AFIP (Argentina tax authority). Fetches transfers from MercadoPago, optionally asks for human approval via Telegram, and issues Factura C vouchers to Consumidor Final through AFIP WSFE.

Overview
Layer	Responsibility
Domain	Models, ports (interfaces), business rules
Use cases	Workflow orchestration
Providers	External integrations (MercadoPago, AFIP, Telegram)
Repository	SQLite persistence
Bootstrap	Dependency wiring from environment
The design follows ports & adapters: use cases depend on protocols (MercadoPagoPort, AfipPort, ApprovalPort), not concrete implementations.

Architecture
Entry Points
Use Cases
Ports
Providers
payments.db
main.py - cron sync
telegram_bot.py - approval worker
ProcessPaymentsUseCase
IssueInvoiceUseCase
RejectPaymentUseCase
PostponePaymentUseCase
MercadoPagoPort
AfipPort
ApprovalPort
HttpMercadoPagoProvider
AfipAuthProvider - WSAA
AfipElectronicBillingProvider - WSFE
AutoApprovalProvider
TelegramApprovalProvider
Payment lifecycle
new MP payment
APPROVAL_MODE=telegram
APPROVAL_MODE=auto + AFIP OK
APPROVAL_MODE=auto + AFIP error
Telegram Confirm
Telegram Reject (terminal)
Telegram Postpone
retry on next run
fetched
pending_approval
issued
failed
rejected
Status	Meaning	Retries?
fetched	Seen from MP, not yet invoiced or re-offered	Yes
pending_approval	Telegram message sent, awaiting decision	No until you act
issued	CAE obtained from AFIP	—
failed	AFIP technical error	Yes (stays out of auto queue until reset)
rejected	User rejected via Telegram	No — terminal
Project structure
arca-automation/
├── main.py                 # Cron/sync entry point
├── telegram_bot.py         # Telegram approval worker (long-running)
├── payments.db             # SQLite state (created at runtime)
├── certs/                  # AFIP certificate + private key (gitignored)
├── src/
│   ├── bootstrap.py        # Config loading + factory functions
│   ├── domain/
│   │   ├── models.py       # MercadoPagoPayment, IssuedInvoice, InvoicePreview
│   │   ├── ports.py        # Protocol interfaces
│   │   ├── config.py       # ApprovalConfig
│   │   ├── exceptions.py
│   │   ├── datetime_utils.py
│   │   └── income.py       # MP income detection rules
│   ├── use_cases/
│   │   ├── process_payments.py
│   │   ├── issue_invoice.py
│   │   ├── reject_payment.py
│   │   └── postpone_payment.py
│   ├── providers/
│   │   ├── mercadopago.py
│   │   ├── afip/
│   │   │   ├── auth.py           # WSAA authentication
│   │   │   ├── afip_electronic_billing.py  # WSFE invoicing
│   │   │   └── transport.py      # SSL fix for AFIP legacy DH
│   │   └── approval/
│   │       ├── auto.py
│   │       └── telegram.py
│   └── repositories/
│       └── payment_repository.py
└── tests/
Requirements
Python ≥ 3.13
uv (package manager)
OpenSSL (for WSAA CMS signing)
MercadoPago API access token
AFIP production certificate + private key
(Optional) Telegram bot token + chat ID
Dependencies
Package	Purpose
httpx	MercadoPago + Telegram HTTP
zeep	AFIP SOAP (WSAA, WSFE)
pydantic	Domain models
python-dotenv	.env loading
cryptography, lxml	zeep / SSL stack
Setup
1. Install
git clone <repo>
cd arca-automation
uv sync
2. AFIP certificates
Place your AFIP production cert and key in certs/ (directory is gitignored):

certs/cert.crt      # or your .crt filename
certs/private.key
3. Environment variables
Create a .env file at the project root:

# MercadoPago
MP_ACCESS_TOKEN=APP_USR-...
MP_USER_ID=123456789
# AFIP
AFIP_CUIT=20123456789
AFIP_CERT_PATH=certs/cert.crt
AFIP_KEY_PATH=certs/private.key
# Approval (optional)
APPROVAL_MODE=auto          # or "telegram"
TELEGRAM_BOT_TOKEN=         # required if mode=telegram
TELEGRAM_CHAT_ID=           # required if mode=telegram
4. Telegram setup (if using manual approval)
Create a bot via @BotFather
Send a message to your bot
Get your chat_id from https://api.telegram.org/bot<TOKEN>/getUpdates
Set APPROVAL_MODE=telegram, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Running
Auto mode (no Telegram)
uv run main.py
Invoices are issued immediately for all fetched payments.

Telegram approval mode
Two processes:

Terminal 1 — bot (always on):

uv run telegram_bot.py
Terminal 2 — sync (cron or manual):

uv run main.py
Cron example (23:00 ART ≈ 02:00 UTC)
0 2 * * * cd /path/to/arca-automation && uv run main.py >> logs/cron.log 2>&1
For Telegram mode, run telegram_bot.py as a systemd service or similar so it stays alive between syncs.

Workflows
Sync pipeline (main.py → ProcessPaymentsUseCase)
Compute current-month date range in ART (NOW-NDAYS … NOW)
Fetch income payments from MercadoPago (paginated)
Insert new payments as fetched
For each fetched payment:
auto: call AFIP → issued or failed
telegram: build preview, send Telegram message → pending_approval
Telegram bot (telegram_bot.py)
Polls Telegram for inline button callbacks:

Button	Action	Result
✅ Confirmar	IssueInvoiceUseCase	issued or failed
❌ Rechazar	RejectPaymentUseCase	rejected (terminal)
⏸ Posponer	PostponePaymentUseCase	back to fetched; re-offered on next sync
Multiple payments → one Telegram message each, sent in the same sync run. Decisions are independent and can happen in any order.

AFIP invoice defaults
Configured in src/providers/afip/afip_electronic_billing.py:

Field	Value	Meaning
CbteTipo	11	Factura C
PtoVta	2	Point of sale 2
Concepto	2	Servicios
DocTipo	99	Consumidor Final
DocNro	0	No document number
CondicionIVAReceptorId	5	Consumidor Final
ImpTotal / ImpNeto	payment amount	No IVA breakdown
ImpIVA	0	Monotributo-style
MonId	PES	Argentine pesos
Service dates (FchServDesde, FchServHasta, FchVtoPago, CbteFch) use the MercadoPago payment date.

AFIP authentication
AfipAuthProvider (src/providers/afip/auth.py):

Builds a Login Ticket Request (TRA) in Argentina local time
Signs it with OpenSSL CMS
Exchanges it at WSAA for token + sign
Caches credentials and renews ~5 minutes before expiration
WSFE calls reuse cached credentials via AfipElectronicBillingProvider.

Database schema
SQLite table payments:

Column	Type	Description
mp_payment_id	INTEGER PK	MercadoPago payment ID
status	TEXT	Lifecycle status
transaction_amount	REAL	Amount in ARS
date_created	TEXT	Payment datetime (ISO)
cae	TEXT	AFIP CAE (when issued)
cae_expiry	TEXT	CAE expiration
invoice_number	INTEGER	Voucher number
error_message	TEXT	Failure/rejection reason
created_at / updated_at	TEXT	Audit timestamps
Testing
uv run pytest          # all tests
uv run pytest -q       # quiet
Coverage includes MercadoPago income rules, AFIP auth caching, approval flow, and Telegram message formatting.

Extensibility (future multi-tenant)
The codebase is structured for per-user configuration:

ApprovalPort — swap auto / telegram / future channels
ApprovalConfig — feature flags per tenant
bootstrap.py — composition root; can be extended to load TenantConfig from DB
Ports isolate MercadoPago, AFIP, and approval from business logic
Phase 2 would add tenant_id to tables and a web UI for per-user settings.

Troubleshooting
Issue	Cause / fix
DH_KEY_TOO_SMALL SSL error	Handled by src/providers/afip/transport.py (SECLEVEL=1)
generationTime inválido	TRA must use ART, not UTC — fixed in auth.py
Payments stuck in fetched	Telegram mode: run telegram_bot.py
Payments stuck in pending_approval	Decide in Telegram, or postpone to retry later
rejected won't retry	By design — terminal status
Bot button does nothing	Restart telegram_bot.py after code changes
Cert not found	Check AFIP_CERT_PATH / AFIP_KEY_PATH in .env
Entry points summary
Command	When to run	Purpose
uv run main.py	Cron / manual	Fetch MP payments, submit for approval or auto-invoice
uv run telegram_bot.py	Always (telegram mode)	Handle approve / reject / postpone callbacks
