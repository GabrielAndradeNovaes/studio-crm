import * as React from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Calendar,
  CalendarClock,
  ContactRound,
  Gem,
  ShoppingBag,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { Badge, Button, Card, Input } from "@/components/ui/primitives";
import { useAuth } from "@/features/auth/AuthContext";
import { apiFetch } from "@/lib/api";
import {
  formatCurrencyBRL,
  shiftPlainDateIso,
  todayIsoInTimezone,
} from "@/lib/dates";
import type {
  AppointmentItem,
  ClientRecord,
  ExecutiveDashboardData,
  PaymentMethodCode,
  PiercingProcedureItem,
  PiercingProductItem,
  StudioDetails,
} from "@/lib/types";

const METHOD_LABELS: Record<PaymentMethodCode, string> = {
  PIX: "PIX",
  CREDIT_CARD: "Cartão de Crédito",
  DEBIT_CARD: "Cartão de Débito",
  CASH: "Dinheiro",
};

export function OverviewPage() {
  const { currentStudio, user } = useAuth();
  const studioTz = currentStudio?.timezone || "America/Sao_Paulo";
  const todayIso = todayIsoInTimezone(studioTz);
  const isOwner = currentStudio?.role === "OWNER";
  const canUsePos =
    currentStudio?.role === "OWNER" || currentStudio?.role === "RECEPTION";
  const hasPiercing = Boolean(
    currentStudio?.enabled_modules?.includes("piercing")
  );

  const firstOfMonthIso = `${todayIso.slice(0, 8)}01`;
  const [dateFrom, setDateFrom] = React.useState(firstOfMonthIso);
  const [dateTo, setDateTo] = React.useState(todayIso);

  const { data: studio } = useQuery({
    queryKey: ["studio-current", currentStudio?.studio_id],
    queryFn: () => apiFetch<StudioDetails>("/studios/current"),
    enabled: Boolean(currentStudio),
  });

  const { data: todayAppointments } = useQuery({
    queryKey: ["appointments-today", currentStudio?.studio_id, todayIso],
    queryFn: () =>
      apiFetch<AppointmentItem[]>(
        `/appointments?date_from=${todayIso}&date_to=${todayIso}`
      ),
    enabled: Boolean(currentStudio),
  });

  const { data: clients } = useQuery({
    queryKey: ["clients-summary", currentStudio?.studio_id],
    queryFn: () => apiFetch<ClientRecord[]>("/clients?limit=300"),
    enabled: Boolean(currentStudio),
  });

  const { data: pendingDownsizes } = useQuery({
    queryKey: ["downsize-summary", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PiercingProcedureItem[]>(
        "/piercing/procedures/downsize-reminders?window=all_pending"
      ),
    enabled: Boolean(currentStudio && hasPiercing),
  });

  const { data: lowStockProducts } = useQuery({
    queryKey: ["piercing-low-stock", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PiercingProductItem[]>("/piercing/products?low_stock_only=true"),
    enabled: Boolean(currentStudio && hasPiercing),
  });

  const { data: dashboard } = useQuery({
    queryKey: [
      "finance-dashboard",
      currentStudio?.studio_id,
      dateFrom,
      dateTo,
    ],
    queryFn: () =>
      apiFetch<ExecutiveDashboardData>(
        `/finance/dashboard?date_from=${dateFrom}&date_to=${dateTo}`
      ),
    enabled: Boolean(currentStudio && isOwner),
  });

  if (!currentStudio) {
    return (
      <Card className="p-6">
        <h1 className="text-xl font-bold">Bem-vindo, {user?.name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Selecione um estúdio no menu lateral ou acesse o painel SuperAdmin
          SaaS.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {studio?.name || currentStudio.studio_name}
          </h1>
          <p className="text-sm text-muted-foreground">
            Fuso: <strong>{studio?.timezone || currentStudio.timezone}</strong>{" "}
            • Papel:{" "}
            <strong className="text-foreground">{currentStudio.role}</strong>
          </p>
        </div>

        {canUsePos && (
          <div className="flex flex-wrap gap-2">
            <Link to="/finance/cashflow">
              <Button variant="outline">
                <Wallet className="h-4 w-4" aria-hidden="true" />
                {isOwner ? "Livro-Caixa" : "Caixa do Dia"}
              </Button>
            </Link>
            <Link to="/pos">
              <Button>
                <ShoppingBag className="h-4 w-4" aria-hidden="true" />
                Abrir PDV
              </Button>
            </Link>
          </div>
        )}
      </div>

      {/* Cards Operacionais Rápidos */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link to="/appointments" className="block">
          <Card className="h-full p-5 transition hover:border-slate-400">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-muted-foreground">
                Agenda de Hoje
              </span>
              <Calendar className="h-4 w-4 text-sky-600" aria-hidden="true" />
            </div>
            <p className="mt-3 text-2xl font-bold text-slate-900">
              {todayAppointments?.length ?? 0}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Com sinal pago:{" "}
              <strong>
                {todayAppointments?.filter((a) => a.deposit_status === "PAID")
                  .length ?? 0}
              </strong>
            </p>
          </Card>
        </Link>

        <Link to="/clients" className="block">
          <Card className="h-full p-5 transition hover:border-slate-400">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-muted-foreground">
                Clientes Ativos
              </span>
              <ContactRound
                className="h-4 w-4 text-slate-700"
                aria-hidden="true"
              />
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
          <Link to="/piercing/downsize" className="block">
            <Card className="h-full p-5 transition hover:border-slate-400">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase text-muted-foreground">
                  Retornos de Downsize
                </span>
                <CalendarClock
                  className="h-4 w-4 text-indigo-600"
                  aria-hidden="true"
                />
              </div>
              <div className="mt-3 flex items-center gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {pendingDownsizes?.length ?? 0}
                </span>
                {(pendingDownsizes?.filter((d) => d.is_overdue).length ?? 0) >
                  0 && (
                  <Badge tone="danger">
                    {pendingDownsizes?.filter((d) => d.is_overdue).length}{" "}
                    atrasado(s)
                  </Badge>
                )}
              </div>
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
      </div>

      {/* Dashboard Executivo & DRE Simplificada — Exclusivo OWNER */}
      {isOwner && (
        <section
          aria-labelledby="dre-heading"
          className="space-y-4 border-t border-border pt-6"
        >
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2
                id="dre-heading"
                className="flex items-center gap-2 text-lg font-bold text-slate-900"
              >
                <TrendingUp className="h-5 w-5 text-emerald-700" aria-hidden="true" />
                Dashboard Executivo & DRE Simplificada
              </h2>
              <p className="text-xs text-muted-foreground">
                Visão gerencial restrita ao proprietário (competência em{" "}
                <strong>{studioTz}</strong>).
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setDateFrom(todayIso);
                  setDateTo(todayIso);
                }}
              >
                Hoje
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setDateFrom(shiftPlainDateIso(todayIso, -6));
                  setDateTo(todayIso);
                }}
              >
                7 dias
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setDateFrom(firstOfMonthIso);
                  setDateTo(todayIso);
                }}
              >
                Mês atual
              </Button>
              <Input
                type="date"
                aria-label="Data inicial da DRE"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="min-h-[38px] w-36 py-1 text-xs"
              />
              <Input
                type="date"
                aria-label="Data final da DRE"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="min-h-[38px] w-36 py-1 text-xs"
              />
            </div>
          </div>

          {dashboard && (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Card className="p-4">
                  <p className="text-xs font-semibold uppercase text-muted-foreground">
                    Faturamento Bruto ({dashboard.completed_sales_count} vendas)
                  </p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">
                    {formatCurrencyBRL(dashboard.gross_revenue)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Ticket médio: {formatCurrencyBRL(dashboard.average_ticket)}
                  </p>
                </Card>

                <Card className="p-4">
                  <p className="text-xs font-semibold uppercase text-muted-foreground">
                    Entradas Líquidas (Caixa)
                  </p>
                  <p className="mt-2 text-2xl font-bold text-emerald-700">
                    {formatCurrencyBRL(dashboard.cash_inflow_net)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    (-) Taxas: {formatCurrencyBRL(dashboard.payment_fees_total)}
                  </p>
                </Card>

                <Card className="p-4">
                  <p className="text-xs font-semibold uppercase text-muted-foreground">
                    Custos Diretos (CMV + Comissões)
                  </p>
                  <p className="mt-2 text-lg font-bold text-slate-900">
                    CMV Joias: {formatCurrencyBRL(dashboard.jewelry_cogs_total)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Comissões:{" "}
                    {formatCurrencyBRL(dashboard.commissions_generated_total)}{" "}
                    (pend.:{" "}
                    {formatCurrencyBRL(dashboard.commissions_pending_total)})
                  </p>
                </Card>

                <Card
                  className={`p-4 text-white ${
                    Number(dashboard.estimated_net_profit) >= 0
                      ? "bg-slate-900"
                      : "bg-red-900"
                  }`}
                >
                  <p className="text-xs font-semibold uppercase text-slate-300">
                    Lucro Líquido Estimado
                  </p>
                  <p className="mt-2 text-2xl font-bold">
                    {formatCurrencyBRL(dashboard.estimated_net_profit)}
                  </p>
                  <p className="mt-1 text-xs text-slate-300">
                    (-) Despesas oper.:{" "}
                    {formatCurrencyBRL(dashboard.operating_expenses_total)}
                  </p>
                </Card>
              </div>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Card className="p-5 space-y-3">
                  <h3 className="text-sm font-bold text-slate-900">
                    Recebimentos por Meio de Pagamento
                  </h3>
                  {dashboard.by_payment_method.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Sem pagamentos concluídos no período.
                    </p>
                  ) : (
                    <div className="space-y-2 text-sm">
                      {dashboard.by_payment_method.map((m) => (
                        <div
                          key={m.method}
                          className="flex items-center justify-between rounded-md border border-border px-3 py-2"
                        >
                          <div>
                            <p className="font-semibold text-slate-900">
                              {METHOD_LABELS[m.method]} ({m.count}x)
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Taxa: {formatCurrencyBRL(m.fee_amount)}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-slate-900">
                              {formatCurrencyBRL(m.gross_amount)}
                            </p>
                            <p className="text-xs text-emerald-700">
                              Líq.: {formatCurrencyBRL(m.net_amount)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>

                <Card className="p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900">
                      Desempenho por Profissional
                    </h3>
                    <Link
                      to="/finance/commissions"
                      className="text-xs font-semibold text-sky-700 hover:underline"
                    >
                      Gerenciar repasses
                    </Link>
                  </div>
                  {dashboard.by_professional.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Sem itens comissionados no período.
                    </p>
                  ) : (
                    <div className="space-y-2 text-sm">
                      {dashboard.by_professional.map((p) => (
                        <div
                          key={p.professional_id}
                          className="flex items-center justify-between rounded-md border border-border px-3 py-2"
                        >
                          <div>
                            <p className="font-semibold text-slate-900">
                              {p.professional_name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {p.items_count} item(ns) realizado(s)
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-slate-900">
                              {formatCurrencyBRL(p.gross_revenue_generated)}
                            </p>
                            <p className="text-xs text-amber-800">
                              Comissão:{" "}
                              {formatCurrencyBRL(p.commissions_generated)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}
