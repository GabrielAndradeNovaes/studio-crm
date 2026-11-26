---
trigger: always_on
description: Diretrizes permanentes de governança Git, segurança e qualidade do projeto SaaS CRM Piercing & Tattoo.
---

# Regras Permanentes do Projeto (SaaS CRM Piercing & Tatuagem)

Estas regras são obrigatórias e permanentes para **todas** as tarefas, fases e correções executadas neste workspace.

## Regra 1 — Commit e Push Automáticos após Alterações

1. **Fluxo Git Obrigatório ao Finalizar Alterações:**
   - Ao concluir qualquer conjunto de alterações, feature, correção ou fase, execute automaticamente:
     1. `git status` (inspeção de arquivos modificados/novos)
     2. `git add` (apenas arquivos rastreáveis e seguros do escopo)
     3. `git commit` seguindo o padrão **Conventional Commits** (ex.: `feat(phase2): ...`, `fix(inventory): ...`, `chore(rules): ...`)
     4. `git push` para a branch atual.
2. **Trava de Segurança (Anti-Leak):**
   - **Jamais** faça commit ou push de arquivos sensíveis ou artefatos locais (`.env`, `.env.*` exceto `.env.example`, chaves privadas, certificados, bancos SQLite locais, `.venv/`, `node_modules/`, `frontend/dist/`).
   - Sempre valide que o `.gitignore` está protegendo esses caminhos **antes** de executar `git add`.
3. **Trava de Qualidade (Testes + Build Verdes):**
   - Execute `git commit` e `git push` **somente após** toda a suíte automatizada do backend (`pytest`) e o build de produção/tipagem do frontend (`npm run build`) passarem com zero erros.
4. **Tratamento de Repositório sem Remote ou Falha de Autenticação:**
   - Caso o repositório ainda não possua `remote origin` configurado ou o `git push` falhe por credenciais/rede, conclua obrigatoriamente o `git commit` local e informe ao usuário o hash do commit gerado e o comando exato pendente para vincular/enviar ao repositório remoto (`git remote add origin <URL_DO_REPOSITORIO> && git push -u origin <BRANCH>`).

## Diretrizes Arquiteturais Inegociáveis

- **Isolamento Multi-Tenant Estrito:** Toda entidade operacional pertence a um `studio_id` e toda leitura, escrita, atualização e exclusão deve passar por `BaseTenantRepository` / `TenantContext` retornando `404` para acessos cruzados (prevenção total contra IDOR).
- **Integridade Contábil e Estoque:** Valores monetários sempre em `NUMERIC(12, 2)` / `Decimal`. Proibida exclusão física de clientes, vendas, movimentações de estoque (`inventory_movements`) ou lançamentos financeiros (`financial_transactions`) — utilize exclusivamente *soft delete* (`deleted_at`) ou lançamentos imutáveis de estorno/Kardex.
- **Proteção de Margem por RBAC:** Campos de custo (`cost_price`, `unit_cost_snapshot`) e lucro líquido são estritamente restritos ao papel `OWNER`, devendo ser omitidos nos DTOs de resposta para `RECEPTION` e `PROFESSIONAL`.
