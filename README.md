# Studio Flow SaaS — CRM, Operacional & Financeiro (Piercing & Tatuagem)

Plataforma SaaS B2B **multi-tenant** voltada para estúdios de **Body Piercing** (MVP) e preparada de forma **modular** para ativação por estúdio do módulo de **Tatuagem** sem refatoração estrutural.

## Arquitetura do Monorepo

- `/backend`: Python 3.12+, FastAPI, SQLAlchemy 2.0 Async, Alembic, Pydantic v2, Argon2id (`pwdlib`), JWT em memória + Refresh Token rotativo em cookie `HttpOnly`.
- `/frontend`: React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query + componentes acessíveis inspirados em `shadcn/ui`.
- `docker-compose.yml`: PostgreSQL 16 + API FastAPI + Frontend Vite.

## Destaques da Fase 1

1. **Identidade Global + Multi-Estúdio (`users` + `studio_memberships`):**
   - Login único por e-mail e senha.
   - 1 vínculo ativo: emite sessão imediata para o `studio_id`.
   - 2+ vínculos ativos: exibe seletor de estúdio no login e permite troca de contexto em tempo real (`/api/v1/auth/switch-studio`).
2. **Isolamento Multi-Tenant Anti-IDOR:**
   - `with_loader_criteria` automático em `SELECT` ORM + `BaseTenantRepository` filtrando explicitamente `studio_id` em `SELECT`, `INSERT`, `UPDATE`, `SOFT DELETE` e `DELETE`.
3. **Governança Comercial SaaS:**
   - Controle de `subscription_status` (`TRIAL | ACTIVE | PAST_DUE | SUSPENDED`), `trial_ends_at`, `timezone` (padrão `America/Sao_Paulo`), `enabled_modules` e `commission_deducts_payment_fee`.
   - Bloqueio automático de estúdios suspensos (`STUDIO_SUSPENDED`) ou inativos (`STUDIO_INACTIVE`).
   - SuperAdmin global (`is_superadmin`) via CLI/seed e painel `/admin`.

## Como Subir via Docker

```bash
cp .env.example .env
docker compose up --build -d
```

- **Frontend:** http://localhost:5173
- **API / Swagger Docs:** http://localhost:8000/docs

### Criar ou Promover SuperAdmin via CLI

```bash
docker compose exec backend python -m app.cli seed-superadmin
```

## Como Rodar os Testes Automatizados (Pytest)

Via container Docker:

```bash
docker compose exec backend pytest -v
```

Ou localmente via ambiente virtual Python (`backend/.venv`):

```powershell
cd backend
.\.venv\Scripts\pytest.exe -v
```
