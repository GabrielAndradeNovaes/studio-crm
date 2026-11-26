import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ContactRound,
  Gem,
  Percent,
  ShieldCheck,
  Syringe,
} from "lucide-react";
import { Badge, Card } from "@/components/ui/primitives";
import { useAuth } from "@/features/auth/AuthContext";
import { apiFetch } from "@/lib/api";
import type {
  ClientRecord,
  PiercingProductItem,
  PiercingServiceItem,
  StudioDetails,
  TeamMemberOwner,
} from "@/lib/types";

export function OverviewPage() {
  const { currentStudio, user } = useAuth();
  const hasPiercing = Boolean(
    currentStudio?.enabled_modules?.includes("piercing")
  );

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

  const { data: clients } = useQuery({
    queryKey: ["clients-summary", currentStudio?.studio_id],
    queryFn: () => apiFetch<ClientRecord[]>("/clients?limit=300"),
    enabled: Boolean(currentStudio),
  });

  const { data: services } = useQuery({
    queryKey: ["piercing-services-summary", currentStudio?.studio_id],
    queryFn: () => apiFetch<PiercingServiceItem[]>("/piercing/services?active_only=true"),
    enabled: Boolean(currentStudio && hasPiercing),
  });

  const { data: lowStockProducts } = useQuery({
    queryKey: ["piercing-low-stock", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PiercingProductItem[]>("/piercing/products?low_stock_only=true"),
    enabled: Boolean(currentStudio && hasPiercing),
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
          Fuso: <strong>{studio?.timezone || currentStudio.timezone}</strong> • Papel:{" "}
          <strong className="text-foreground">{currentStudio.role}</strong>
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link to="/clients" className="block">
          <Card className="h-full p-5 transition hover:border-slate-400">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-muted-foreground">
                Clientes Ativos
              </span>
              <ContactRound className="h-4 w-4 text-slate-700" aria-hidden="true" />
            </div>
            <p className="mt-3 text-2xl font-bold text-slate-900">
              {clients?.length ?? 0}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Menores (&lt; 18):{" "}
              <strong>{clients?.filter((c) => c.is_minor).length ?? 0}</strong>
            </p>
          </Card>
        </Link>

        {hasPiercing && (
          <Link to="/piercing/services" className="block">
            <Card className="h-full p-5 transition hover:border-slate-400">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase text-muted-foreground">
                  Perfurações Ativas
                </span>
                <Syringe className="h-4 w-4 text-sky-600" aria-hidden="true" />
              </div>
              <p className="mt-3 text-2xl font-bold text-slate-900">
                {services?.length ?? 0}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Catálogo anatômico configurado
              </p>
            </Card>
          </Link>
        )}

        {hasPiercing && (
          <Link to="/piercing/inventory" className="block">
            <Card className="h-full p-5 transition hover:border-slate-400">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase text-muted-foreground">
                  Alertas de Estoque
                </span>
                <Gem className="h-4 w-4 text-amber-600" aria-hidden="true" />
              </div>
              <div className="mt-3 flex items-center gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {lowStockProducts?.length ?? 0}
                </span>
                {(lowStockProducts?.length ?? 0) > 0 ? (
                  <Badge tone="warning" className="gap-1">
                    <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                    Reposição
                  </Badge>
                ) : (
                  <Badge tone="success">Em dia</Badge>
                )}
              </div>
            </Card>
          </Link>
        )}

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">
              Minhas Comissões &amp; Plano
            </span>
            <Percent className="h-4 w-4 text-emerald-600" aria-hidden="true" />
          </div>
          <p className="mt-3 text-sm font-medium text-slate-900">
            Serviço: <strong>{myProfile?.commission_service_pct ?? "0.00"}%</strong> •
            Joia: <strong>{myProfile?.commission_product_pct ?? "0.00"}%</strong>
          </p>
          <div className="mt-2 flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
            <span className="text-xs text-muted-foreground">
              Status: {currentStudio.subscription_status}
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
}
