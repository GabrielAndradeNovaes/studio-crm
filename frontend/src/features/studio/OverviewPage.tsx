import { useQuery } from "@tanstack/react-query";
import { Clock, Layers, Percent, ShieldCheck } from "lucide-react";
import { Badge, Card } from "@/components/ui/primitives";
import { useAuth } from "@/features/auth/AuthContext";
import { apiFetch } from "@/lib/api";
import type { StudioDetails, TeamMemberOwner } from "@/lib/types";

export function OverviewPage() {
  const { currentStudio, user } = useAuth();

  const { data: studio } = useQuery({
    queryKey: ["studio-current", currentStudio?.studio_id],
    queryFn: () => apiFetch<StudioDetails>("/studios/current"),
    enabled: Boolean(currentStudio),
  });

  const { data: myProfile } = useQuery({
    queryKey: ["team-me", currentStudio?.studio_id],
    queryFn: () => apiFetch<TeamMemberOwner>("/team/me"),
    enabled: Boolean(currentStudio),
  });

  if (!currentStudio) {
    return (
      <Card className="p-6">
        <h1 className="text-xl font-bold">Bem-vindo, {user?.name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Selecione um estúdio no menu lateral ou acesse o painel SuperAdmin SaaS.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          {studio?.name || currentStudio.studio_name}
        </h1>
        <p className="text-sm text-muted-foreground">
          Ambiente operacional isolado por estúdio • Papel atual:{" "}
          <strong className="text-foreground">{currentStudio.role}</strong>
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">
              Assinatura SaaS
            </span>
            <ShieldCheck className="h-4 w-4 text-emerald-600" aria-hidden="true" />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <Badge
              tone={
                currentStudio.subscription_status === "ACTIVE"
                  ? "success"
                  : currentStudio.subscription_status === "PAST_DUE"
                  ? "warning"
                  : "info"
              }
            >
              {currentStudio.subscription_status}
            </Badge>
            <span className="text-xs text-muted-foreground">
              Plano: {studio?.plan_tier || "piercing_mvp"}
            </span>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">
              Módulos Ativos
            </span>
            <Layers className="h-4 w-4 text-sky-600" aria-hidden="true" />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {currentStudio.enabled_modules.map((mod) => (
              <Badge key={mod} tone="info">
                {mod === "piercing" ? "Piercing (MVP)" : "Tatuagem"}
              </Badge>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">
              Fuso do Caixa
            </span>
            <Clock className="h-4 w-4 text-slate-600" aria-hidden="true" />
          </div>
          <p className="mt-3 text-base font-semibold text-slate-900">
            {studio?.timezone || currentStudio.timezone}
          </p>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">
              Minhas Comissões
            </span>
            <Percent className="h-4 w-4 text-slate-600" aria-hidden="true" />
          </div>
          <p className="mt-3 text-sm font-medium text-slate-900">
            Perfuração:{" "}
            <strong>{myProfile?.commission_service_pct ?? "0.00"}%</strong> • Joias:{" "}
            <strong>{myProfile?.commission_product_pct ?? "0.00"}%</strong>
          </p>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="text-base font-semibold text-slate-900">
          Fundação Multi-Tenant &amp; Segurança Ativa (Fase 1 Concluída)
        </h2>
        <ul className="mt-3 grid grid-cols-1 gap-2 text-sm text-muted-foreground sm:grid-cols-2">
          <li>• Isolamento estrito por studio_id em SELECT, INSERT, UPDATE e DELETE</li>
          <li>• Sessão JWT em memória + Refresh Token rotativo HttpOnly</li>
          <li>• Suporte multi-estúdio por profissional/proprietário com troca rápida</li>
          <li>• Arquitetura modular pronta para Piercing (MVP) e futuro Tatuagem</li>
        </ul>
      </Card>
    </div>
  );
}
