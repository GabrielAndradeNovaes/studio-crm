# Studio Flow SaaS — CRM, Operacional & Financeiro (Piercing & Tatuagem)

Plataforma SaaS B2B **multi-tenant** voltada para estúdios de **Body Piercing** (MVP) e preparada de forma **modular** para ativação por estúdio do módulo de **Tatuagem** sem refatoração estrutural.

## Arquitetura do Monorepo

- `/backend`: Python 3.12+, FastAPI, SQLAlchemy 2.0 Async, Alembic, Pydantic v2, Argon2id (`pwdlib`), JWT em memória + Refresh Token rotativo em cookie `HttpOnly`.
- `/frontend`: React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query + componentes acessíveis inspirados em `shadcn/ui`.
- `docker-compose.yml`: PostgreSQL 16 + API FastAPI + Frontend Vite.

## Destaques das Fases 1 e 2

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
4. **CRM de Clientes (`clients`):**
   - Busca rápida por nome, e-mail ou WhatsApp normalizado (índice único parcial ativo por estúdio), tags e origem do lead.
   - Cálculo de maioridade no fuso do estúdio e exigência obrigatória de dados do responsável legal para menores de 18 anos.
5. **Módulo Piercing — Catálogo e Estoque/Kardex (`piercing_services`, `piercing_products`, `inventory_movements`):**
   - Catálogo de perfurações por local anatômico com duração, preço base e recomendação de downsize.
   - Estoque de joias (Titânio ASTM F136, Ouro 18k, calibre, tamanho) e insumos pós-piercing com Kardex imutável (`SELECT ... FOR UPDATE`), bloqueio de edição direta de saldo e omissão estrita de custos (`cost_price` / `unit_cost_snapshot`) para `RECEPTION` e `PROFESSIONAL`.

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
