# Plataforma Multi-Agent — Instrucciones del Proyecto

## Contexto general

Plataforma **faceless** de productos de IA que generan artefactos descargables (PDFs, DOCX) y los venden automáticamente. Un solo dominio actúa como paraguas de múltiples productos independientes. No hay atención a clientes, no hay cara pública, no hay reuniones. El sistema opera 24/7 sin intervención manual.

**Perfil del founder:** técnico solo, trabaja con Copilot + Claude + ChatGPT + Gemini como asistentes. Objetivo: ingresos pasivos en USD.

---

## Arquitectura del paraguas

```
TU_DOMINIO.com
├── cv.tudominio.com       → AgentCV (primer MVP)
├── audit.tudominio.com    → AgentAudit
├── legal.tudominio.com    → AgentLegal
├── docs.tudominio.com     → AgentDocs
├── brief.tudominio.com    → AgentBrief
└── seo.tudominio.com      → AgentSEO
```

Todos los productos comparten la misma infraestructura base definida en `agent-core-infra`.

---

## Stack tecnológico

| Capa | Tecnología | Hosting |
|---|---|---|
| Frontend | Next.js 15 App Router + TypeScript | Vercel |
| Agentes IA | Python + LangGraph + GPT-4o | Railway |
| Base de datos | Supabase (PostgreSQL) | Supabase Cloud |
| Storage artefactos | Cloudflare R2 | Cloudflare |
| Pagos | LemonSqueezy | LemonSqueezy Cloud |
| Emails | Resend | Resend Cloud |
| Analytics | Plausible | Railway o Plausible.io |

---

## Repos en GitHub

Organización: `github.com/TU_ORG/`

```
agent-core-infra        ← REPO 0 — infra compartida (construir primero)
agentcv                 ← Semana 1 — primer MVP
factura-bot-tg          ← Semana 1 — bot Telegram
agentaudit              ← Semana 2
menuqr-saas             ← Semana 2
agentlegal              ← Semana 3
api-pdf-parser          ← Semana 4
uptime-monitor          ← Semana 4
agentdocs               ← Semana 5
agentseo                ← Semana 5
agenda-bot-wa           ← Semana 6
api-email-validator     ← Semana 6
nextjs-saas-boilerplate ← Semana 7
```

**Total: 13 repos.** Cada repo de producto agrega `agent-core-infra` como git submodule en `/core`.

```bash
git submodule add https://github.com/TU_ORG/agent-core-infra.git core
```

---

## Repo 0 — agent-core-infra

Librería compartida. Todo producto la usa. Contiene:

```
lib/
├── payments/lemon_squeezy.py   # create_checkout(), verify_webhook()
├── storage/r2_client.py        # upload_and_sign(), signed_url()
├── email/resend_client.py      # send_delivery(), send_template()
├── email/templates/            # HTML templates: delivery, nurture, upsell
├── db/supabase_client.py       # insert(), update(), select_one(), upsert_lead()
└── ai/openai_client.py         # complete() con retry, rate limiting, cost tracking
```

---

## Estructura de cada producto multi-agent

```
producto/
├── agents/                     # Python — deploy en Railway
│   ├── main.py                 # FastAPI: /process, /status/{id} (SSE), /health
│   ├── pipeline.py             # LangGraph StateGraph con los agentes
│   ├── agents/
│   │   ├── agent_1.py          # Cada agente recibe y retorna parcial del state
│   │   ├── agent_2.py
│   │   └── delivery.py        # Último nodo: sube a R2, manda email, guarda en DB
│   ├── requirements.txt
│   └── railway.toml
└── app/                        # Next.js — deploy en Vercel
    └── api/
        ├── process/route.ts    # POST → forwards al backend Python
        ├── status/route.ts     # GET → proxea SSE stream
        └── webhook/route.ts    # POST → LemonSqueezy events
```

---

## Flujo end-to-end (igual en todos los productos)

```
1. Usuario llega a la landing
2. Sube archivo / ingresa texto
3. POST /api/process → job_id retornado
4. Frontend abre SSE: GET /api/status/{job_id}
5. Agentes corren en LangGraph (Railway):
   Agent1 → Agent2 → Agent3 → [AgentN-1 ‖ AgentN] → Delivery
6. Delivery:
   a. Sube artefactos a Cloudflare R2 (signed URL 48hs)
   b. Manda email con links via Resend
   c. Guarda job y lead en Supabase
7. Frontend muestra preview parcial gratis (hook para pago)
8. Usuario paga → LemonSqueezy webhook → job.paid = true → acceso completo
```

---

## Variables de entorno (compartidas en todos los productos)

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...        # Solo en backend
SUPABASE_ANON_KEY=eyJ...           # Frontend si se necesita

# Cloudflare R2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_BUCKET=agent-artifacts

# LemonSqueezy
LEMON_SQUEEZY_API_KEY=...
LEMON_STORE_ID=...
LEMON_WEBHOOK_SECRET=whsec_...

# Resend
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@tudominio.com
EMAIL_FROM_NAME=Nombre del producto

# App
FRONTEND_URL=https://producto.tudominio.com
AGENTS_API_URL=https://producto-agents.up.railway.app
```

---

## Schema de Supabase

```sql
-- Un schema por producto
CREATE SCHEMA IF NOT EXISTS agentcv;
CREATE SCHEMA IF NOT EXISTS agentaudit;
CREATE SCHEMA IF NOT EXISTS agentlegal;

-- Tabla de jobs genérica (replicar por producto)
CREATE TABLE agentcv.jobs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id        TEXT UNIQUE NOT NULL,
  user_email    TEXT,
  paid          BOOLEAN DEFAULT false,
  plan          TEXT DEFAULT 'free',
  status        TEXT DEFAULT 'processing',
  artifact_urls JSONB DEFAULT '{}',
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Leads unificados para todos los productos
CREATE TABLE public.leads (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email                 TEXT UNIQUE NOT NULL,
  source_product        TEXT,
  products_purchased    TEXT[] DEFAULT '{}',
  subscribed_newsletter BOOLEAN DEFAULT false,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Producto 1 — AgentCV (primer MVP, semana 1)

**Problema:** job seekers necesitan CVs optimizados para ATS pero no saben cómo. **Solución:** 5 agentes en paralelo transforman cualquier CV en un PDF profesional con score ATS en 30 segundos.

### Pipeline LangGraph

```
parse_cv → analyze_ats → rewrite_cv → [generate_pdf ‖ generate_insights] → deliver
```

| Agente | Modelo | Rol |
|---|---|---|
| Parser | GPT-4o-mini | PDF/DOCX → texto estructurado + secciones JSON |
| ATS Analyzer | GPT-4o-mini | Calcula score 0-100, keywords presentes/faltantes |
| Rewriter | GPT-4o | Reescribe cada sección con verbos de acción + keywords |
| Designer | WeasyPrint | Genera PDF profesional desde HTML/CSS |
| Insights | WeasyPrint | PDF de 1 página con análisis ATS y recomendaciones |
| Delivery | — | R2 upload + Resend email + Supabase update |

### Monetización

| Producto | Precio | Variante LS |
|---|---|---|
| ATS Score Report | $4 | LEMON_VARIANT_ATS_ONLY |
| CV Optimizado PDF | $7 | LEMON_VARIANT_FULL |
| CV + Insights Bundle | $12 | LEMON_VARIANT_BUNDLE |
| Pro mensual (ilimitado) | $19/mes | LEMON_VARIANT_PRO |

### Preview gratuita como hook
El ATS score (número) se muestra gratis. El PDF completo y el reporte requieren pago. El webhook de LemonSqueezy setea `job.paid = true` y libera los links de descarga.

---

## Convenciones de código

- **Python:** async/await en todo el backend. Pydantic para validación. `ruff` para linting.
- **TypeScript:** App Router de Next.js 15. Server Components por defecto, Client Components solo cuando se necesita estado/interactividad.
- **LangGraph state:** siempre `TypedDict`. Los agentes reciben el state completo y retornan solo los campos que modifican.
- **Errores:** cada agente tiene try/except. Los errores se propagan como `{"error": "mensaje"}` en el state y se loguean antes de retornar.
- **Secrets:** nunca en el código. Siempre en variables de entorno. `.env` en `.gitignore`.
- **Branching:** `main` protegida. Desarrollar en `dev` o branches de feature. PR para mergear.

---

## Monetización y lead gen (igual en todos los productos)

1. **Preview gratuita** → muestra resultado parcial → hook para pago
2. **LemonSqueezy checkout** → pago → webhook → acceso completo
3. **Email de entrega** → links con expiración 48hs (Resend)
4. **Secuencia nurture** → día 1, 3, 7 → upsell al plan pro o cross-sell otro producto
5. **Lead unificado** → `public.leads` → base de datos cross-producto

---

## Canales de adquisición por producto

| Producto | Canal principal |
|---|---|
| AgentCV | Reddit r/jobs, r/resumes, SEO "ai cv optimizer" |
| AgentAudit | Twitter devs, r/webdev, SEO "code review ai" |
| AgentLegal | Reddit r/freelance, SEO "nda generator free" |
| AgentBrief | Facebook grupos marketing LATAM |
| Menú QR | Facebook grupos restaurantes/gastronómicos LATAM |
| Bot Facturas | Telegram grupos finanzas personales, Reddit |
| APIs | RapidAPI marketplace (orgánico) |

---

## Orden de prioridad de construcción

```
Semana 0: Setup de accounts + agent-core-infra
Semana 1: AgentCV backend (Python/LangGraph) + Bot Facturas TG
Semana 2: AgentCV frontend (Next.js) + primer cliente real
Semana 3: AgentAudit + Menú QR
Semana 4: AgentLegal + API PDF Parser
Semana 5: SEO foundation + Product Hunt launch del mejor producto
Mes 2+:   AgentDocs, AgentSEO, AgentBrief, APIs restantes
```

---

## Lo que NO hacer

- No hablar con clientes (el sistema es 100% autoservicio)
- No buildear más de un producto a la vez hasta que el primero tenga tracción
- No commitear `.env` ni secrets al repo
- No usar Stripe directamente (LemonSqueezy maneja impuestos desde Argentina)
- No lanzar sin tener el flujo completo funcionando: upload → pago → entrega → email
