# agent-core-infra

Librería compartida para la plataforma multi-agente. Todos los productos la consumen como git submodule.

## Módulos

| Módulo | Descripción |
|--------|-------------|
| `lib/ai` | Cliente OpenAI async con retry y cost tracking por producto |
| `lib/db` | Cliente Supabase singleton (CRUD + upsert leads) |
| `lib/storage` | Cloudflare R2: upload, signed URLs con TTL, delete |
| `lib/payments` | Factory de proveedores de pago (LemonSqueezy implementado) |
| `lib/email` | Resend: envío transaccional, templates Jinja2, secuencias nurture |
| `lib/agents` | BaseAgent, estado LangGraph, retry exponencial, SSE streaming |
| `lib/pdf` | WeasyPrint + Jinja2: render de reportes y documentos a PDF |

## Instalación en un producto

```bash
# Como submodule
git submodule add https://github.com/aac-2502/agent-core-infra.git core

# Instalar como paquete editable (dev local)
pip install -e ./core

# Para Railway/producción, en requirements.txt:
# git+https://github.com/aac-2502/agent-core-infra.git#egg=agent-core-infra
```

## Variables de entorno requeridas

```bash
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
R2_ACCOUNT_ID=
R2_ACCESS_KEY=
R2_SECRET_KEY=
R2_BUCKET=agent-artifacts
LEMON_SQUEEZY_API_KEY=
LEMON_STORE_ID=
LEMON_WEBHOOK_SECRET=
PAYMENT_PROVIDER=lemon_squeezy
RESEND_API_KEY=
EMAIL_FROM_DOMAIN=noreply@yourdomain.com
```

## Uso rápido

```python
from lib.ai import complete
from lib.storage import upload_and_sign
from lib.email import send_delivery
from lib.pdf import render_report
from lib.agents import BaseAgent

# Completar con GPT-4o-mini
text = await complete([{"role": "user", "content": "Hola"}], product="agentcv")

# Subir PDF y obtener URL firmada (48h)
url = upload_and_sign("agentcv/job123/cv.pdf", pdf_bytes)

# Mandar email de entrega
await send_delivery("user@example.com", "AgentCV", [{"name": "CV", "url": url}])

# Agente custom
class MiAgente(BaseAgent):
    name = "mi_agente"
    async def run(self, state: dict) -> dict:
        return {"campo": "valor"}
```

## Estructura

```
lib/
├── agents/      BaseAgent, state TypedDict, retry, SSE streaming
├── ai/          OpenAI client
├── db/          Supabase client
├── email/       Resend client + templates + sequences
├── payments/    Factory + LemonSqueezy
├── pdf/         WeasyPrint + templates Jinja2
└── storage/     Cloudflare R2
```

## Desarrollo

```bash
pip install -e ".[dev]"
ruff check lib/
pytest tests/
```
