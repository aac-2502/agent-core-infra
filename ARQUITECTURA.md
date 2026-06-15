# Arquitectura Técnica Completa — Paraguas Multi-Agent

## Índice
1. [Repo 0 — agent-core-infra](#repo-0)
2. [Arquitectura AgentCV (primer MVP)](#agentcv)
3. [Infraestructura compartida por capa](#infra)
4. [Flujo de datos end-to-end](#flujo)
5. [Deploy y DevOps](#deploy)
6. [Secuencias de email y lead gen](#email)
7. [Estrategia GitHub](#github)

---

## 1. Repo 0 — agent-core-infra {#repo-0}

**Construir PRIMERO. Todo lo demás depende de esto.**

```
agent-core-infra/
├── lib/
│   ├── payments/
│   │   ├── lemon_squeezy.py       # Cliente LemonSqueezy
│   │   ├── webhook_handler.py     # Verifica firma y enruta eventos
│   │   └── checkout.py            # Genera links de checkout por producto
│   ├── pdf/
│   │   ├── generator.py           # WeasyPrint wrapper con templates base
│   │   ├── templates/
│   │   │   ├── base.html          # Template HTML base para todos los PDFs
│   │   │   ├── report.html        # Template para reportes (AgentAudit, AgentSEO)
│   │   │   └── document.html      # Template para docs (AgentLegal, AgentDocs)
│   │   └── styles/
│   │       └── base.css           # CSS compartido para PDFs
│   ├── storage/
│   │   ├── r2_client.py           # Cloudflare R2: upload, signed URLs, delete
│   │   └── artifact_manager.py    # Gestión de artefactos con expiración
│   ├── email/
│   │   ├── resend_client.py       # Cliente Resend configurado
│   │   ├── templates/
│   │   │   ├── delivery.html      # Email de entrega del artefacto
│   │   │   ├── confirmation.html  # Confirmación de compra
│   │   │   ├── nurture_1.html     # Email nurturing día 1
│   │   │   └── upsell.html        # Upsell cross-producto
│   │   └── sequences.py           # Orquestación de secuencias
│   ├── agents/
│   │   ├── base_agent.py          # Clase base para todos los agentes
│   │   ├── state.py               # Schema de estado compartido LangGraph
│   │   ├── retry.py               # Lógica de retry con backoff exponencial
│   │   └── streaming.py           # SSE streaming para el frontend
│   ├── ai/
│   │   ├── openai_client.py       # Cliente OpenAI con rate limiting
│   │   ├── cost_tracker.py        # Tracking de costo por producto/usuario
│   │   └── prompts/               # Prompts base reutilizables
│   └── db/
│       ├── supabase_client.py     # Cliente Supabase singleton
│       └── models.py              # Schemas Pydantic compartidos
├── pyproject.toml                 # Dependencias Python
└── README.md
```

### Instalación como submodule en cada repo de producto:
```bash
git submodule add https://github.com/TU_ORG/agent-core-infra.git core
```

---

## 2. AgentCV — Arquitectura Completa (Primer MVP) {#agentcv}

### Estructura del repo

```
agentcv/
├── app/                           # Next.js 15 App Router
│   ├── page.tsx                   # Landing con upload form
│   ├── result/[jobId]/page.tsx    # Página de resultado con SSE streaming
│   ├── api/
│   │   ├── process/route.ts       # POST: inicia el pipeline de agentes
│   │   ├── status/[jobId]/route.ts # GET: SSE stream del progreso
│   │   └── webhook/route.ts       # POST: LemonSqueezy webhook
│   └── components/
│       ├── CVUploader.tsx         # Dropzone para PDF/DOCX
│       ├── ProgressStream.tsx     # Visualización en tiempo real del pipeline
│       └── PreviewGate.tsx        # Preview parcial + CTA de pago
├── agents/                        # Python + LangGraph
│   ├── main.py                    # FastAPI app
│   ├── pipeline.py                # Definición del grafo LangGraph
│   ├── agents/
│   │   ├── parser.py              # Agent 1: extrae texto del PDF/DOCX
│   │   ├── ats_analyzer.py        # Agent 2: calcula ATS score
│   │   ├── rewriter.py            # Agent 3: reescribe con GPT-4o
│   │   ├── designer.py            # Agent 4: genera PDF con template
│   │   └── insights.py            # Agent 5: genera reporte de mejoras
│   └── core -> ../core            # Symlink al submodule agent-core-infra
├── railway.toml                   # Config Railway para el backend Python
└── vercel.json                    # Config Vercel para el frontend Next.js
```

### Pipeline LangGraph

```python
# agents/pipeline.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
from agents.parser import parse_cv
from agents.ats_analyzer import analyze_ats
from agents.rewriter import rewrite_cv
from agents.designer import generate_pdf
from agents.insights import generate_insights
from core.lib.storage.r2_client import upload_artifact
from core.lib.email.resend_client import send_delivery_email

class CVState(TypedDict):
    job_id: str
    user_email: str
    raw_file_bytes: bytes
    file_type: str          # "pdf" | "docx"
    job_description: Optional[str]
    extracted_text: str
    ats_score: int
    ats_keywords_missing: list[str]
    rewritten_sections: dict
    pdf_bytes: bytes
    insights_pdf_bytes: bytes
    artifact_urls: dict
    error: Optional[str]

def build_pipeline():
    graph = StateGraph(CVState)

    # Nodos
    graph.add_node("parse", parse_cv)
    graph.add_node("ats_analyze", analyze_ats)
    graph.add_node("rewrite", rewrite_cv)
    # Los últimos dos corren en paralelo
    graph.add_node("generate_pdf", generate_pdf)
    graph.add_node("generate_insights", generate_insights)
    graph.add_node("upload_and_deliver", upload_and_deliver)

    # Edges
    graph.set_entry_point("parse")
    graph.add_edge("parse", "ats_analyze")
    graph.add_edge("ats_analyze", "rewrite")
    # Fan-out: rewrite → dos agentes en paralelo
    graph.add_edge("rewrite", "generate_pdf")
    graph.add_edge("rewrite", "generate_insights")
    # Fan-in: ambos deben terminar antes de upload
    graph.add_edge(["generate_pdf", "generate_insights"], "upload_and_deliver")
    graph.add_edge("upload_and_deliver", END)

    return graph.compile()

async def upload_and_deliver(state: CVState):
    # Sube los artefactos a R2
    cv_url = await upload_artifact(
        key=f"agentcv/{state['job_id']}/cv_optimizado.pdf",
        data=state["pdf_bytes"],
        expires_in_hours=48
    )
    insights_url = await upload_artifact(
        key=f"agentcv/{state['job_id']}/insights.pdf",
        data=state["insights_pdf_bytes"],
        expires_in_hours=48
    )
    # Manda el email con los links de descarga
    await send_delivery_email(
        to=state["user_email"],
        template="delivery",
        context={
            "product": "AgentCV",
            "downloads": [
                {"name": "CV Optimizado", "url": cv_url},
                {"name": "Insights Report", "url": insights_url},
            ],
            "ats_score": state["ats_score"]
        }
    )
    return {"artifact_urls": {"cv": cv_url, "insights": insights_url}}
```

### Agent Parser

```python
# agents/agents/parser.py
import PyMuPDF as fitz
from docx import Document
import io

async def parse_cv(state: CVState) -> dict:
    if state["file_type"] == "pdf":
        doc = fitz.open(stream=state["raw_file_bytes"], filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
    else:
        doc = Document(io.BytesIO(state["raw_file_bytes"]))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    return {"extracted_text": text}
```

### Agent ATS Analyzer

```python
# agents/agents/ats_analyzer.py
from openai import AsyncOpenAI
import json

client = AsyncOpenAI()

PROMPT = """Analiza este CV y, dado el job description (si existe), devuelve JSON:
{
  "ats_score": int (0-100),
  "keywords_present": ["lista de keywords encontradas"],
  "keywords_missing": ["lista de keywords importantes no encontradas"],
  "sections_detected": ["Experiencia", "Educación", "Skills", ...],
  "main_weaknesses": ["descripción corta de cada debilidad"]
}
Solo JSON, sin explicación."""

async def analyze_ats(state: CVState) -> dict:
    context = f"CV:\n{state['extracted_text'][:6000]}"
    if state.get("job_description"):
        context += f"\n\nJOB DESCRIPTION:\n{state['job_description'][:2000]}"

    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # Mini para el análisis, 4o para el rewrite
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": context}
        ],
        response_format={"type": "json_object"}
    )
    data = json.loads(response.choices[0].message.content)
    return {
        "ats_score": data["ats_score"],
        "ats_keywords_missing": data["keywords_missing"]
    }
```

### FastAPI endpoint con SSE streaming

```python
# agents/main.py
from fastapi import FastAPI, UploadFile
from fastapi.responses import StreamingResponse
from pipeline import build_pipeline
import asyncio, json, uuid

app = FastAPI()
pipeline = build_pipeline()
jobs = {}  # En producción: Redis

@app.post("/process")
async def process_cv(file: UploadFile, job_description: str = "", email: str = ""):
    job_id = str(uuid.uuid4())
    state = {
        "job_id": job_id,
        "user_email": email,
        "raw_file_bytes": await file.read(),
        "file_type": "pdf" if file.content_type == "application/pdf" else "docx",
        "job_description": job_description,
    }
    jobs[job_id] = {"status": "processing", "progress": 0}
    asyncio.create_task(run_pipeline(job_id, state))
    return {"job_id": job_id}

@app.get("/status/{job_id}")
async def status_stream(job_id: str):
    async def event_generator():
        while True:
            job = jobs.get(job_id, {})
            yield f"data: {json.dumps(job)}\n\n"
            if job.get("status") in ["done", "error"]:
                break
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def run_pipeline(job_id: str, state: dict):
    try:
        result = await pipeline.ainvoke(state)
        jobs[job_id] = {"status": "done", "urls": result["artifact_urls"]}
    except Exception as e:
        jobs[job_id] = {"status": "error", "message": str(e)}
```

### Webhook LemonSqueezy (Next.js)

```typescript
// app/api/webhook/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const supabase = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SERVICE_KEY!)

export async function POST(req: NextRequest) {
  const body = await req.text()
  const sig = req.headers.get('x-signature')

  // Verificar firma LemonSqueezy
  const hash = crypto.createHmac('sha256', process.env.LEMON_WEBHOOK_SECRET!).update(body).digest('hex')
  if (hash !== sig) return NextResponse.json({ error: 'Invalid signature' }, { status: 401 })

  const event = JSON.parse(body)
  if (event.meta.event_name === 'order_created') {
    const { job_id, email } = event.meta.custom_data
    // Actualizar estado en Supabase: el usuario pagó, liberar descarga completa
    await supabase.from('cv_jobs').update({ paid: true, email }).eq('job_id', job_id)
  }

  return NextResponse.json({ ok: true })
}
```

---

## 3. Infraestructura compartida por capa {#infra}

### Supabase — Schema unificado

```sql
-- Una DB, schemas por producto
CREATE SCHEMA agentcv;
CREATE SCHEMA agentaudit;
CREATE SCHEMA agentlegal;

-- Tabla de jobs genérica (cada producto la extiende)
CREATE TABLE agentcv.jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_email TEXT,
  paid BOOLEAN DEFAULT false,
  plan TEXT DEFAULT 'free',   -- 'ats_only' | 'full' | 'bundle' | 'pro'
  artifact_urls JSONB,
  ats_score INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '48 hours'
);

-- Leads unificados (cross-producto)
CREATE TABLE public.leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  source_product TEXT,          -- 'agentcv' | 'agentaudit' | etc.
  products_purchased TEXT[],
  subscribed_newsletter BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Cloudflare R2 — Gestión de artefactos

```python
# core/lib/storage/r2_client.py
import boto3
from datetime import datetime, timedelta

r2 = boto3.client(
    's3',
    endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    region_name='auto'
)

async def upload_artifact(key: str, data: bytes, expires_in_hours: int = 48) -> str:
    r2.put_object(Bucket=BUCKET_NAME, Key=key, Body=data, ContentType='application/pdf')
    url = r2.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': key},
        ExpiresIn=expires_in_hours * 3600
    )
    return url
```

---

## 4. Flujo de datos end-to-end {#flujo}

```
Usuario en tudominio.com
        │
        ▼
[Next.js Frontend — Vercel]
  Upload archivo → POST /api/process
        │
        ▼ (job_id retornado)
[SSE Stream — GET /api/status/{job_id}]
  Muestra progreso en tiempo real
        │
        ▼
[FastAPI + LangGraph — Railway]
  Agent 1: Parser  →  Agent 2: ATS
          ↓
  Agent 3: Rewriter
     ↙         ↘
Agent 4: PDF  Agent 5: Insights
     ↘         ↙
  upload_and_deliver
        │
        ▼
[Cloudflare R2]
  Artefactos con signed URL 48hs
        │
        ▼
[Resend]
  Email de entrega con links
        │
        ▼
[Supabase]
  job.paid = false → mostrar preview
  (Usuario ve ATS score gratis)
        │
        ▼ (quiere el PDF completo)
[LemonSqueezy Checkout]
  Pago procesado
        │
        ▼
[Webhook → /api/webhook]
  job.paid = true
  Lead guardado en public.leads
        │
        ▼
[Email delivery + nurture sequence]
  Día 1: entrega del artefacto
  Día 3: tips de optimización de CV
  Día 7: upsell AgentLegal ("¿Tenés contrato freelance?")
```

---

## 5. Deploy y DevOps {#deploy}

### Railway (backend Python por producto)

```toml
# railway.toml
[build]
builder = "dockerfile"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
```

### Vercel (frontend Next.js por producto)

```json
// vercel.json
{
  "env": {
    "AGENTS_API_URL": "@agentcv-agents-url",
    "SUPABASE_URL": "@supabase-url",
    "LEMON_WEBHOOK_SECRET": "@lemon-secret"
  },
  "functions": {
    "app/api/**": { "maxDuration": 60 }
  }
}
```

### Variables de entorno por producto

```bash
# Compartidas (todas usan las mismas)
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
R2_ACCOUNT_ID=...
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
RESEND_API_KEY=re_...
LEMON_SQUEEZY_API_KEY=...
LEMON_WEBHOOK_SECRET=...

# Por producto (solo cambia el producto_id)
PRODUCT_ID=agentcv
LEMON_PRODUCT_VARIANT_ATS=123456
LEMON_PRODUCT_VARIANT_FULL=123457
LEMON_PRODUCT_VARIANT_BUNDLE=123458
```

---

## 6. Secuencias de email y lead gen {#email}

### Secuencia AgentCV (Resend)

```python
# core/lib/email/sequences.py
SEQUENCES = {
    "agentcv_free": [
        # Inmediato
        {"delay_hours": 0, "template": "cv_ats_score", "subject": "Tu ATS Score: {score}/100"},
        # Día 1
        {"delay_hours": 24, "template": "cv_tips_1", "subject": "3 errores que detectamos en tu CV"},
        # Día 3
        {"delay_hours": 72, "template": "cv_upsell", "subject": "Ver el CV optimizado completo →"},
        # Día 7
        {"delay_hours": 168, "template": "cross_sell_legal", "subject": "¿Tenés un contrato freelance actualizado?"},
    ],
    "agentcv_paid": [
        {"delay_hours": 0, "template": "cv_delivery", "subject": "Tu CV optimizado está listo ↓"},
        {"delay_hours": 72, "template": "cv_followup", "subject": "¿Ya lo enviaste? Tip para la entrevista"},
        {"delay_hours": 240, "template": "agentaudit_upsell", "subject": "¿Tenés código que revisar antes de una entrevista técnica?"},
    ]
}
```

---

## 7. Estrategia GitHub {#github}

### Orden de creación de repos

```
Semana 0: agent-core-infra       ← PRIMERO, siempre
Semana 1: agentcv                ← Primer MVP
Semana 1: factura-bot-tg         ← En paralelo, 3 días
Semana 2: agentaudit             ← Segundo producto
Semana 2: menuqr-saas            ← Micro-SaaS simple
Semana 3: agentlegal             ← Tercer agente
Semana 4: api-pdf-parser         ← API para RapidAPI
Semana 4: uptime-monitor         ← MRR recurrente
Semana 5: agentdocs              ← Para devs
Semana 5: agentseo               ← Para SEOs/bloggers
Semana 6: agenda-bot-wa          ← Bot profesionales
Semana 6: api-email-validator    ← API simple
Semana 7: nextjs-saas-boilerplate ← Producto digital
```

### Convenciones en todos los repos

- `main` — producción, protegida
- `dev` — desarrollo activo
- PR antes de mergear a main
- `.env.example` siempre presente, `.env` en `.gitignore`
- `Makefile` con comandos: `make dev`, `make build`, `make deploy`

### Total de repos: 14
- 1 infra compartida
- 6 productos multi-agent
- 3 micro-SaaS
- 2 bots
- 2 APIs
- 1 producto digital
```
