import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, DollarSign } from "lucide-react";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import {
  formatCurrencyBRL,
  formatUtcInStudioTimezone,
  shiftPlainDateIso,
  todayIsoInTimezone,
} from "@/lib/dates";
import type {
  CommissionItemRecord,
  CommissionPayoutResult,
  CommissionStatus,
  MyCommissionsSummary,
  PaymentMethodCode,
  TeamMemberDirectory,
} from "@/lib/types";

const STATUS_BADGE: Record<
  CommissionStatus,
  { label: string; tone: "warning" | "success" | "neutral" }
> = {
  PENDING: { label: "Pendente", tone: "warning" },
  PAID: { label: "Paga", tone: "success" },
  REVERSED: { label: "Estornada", tone: "neutral" },
};

export function CommissionsPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const studioTz = currentStudio?.timezone || "America/Sao_Paulo";
  const isOwner = currentStudio?.role === "OWNER";
  const todayIso = todayIsoInTimezone(studioTz);

  const [dateFrom, setDateFrom] = React.useState(() =>
    shiftPlainDateIso(todayIso, -30)
  );
  const [dateTo, setDateTo] = React.useState(todayIso);
  const [profFilter, setProfFilter] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);

  const [payoutOpen, setPayoutOpen] = React.useState(false);
  const [payoutMethod, setPayoutMethod] =
    React.useState<PaymentMethodCode>("PIX");
  const [payoutNotes, setPayoutNotes] = React.useState("");
  const [payoutError, setPayoutError] = React.useState<string | null>(null);

  const directoryQuery = useQuery({
    queryKey: ["team-directory", currentStudio?.studio_id],
    queryFn: () => apiFetch<TeamMemberDirectory[]>("/team/directory"),
    enabled: Boolean(currentStudio && isOwner),
  });

  const ownerCommissionsQuery = useQuery({
    queryKey: [
      "finance-commissions",
      currentStudio?.studio_id,
      profFilter,
      statusFilter,
      dateFrom,
      dateTo,
    ],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("date_from", dateFrom);
      params.set("date_to", dateTo);
      if (profFilter) params.set("professional_id", profFilter);
      if (statusFilter) params.set("status", statusFilter);
      return apiFetch<CommissionItemRecord[]>(
        `/finance/commissions?${params.toString()}`
      );
    },
    enabled: Boolean(currentStudio && isOwner),
  });

  const myCommissionsQuery = useQuery({
    queryKey: [
      "finance-my-commissions",
      currentStudio?.studio_id,
      dateFrom,
      dateTo,
    ],
    queryFn: () =>
      apiFetch<MyCommissionsSummary>(
        `/finance/my-commissions?date_from=${dateFrom}&date_to=${dateTo}`
      ),
    enabled: Boolean(currentStudio && !isOwner),
  });

  // Limpa seleção ao trocar filtros
  React.useEffect(() => {
    setSelectedIds([]);
  }, [profFilter, statusFilter, dateFrom, dateTo]);

  const ownerItems = ownerCommissionsQuery.data || [];
  const selectedRecords = ownerItems.filter((c) => selectedIds.includes(c.id));
  const selectedProfessionalId =
    selectedRecords[0]?.professional_id || profFilter || "";

  const selectedTotalCents = selectedRecords.reduce(
    (acc, item) => acc + Math.round(Number(item.commission_amount) * 100),
    0
  );

  const toggleSelect = (item: CommissionItemRecord) => {
    if (item.status !== "PENDING") return;
    setSelectedIds((prev) => {
      if (prev.includes(item.id)) {
        return prev.filter((id) => id !== item.id);
      }
      // Garante seleção de apenas 1 profissional por lote de repasse
      if (
        selectedRecords.length > 0 &&
        selectedRecords[0].professional_id !== item.professional_id
      ) {
        return [item.id];
      }
      return [...prev, item.id];
    });
  };

  const selectAllPendingForProf = () => {
    const targetProf =
      profFilter ||
      ownerItems.find((i) => i.status === "PENDING")?.professional_id;
    if (!targetProf) return;
    const ids = ownerItems
      .filter(
        (i) => i.status === "PENDING" && i.professional_id === targetProf
      )
      .map((i) => i.id);
    setSelectedIds(ids);
  };

  const payoutMutation = useMutation({
    mutationFn: () =>
      apiFetch<CommissionPayoutResult>("/finance/commissions/payout", {
        method: "POST",
        body: JSON.stringify({
          professional_id: selectedProfessionalId,
          commission_ids: selectedIds,
          payment_method: payoutMethod,
          notes: payoutNotes.trim() || null,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["finance-commissions"] });
      queryClient.invalidateQueries({ queryKey: ["finance-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      setSelectedIds([]);
      setPayoutNotes("");
      setPayoutError(null);
      setPayoutOpen(false);
    },
    onError: (err) => {
      setPayoutError(
        err instanceof ApiError
          ? err.detail
          : "Não foi possível liquidar o repasse."
      );
    },
  });

  if (!isOwner) {
    const summary = myCommissionsQuery.data;
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Minhas Comissões
          </h1>
          <p className="text-sm text-muted-foreground">
            Acompanhe seus ganhos por perfuração e venda de joias no período.
          </p>
        </div>

        <Card className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label htmlFor="my-comm-from">De</Label>
              <Input
                id="my-comm-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="min-h-[42px] w-40"
              />
            </div>
            <div>
              <Label htmlFor="my-comm-to">Até</Label>
              <Input
                id="my-comm-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="min-h-[42px] w-40"
              />
            </div>
          </div>
        </Card>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card className="p-4">
            <p className="text-xs font-semibold uppercase text-muted-foreground">
              A Receber (Pendente)
            </p>
            <p className="mt-2 text-2xl font-bold text-amber-700">
              {formatCurrencyBRL(summary?.pending_total || "0.00")}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs font-semibold uppercase text-muted-foreground">
              Total Já Pago
            </p>
            <p className="mt-2 text-2xl font-bold text-emerald-700">
              {formatCurrencyBRL(summary?.paid_total || "0.00")}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs font-semibold uppercase text-muted-foreground">
              Estornadas
            </p>
            <p className="mt-2 text-2xl font-bold text-slate-600">
              {formatCurrencyBRL(summary?.reversed_total || "0.00")}
            </p>
          </Card>
        </div>

        <Card className="p-5">
          <div className="table-wrapper">
            <table
              className="responsive-data-table text-left text-sm"
              style={
                {
                  "--label-2": '"Data"',
                  "--label-3": '"Base / %"',
                  "--label-4": '"Comissão"',
                  "--label-5": '"Status"',
                } as React.CSSProperties
              }
            >
              <thead className="bg-secondary text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2.5">Item</th>
                  <th className="px-3 py-2.5">Data</th>
                  <th className="px-3 py-2.5">Base / %</th>
                  <th className="px-3 py-2.5">Comissão</th>
                  <th className="px-3 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {summary?.items.map((item) => {
                  const dt = formatUtcInStudioTimezone(
                    item.created_at,
                    studioTz
                  );
                  const st = STATUS_BADGE[item.status];
                  return (
                    <tr key={item.id} className="border-b border-border">
                      <th
                        scope="row"
                        className="px-3 py-2.5 font-semibold text-slate-900"
                      >
                        {item.description}
                      </th>
                      <td className="px-3 py-2.5">{dt.dateLabel}</td>
                      <td className="px-3 py-2.5 text-xs">
                        {formatCurrencyBRL(item.base_amount)} (
                        {item.commission_pct_snapshot}%)
                      </td>
                      <td className="px-3 py-2.5 font-bold">
                        {formatCurrencyBRL(item.commission_amount)}
                      </td>
                      <td className="px-3 py-2.5">
                        <Badge tone={st.tone}>{st.label}</Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {summary?.items.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Nenhuma comissão registrada no período.
              </p>
            )}
          </div>
        </Card>
      </div>
    );
  }

  const totalPendingOwnerCents = ownerItems
    .filter((i) => i.status === "PENDING")
    .reduce((acc, i) => acc + Math.round(Number(i.commission_amount) * 100), 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Gestão & Repasse de Comissões
          </h1>
          <p className="text-sm text-muted-foreground">
            Percentuais separados para serviços e joias, com dedução automática
            de ajustes de estorno em lote único no livro-caixa.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={selectAllPendingForProf}
          >
            Selecionar pendentes do profissional
          </Button>
          <Button
            disabled={selectedIds.length === 0 || selectedTotalCents <= 0}
            onClick={() => {
              setPayoutError(null);
              setPayoutOpen(true);
            }}
          >
            <DollarSign className="h-4 w-4" aria-hidden="true" />
            Registrar Repasse (
            {formatCurrencyBRL((selectedTotalCents / 100).toFixed(2))})
          </Button>
        </div>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label htmlFor="comm-prof">Profissional</Label>
              <select
                id="comm-prof"
                value={profFilter}
                onChange={(e) => setProfFilter(e.target.value)}
                className="flex min-h-[42px] rounded-md border border-input bg-card px-3 text-sm"
              >
                <option value="">Todos os profissionais</option>
                {directoryQuery.data?.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name} ({m.role})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label htmlFor="comm-status">Status</Label>
              <select
                id="comm-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="flex min-h-[42px] rounded-md border border-input bg-card px-3 text-sm"
              >
                <option value="">Todos</option>
                <option value="PENDING">Pendentes</option>
                <option value="PAID">Pagas</option>
                <option value="REVERSED">Estornadas</option>
              </select>
            </div>

            <div>
              <Label htmlFor="comm-from">De</Label>
              <Input
                id="comm-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="min-h-[42px] w-40"
              />
            </div>

            <div>
              <Label htmlFor="comm-to">Até</Label>
              <Input
                id="comm-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="min-h-[42px] w-40"
              />
            </div>
          </div>

          <div className="text-right text-xs text-muted-foreground">
            Total pendente listado:{" "}
            <strong className="text-sm text-amber-800">
              {formatCurrencyBRL((totalPendingOwnerCents / 100).toFixed(2))}
            </strong>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <div className="table-wrapper">
          <table
            className="responsive-data-table text-left text-sm"
            style={
              {
                "--label-2": '"Profissional"',
                "--label-3": '"Data"',
                "--label-4": '"Base / %"',
                "--label-5": '"Valor"',
                "--label-6": '"Status"',
              } as React.CSSProperties
            }
          >
            <thead className="bg-secondary text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2.5">Item / Seleção</th>
                <th className="px-3 py-2.5">Profissional</th>
                <th className="px-3 py-2.5">Data</th>
                <th className="px-3 py-2.5">Base / %</th>
                <th className="px-3 py-2.5">Comissão</th>
                <th className="px-3 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {ownerItems.map((item) => {
                const dt = formatUtcInStudioTimezone(item.created_at, studioTz);
                const st = STATUS_BADGE[item.status];
                const checked = selectedIds.includes(item.id);
                const isNegative = Number(item.commission_amount) < 0;

                return (
                  <tr key={item.id} className="border-b border-border">
                    <th
                      scope="row"
                      className="px-3 py-2.5 font-semibold text-slate-900"
                    >
                      <label className="flex items-center gap-2.5">
                        {item.status === "PENDING" ? (
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleSelect(item)}
                            className="h-4 w-4 rounded border-input"
                          />
                        ) : (
                          <CheckCircle2
                            className="h-4 w-4 text-slate-400"
                            aria-hidden="true"
                          />
                        )}
                        <span>{item.description}</span>
                      </label>
                    </th>
                    <td className="px-3 py-2.5">{item.professional_name}</td>
                    <td className="px-3 py-2.5">{dt.dateLabel}</td>
                    <td className="px-3 py-2.5 text-xs">
                      {formatCurrencyBRL(item.base_amount)} (
                      {item.commission_pct_snapshot}%)
                    </td>
                    <td
                      className={`px-3 py-2.5 font-bold ${
                        isNegative ? "text-red-700" : "text-slate-900"
                      }`}
                    >
                      {formatCurrencyBRL(item.commission_amount)}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge tone={st.tone}>{st.label}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {ownerItems.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Nenhuma comissão encontrada com os filtros selecionados.
            </p>
          )}
        </div>
      </Card>

      <ModalDialog
        open={payoutOpen}
        onClose={() => setPayoutOpen(false)}
        title="Confirmar Repasse de Comissões"
        description={`Profissional: ${
          selectedRecords[0]?.professional_name || ""
        } • ${selectedIds.length} item(ns) selecionado(s).`}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            payoutMutation.mutate();
          }}
          className="space-y-4"
        >
          {payoutError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {payoutError}
            </div>
          )}

          <div className="rounded-lg bg-slate-900 p-4 text-white">
            <p className="text-xs uppercase text-slate-300">
              Valor Líquido do Repasse (EXPENSE / COMMISSION_PAYOUT)
            </p>
            <p className="mt-1 text-2xl font-bold">
              {formatCurrencyBRL((selectedTotalCents / 100).toFixed(2))}
            </p>
          </div>

          <div>
            <Label htmlFor="payout-method">Meio de Pagamento *</Label>
            <select
              id="payout-method"
              value={payoutMethod}
              onChange={(e) =>
                setPayoutMethod(e.target.value as PaymentMethodCode)
              }
              className="flex min-h-[46px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="PIX">PIX</option>
              <option value="CASH">Dinheiro</option>
              <option value="DEBIT_CARD">Transferência / Débito</option>
            </select>
          </div>

          <div>
            <Label htmlFor="payout-notes">Observações</Label>
            <Input
              id="payout-notes"
              value={payoutNotes}
              onChange={(e) => setPayoutNotes(e.target.value)}
              placeholder="Ex.: Fechamento quinzenal"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setPayoutOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={payoutMutation.isPending}>
              {payoutMutation.isPending
                ? "Liquidando..."
                : "Confirmar Pagamento"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}
