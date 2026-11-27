import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  Plus,
  RotateCcw,
  ShoppingBag,
  Wallet,
} from "lucide-react";
import { AccessibleTabs } from "@/components/ui/AccessibleTabs";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import {
  formatCurrencyBRL,
  formatPlainCalendarDate,
  formatUtcInStudioTimezone,
  shiftPlainDateIso,
  todayIsoInTimezone,
} from "@/lib/dates";
import type {
  CashflowPeriodSummary,
  DailyRegisterData,
  FinancialTransactionCategory,
  FinancialTransactionRecord,
  ManualCategoryAllowed,
  PaymentMethodCode,
  SaleRecord,
} from "@/lib/types";

const CATEGORY_LABELS: Record<FinancialTransactionCategory, string> = {
  APPOINTMENT_DEPOSIT: "Sinal de Agendamento",
  SALE_PAYMENT: "Recebimento PDV",
  COMMISSION_PAYOUT: "Repasse de Comissão",
  FIXED_EXPENSE: "Despesa Fixa",
  VARIABLE_EXPENSE: "Despesa Variável",
  INVENTORY_PURCHASE: "Compra de Joias/Insumos",
  OTHER_INCOME: "Outra Receita",
  REFUND_OUTFLOW: "Saída por Estorno",
  MANUAL_REVERSAL: "Estorno Contábil",
};

const METHOD_LABELS: Record<PaymentMethodCode, string> = {
  PIX: "PIX",
  CREDIT_CARD: "Cartão de Crédito",
  DEBIT_CARD: "Cartão de Débito",
  CASH: "Dinheiro",
};

export function FinanceCashflowPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const studioTz = currentStudio?.timezone || "America/Sao_Paulo";
  const isOwner = currentStudio?.role === "OWNER";
  const todayIso = todayIsoInTimezone(studioTz);

  const [activeTab, setActiveTab] = React.useState("ledger");
  const [dateFrom, setDateFrom] = React.useState(() =>
    shiftPlainDateIso(todayIso, -30)
  );
  const [dateTo, setDateTo] = React.useState(todayIso);
  const [dailyDate, setDailyDate] = React.useState(todayIso);
  const [salesStatusFilter, setSalesStatusFilter] = React.useState("");

  // Modais exclusivos OWNER
  const [manualOpen, setManualOpen] = React.useState(false);
  const [manualCategory, setManualCategory] =
    React.useState<ManualCategoryAllowed>("FIXED_EXPENSE");
  const [manualDesc, setManualDesc] = React.useState("");
  const [manualAmount, setManualAmount] = React.useState("");
  const [manualMethod, setManualMethod] =
    React.useState<PaymentMethodCode>("PIX");
  const [manualCompetenceDate, setManualCompetenceDate] =
    React.useState(todayIso);

  const [reverseTxTarget, setReverseTxTarget] =
    React.useState<FinancialTransactionRecord | null>(null);
  const [reverseReason, setReverseReason] = React.useState("");

  const [refundSaleTarget, setRefundSaleTarget] =
    React.useState<SaleRecord | null>(null);
  const [refundSaleReason, setRefundSaleReason] = React.useState("");
  const [refundDepositToo, setRefundDepositToo] = React.useState(false);
  const [modalError, setModalError] = React.useState<string | null>(null);

  const ledgerQuery = useQuery({
    queryKey: [
      "finance-transactions",
      currentStudio?.studio_id,
      dateFrom,
      dateTo,
    ],
    queryFn: () =>
      apiFetch<CashflowPeriodSummary>(
        `/finance/transactions?date_from=${dateFrom}&date_to=${dateTo}`
      ),
    enabled: Boolean(currentStudio && isOwner),
  });

  const salesQuery = useQuery({
    queryKey: [
      "finance-sales",
      currentStudio?.studio_id,
      dateFrom,
      dateTo,
      salesStatusFilter,
    ],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("date_from", dateFrom);
      params.set("date_to", dateTo);
      if (salesStatusFilter) params.set("status", salesStatusFilter);
      return apiFetch<SaleRecord[]>(`/finance/sales?${params.toString()}`);
    },
    enabled: Boolean(currentStudio && isOwner),
  });

  const dailyRegisterQuery = useQuery({
    queryKey: [
      "finance-daily-register",
      currentStudio?.studio_id,
      dailyDate,
    ],
    queryFn: () =>
      apiFetch<DailyRegisterData>(
        `/finance/daily-register?target_date=${dailyDate}`
      ),
    enabled: Boolean(currentStudio),
  });

  const createManualMutation = useMutation({
    mutationFn: () =>
      apiFetch<FinancialTransactionRecord>("/finance/transactions", {
        method: "POST",
        body: JSON.stringify({
          category: manualCategory,
          description: manualDesc.trim(),
          amount: manualAmount,
          payment_method: manualMethod,
          competence_date: manualCompetenceDate,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["finance-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      setManualOpen(false);
      setManualDesc("");
      setManualAmount("");
      setModalError(null);
    },
    onError: (err) => {
      setModalError(
        err instanceof ApiError ? err.detail : "Erro ao lançar movimentação."
      );
    },
  });

  const reverseTxMutation = useMutation({
    mutationFn: () => {
      if (!reverseTxTarget) throw new Error("Lançamento inválido");
      return apiFetch<FinancialTransactionRecord>(
        `/finance/transactions/${reverseTxTarget.id}/reverse`,
        {
          method: "POST",
          body: JSON.stringify({ reason: reverseReason.trim() }),
        }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["finance-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["finance-daily-register"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      setReverseTxTarget(null);
      setReverseReason("");
      setModalError(null);
    },
    onError: (err) => {
      setModalError(
        err instanceof ApiError ? err.detail : "Erro ao estornar lançamento."
      );
    },
  });

  const refundSaleMutation = useMutation({
    mutationFn: () => {
      if (!refundSaleTarget) throw new Error("Venda inválida");
      return apiFetch<SaleRecord>(
        `/finance/sales/${refundSaleTarget.id}/refund`,
        {
          method: "POST",
          body: JSON.stringify({
            reason: refundSaleReason.trim(),
            refund_deposit: refundDepositToo,
          }),
        }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["finance-sales"] });
      queryClient.invalidateQueries({ queryKey: ["finance-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["finance-daily-register"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["finance-commissions"] });
      queryClient.invalidateQueries({ queryKey: ["piercing-products"] });
      setRefundSaleTarget(null);
      setRefundSaleReason("");
      setRefundDepositToo(false);
      setModalError(null);
    },
    onError: (err) => {
      setModalError(
        err instanceof ApiError ? err.detail : "Erro ao estornar venda."
      );
    },
  });

  const reversedIds = React.useMemo(() => {
    const set = new Set<string>();
    for (const tx of ledgerQuery.data?.transactions || []) {
      if (tx.reversed_transaction_id) {
        set.add(tx.reversed_transaction_id);
      }
    }
    return set;
  }, [ledgerQuery.data]);

  const dailyRegisterSection = (
    <div className="space-y-5">
      <Card className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Caixa Operacional do Dia
            </h2>
            <p className="text-xs text-muted-foreground">
              Conferência diária de entradas no fuso <strong>{studioTz}</strong>{" "}
              (sem exposição de custos ou margens).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="daily-register-date" className="mb-0 text-xs">
              Data:
            </Label>
            <Input
              id="daily-register-date"
              type="date"
              value={dailyDate}
              onChange={(e) => setDailyDate(e.target.value)}
              className="min-h-[40px] w-40"
            />
          </div>
        </div>
      </Card>

      {dailyRegisterQuery.data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="p-4">
              <p className="text-xs font-semibold uppercase text-muted-foreground">
                Checkout de Vendas ({dailyRegisterQuery.data.completed_sales_count})
              </p>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {formatCurrencyBRL(dailyRegisterQuery.data.sales_checkout_gross)}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-xs font-semibold uppercase text-muted-foreground">
                Sinais Recebidos ({dailyRegisterQuery.data.deposits_received_count})
              </p>
              <p className="mt-2 text-2xl font-bold text-emerald-700">
                {formatCurrencyBRL(
                  dailyRegisterQuery.data.deposits_received_gross
                )}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-xs font-semibold uppercase text-muted-foreground">
                Saídas por Estorno
              </p>
              <p className="mt-2 text-2xl font-bold text-red-700">
                {formatCurrencyBRL(
                  dailyRegisterQuery.data.refunds_outflow_total
                )}
              </p>
            </Card>
            <Card className="bg-slate-900 p-4 text-white">
              <p className="text-xs font-semibold uppercase text-slate-300">
                Saldo Operacional Líquido
              </p>
              <p className="mt-2 text-2xl font-bold">
                {formatCurrencyBRL(
                  dailyRegisterQuery.data.net_operational_cash
                )}
              </p>
            </Card>
          </div>

          <Card className="p-5 space-y-3">
            <h3 className="text-sm font-bold text-slate-900">
              Conferência por Meio de Pagamento (
              {formatPlainCalendarDate(dailyRegisterQuery.data.date)})
            </h3>
            {dailyRegisterQuery.data.by_payment_method.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nenhum recebimento registrado nesta data.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {dailyRegisterQuery.data.by_payment_method.map((item) => (
                  <div
                    key={item.method}
                    className="rounded-lg border border-border bg-slate-50 p-3"
                  >
                    <p className="text-xs font-bold text-slate-900">
                      {METHOD_LABELS[item.method]} ({item.count}x)
                    </p>
                    <p className="mt-1 text-base font-bold text-slate-900">
                      {formatCurrencyBRL(item.gross_amount)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Líquido: {formatCurrencyBRL(item.net_amount)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-5 space-y-3">
            <h3 className="text-sm font-bold text-slate-900">
              Vendas Registradas no Dia
            </h3>
            {dailyRegisterQuery.data.sales.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nenhuma venda registrada nesta data.
              </p>
            ) : (
              <div className="table-wrapper">
                <table
                  className="responsive-data-table text-left text-sm"
                  style={
                    {
                      "--label-2": '"Status"',
                      "--label-3": '"Itens"',
                      "--label-4": '"Sinal Abatido"',
                      "--label-5": '"Checkout"',
                    } as React.CSSProperties
                  }
                >
                  <thead className="bg-secondary text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2.5">Cliente</th>
                      <th className="px-3 py-2.5">Status</th>
                      <th className="px-3 py-2.5">Itens</th>
                      <th className="px-3 py-2.5">Sinal Abatido</th>
                      <th className="px-3 py-2.5">Cobrado no Checkout</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dailyRegisterQuery.data.sales.map((s) => (
                      <tr key={s.id} className="border-b border-border">
                        <th
                          scope="row"
                          className="px-3 py-2.5 font-semibold text-slate-900"
                        >
                          {s.client_name || "Balcão (Avulso)"}
                        </th>
                        <td className="px-3 py-2.5">
                          <Badge
                            tone={
                              s.status === "COMPLETED" ? "success" : "danger"
                            }
                          >
                            {s.status === "COMPLETED" ? "Concluída" : "Estornada"}
                          </Badge>
                        </td>
                        <td className="px-3 py-2.5 text-xs">
                          {s.items
                            .map(
                              (it) =>
                                `${it.quantity}x ${it.description_snapshot}`
                            )
                            .join(", ")}
                        </td>
                        <td className="px-3 py-2.5">
                          {formatCurrencyBRL(s.deposit_deducted_amount)}
                        </td>
                        <td className="px-3 py-2.5 font-semibold">
                          {formatCurrencyBRL(s.total_due_amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );

  // Recepção vê exclusivamente o Caixa Operacional do Dia (sem livro-caixa completo/despesas/lucro)
  if (!isOwner) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Caixa do Dia</h1>
            <p className="text-sm text-muted-foreground">
              Resumo operacional diário da recepção.
            </p>
          </div>
          <Link to="/pos">
            <Button>
              <ShoppingBag className="h-4 w-4" aria-hidden="true" />
              Ir para o PDV
            </Button>
          </Link>
        </div>
        {dailyRegisterSection}
      </div>
    );
  }

  const ledgerPanel = (
    <div className="space-y-5">
      <Card className="p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label htmlFor="ledger-from">De</Label>
              <Input
                id="ledger-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="min-h-[42px] w-40"
              />
            </div>
            <div>
              <Label htmlFor="ledger-to">Até</Label>
              <Input
                id="ledger-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="min-h-[42px] w-40"
              />
            </div>
          </div>

          <Button
            onClick={() => {
              setModalError(null);
              setManualCompetenceDate(todayIso);
              setManualOpen(true);
            }}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Lançar Despesa / Receita
          </Button>
        </div>
      </Card>

      {ledgerQuery.data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-muted-foreground">
                Entradas Líquidas
              </span>
              <ArrowUpCircle
                className="h-4 w-4 text-emerald-600"
                aria-hidden="true"
              />
            </div>
            <p className="mt-2 text-2xl font-bold text-emerald-700">
              {formatCurrencyBRL(ledgerQuery.data.total_inflows)}
            </p>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-muted-foreground">
                Saídas & Estornos
              </span>
              <ArrowDownCircle
                className="h-4 w-4 text-red-600"
                aria-hidden="true"
              />
            </div>
            <p className="mt-2 text-2xl font-bold text-red-700">
              {formatCurrencyBRL(ledgerQuery.data.total_outflows)}
            </p>
          </Card>

          <Card className="bg-slate-900 p-4 text-white">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-slate-300">
                Saldo Líquido do Período
              </span>
              <Wallet className="h-4 w-4 text-slate-300" aria-hidden="true" />
            </div>
            <p className="mt-2 text-2xl font-bold">
              {formatCurrencyBRL(ledgerQuery.data.net_balance)}
            </p>
          </Card>
        </div>
      )}

      <Card className="p-5">
        <div className="table-wrapper">
          <table
            className="responsive-data-table text-left text-sm"
            style={
              {
                "--label-2": '"Data"',
                "--label-3": '"Categoria"',
                "--label-4": '"Bruto / Taxa"',
                "--label-5": '"Líquido"',
                "--label-6": '"Ações"',
              } as React.CSSProperties
            }
          >
            <thead className="bg-secondary text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2.5">Descrição</th>
                <th className="px-3 py-2.5">Competência</th>
                <th className="px-3 py-2.5">Categoria</th>
                <th className="px-3 py-2.5">Bruto / Taxa</th>
                <th className="px-3 py-2.5">Impacto Caixa</th>
                <th className="px-3 py-2.5">Ações</th>
              </tr>
            </thead>
            <tbody>
              {ledgerQuery.data?.transactions.map((tx) => {
                const isInflow = tx.cash_flow_direction === "INFLOW";
                const canReverseManual =
                  !tx.reference_sale_id &&
                  !tx.reference_appointment_id &&
                  tx.category !== "COMMISSION_PAYOUT" &&
                  tx.type !== "REVERSAL" &&
                  !reversedIds.has(tx.id);
                const paidFmt = formatUtcInStudioTimezone(tx.paid_at, studioTz);

                return (
                  <tr key={tx.id} className="border-b border-border">
                    <th
                      scope="row"
                      className="px-3 py-2.5 font-semibold text-slate-900"
                    >
                      <div>{tx.description}</div>
                      <div className="text-xs font-normal text-muted-foreground">
                        {tx.payment_method
                          ? `${METHOD_LABELS[tx.payment_method]} • `
                          : ""}
                        {paidFmt.dateLabel} {paidFmt.timeLabel}
                      </div>
                    </th>
                    <td className="px-3 py-2.5">
                      {formatPlainCalendarDate(tx.competence_date)}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge
                        tone={
                          tx.type === "REVERSAL"
                            ? "warning"
                            : isInflow
                            ? "success"
                            : "neutral"
                        }
                      >
                        {CATEGORY_LABELS[tx.category]}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5 text-xs">
                      {formatCurrencyBRL(tx.gross_amount)}
                      {Number(tx.fee_amount) > 0
                        ? ` (-${formatCurrencyBRL(tx.fee_amount)})`
                        : ""}
                    </td>
                    <td
                      className={`px-3 py-2.5 font-bold ${
                        isInflow ? "text-emerald-700" : "text-red-700"
                      }`}
                    >
                      {isInflow ? "+" : "-"}
                      {formatCurrencyBRL(tx.net_amount)}
                    </td>
                    <td className="px-3 py-2.5">
                      {reversedIds.has(tx.id) ? (
                        <Badge tone="neutral">Estornado</Badge>
                      ) : canReverseManual ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setModalError(null);
                            setReverseReason("");
                            setReverseTxTarget(tx);
                          }}
                        >
                          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                          Estornar
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          Imutável
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {ledgerQuery.data?.transactions.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Nenhuma transação encontrada neste período.
            </p>
          )}
        </div>
      </Card>
    </div>
  );

  const salesAndRefundsPanel = (
    <div className="space-y-5">
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="sales-from">De</Label>
            <Input
              id="sales-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="min-h-[42px] w-40"
            />
          </div>
          <div>
            <Label htmlFor="sales-to">Até</Label>
            <Input
              id="sales-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="min-h-[42px] w-40"
            />
          </div>
          <div>
            <Label htmlFor="sales-status">Status</Label>
            <select
              id="sales-status"
              value={salesStatusFilter}
              onChange={(e) => setSalesStatusFilter(e.target.value)}
              className="flex min-h-[42px] rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="">Todas</option>
              <option value="COMPLETED">Concluídas</option>
              <option value="REFUNDED">Estornadas</option>
            </select>
          </div>
        </div>
      </Card>

      <div className="space-y-3">
        {salesQuery.data?.map((sale) => (
          <Card key={sale.id} className="p-4 sm:p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-bold uppercase text-muted-foreground">
                    #{sale.id.slice(0, 8)} •{" "}
                    {formatPlainCalendarDate(sale.competence_date)}
                  </span>
                  <Badge
                    tone={sale.status === "COMPLETED" ? "success" : "danger"}
                  >
                    {sale.status === "COMPLETED" ? "Concluída" : "Estornada"}
                  </Badge>
                  {sale.total_cost_snapshot !== undefined && (
                    <Badge tone="neutral">
                      CMV congelado: {formatCurrencyBRL(sale.total_cost_snapshot)}
                    </Badge>
                  )}
                </div>

                <p className="text-base font-semibold text-slate-900">
                  {sale.client_name || "Balcão (Avulso)"} — Subtotal{" "}
                  {formatCurrencyBRL(sale.subtotal_amount)}
                </p>

                <p className="text-xs text-muted-foreground">
                  Itens:{" "}
                  {sale.items
                    .map((i) => `${i.quantity}x ${i.description_snapshot}`)
                    .join(", ")}
                </p>

                <p className="text-xs text-muted-foreground">
                  Desconto: {formatCurrencyBRL(sale.discount_amount)} • Sinal
                  abatido: {formatCurrencyBRL(sale.deposit_deducted_amount)} •{" "}
                  <strong>
                    Checkout: {formatCurrencyBRL(sale.total_due_amount)}
                  </strong>
                </p>

                {sale.refund_reason && (
                  <p className="text-xs font-medium text-red-700">
                    Motivo do estorno: {sale.refund_reason}
                  </p>
                )}
              </div>

              {sale.status === "COMPLETED" && (
                <div>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      setModalError(null);
                      setRefundSaleReason("");
                      setRefundDepositToo(false);
                      setRefundSaleTarget(sale);
                    }}
                  >
                    <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                    Estornar Venda
                  </Button>
                </div>
              )}
            </div>
          </Card>
        ))}

        {salesQuery.data?.length === 0 && (
          <Card className="p-8 text-center text-sm text-muted-foreground">
            Nenhuma venda registrada no período selecionado.
          </Card>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Livro-Caixa Imutável & Vendas
          </h1>
          <p className="text-sm text-muted-foreground">
            Escrituração auditável sem exclusão física — estornos geram
            contra-lançamentos automáticos no caixa e no Kardex.
          </p>
        </div>
        <Link to="/pos">
          <Button>
            <ShoppingBag className="h-4 w-4" aria-hidden="true" />
            Abrir PDV
          </Button>
        </Link>
      </div>

      <AccessibleTabs
        ariaLabel="Visões financeiras do estúdio"
        activeTabId={activeTab}
        onTabChange={setActiveTab}
        tabs={[
          {
            id: "ledger",
            label: "Livro-Caixa & Despesas",
            content: ledgerPanel,
          },
          {
            id: "sales",
            label: "Vendas & Estornos",
            content: salesAndRefundsPanel,
          },
          {
            id: "daily",
            label: "Caixa Operacional do Dia",
            content: dailyRegisterSection,
          },
        ]}
      />

      {/* Modal Lançamento Manual */}
      <ModalDialog
        open={manualOpen}
        onClose={() => setManualOpen(false)}
        title="Novo Lançamento Manual no Livro-Caixa"
        description="Registre despesas operacionais, compras de estoque ou receitas avulsas."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createManualMutation.mutate();
          }}
          className="space-y-4"
        >
          {modalError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {modalError}
            </div>
          )}

          <div>
            <Label htmlFor="man-cat">Categoria *</Label>
            <select
              id="man-cat"
              value={manualCategory}
              onChange={(e) =>
                setManualCategory(e.target.value as ManualCategoryAllowed)
              }
              className="flex min-h-[46px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="FIXED_EXPENSE">Despesa Fixa (Aluguel, Luz, SaaS)</option>
              <option value="VARIABLE_EXPENSE">
                Despesa Variável (Descartáveis, Marketing)
              </option>
              <option value="INVENTORY_PURCHASE">
                Compra de Joias / Insumos (Saída de Caixa)
              </option>
              <option value="OTHER_INCOME">Outra Receita Operacional</option>
            </select>
          </div>

          <div>
            <Label htmlFor="man-desc">Descrição *</Label>
            <Input
              id="man-desc"
              required
              minLength={2}
              value={manualDesc}
              onChange={(e) => setManualDesc(e.target.value)}
              placeholder="Ex.: Aluguel sala comercial..."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="man-amount">Valor (R$) *</Label>
              <Input
                id="man-amount"
                inputMode="decimal"
                required
                value={manualAmount}
                onChange={(e) => setManualAmount(e.target.value)}
                placeholder="150.00"
              />
            </div>

            <div>
              <Label htmlFor="man-date">Data Competência *</Label>
              <Input
                id="man-date"
                type="date"
                required
                value={manualCompetenceDate}
                onChange={(e) => setManualCompetenceDate(e.target.value)}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="man-method">Meio de Pagamento</Label>
            <select
              id="man-method"
              value={manualMethod}
              onChange={(e) =>
                setManualMethod(e.target.value as PaymentMethodCode)
              }
              className="flex min-h-[46px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="PIX">PIX</option>
              <option value="CASH">Dinheiro</option>
              <option value="DEBIT_CARD">Cartão de Débito</option>
              <option value="CREDIT_CARD">Cartão de Crédito</option>
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setManualOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={createManualMutation.isPending}>
              {createManualMutation.isPending ? "Salvando..." : "Registrar"}
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Modal Estorno de Lançamento Manual */}
      <ModalDialog
        open={Boolean(reverseTxTarget)}
        onClose={() => setReverseTxTarget(null)}
        title="Estornar Lançamento Manual"
        description="O registro original será preservado e um contra-lançamento (REVERSAL) anulará seu saldo."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            reverseTxMutation.mutate();
          }}
          className="space-y-4"
        >
          {modalError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {modalError}
            </div>
          )}
          <div>
            <Label htmlFor="rev-reason">Motivo do Estorno *</Label>
            <Input
              id="rev-reason"
              required
              minLength={2}
              value={reverseReason}
              onChange={(e) => setReverseReason(e.target.value)}
              placeholder="Ex.: Valor digitado em duplicidade"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => setReverseTxTarget(null)}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={reverseTxMutation.isPending}
            >
              Confirmar Estorno Contábil
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Modal Estorno de Venda Completa */}
      <ModalDialog
        open={Boolean(refundSaleTarget)}
        onClose={() => setRefundSaleTarget(null)}
        title="Estornar Venda Completa"
        description="Devolve joias ao estoque (RETURN_REFUND), gera saída de estorno no caixa e reverte/compensa comissões."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            refundSaleMutation.mutate();
          }}
          className="space-y-4"
        >
          {modalError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {modalError}
            </div>
          )}

          <div>
            <Label htmlFor="refund-sale-reason">Motivo do Estorno *</Label>
            <Input
              id="refund-sale-reason"
              required
              minLength={2}
              value={refundSaleReason}
              onChange={(e) => setRefundSaleReason(e.target.value)}
              placeholder="Ex.: Desistência / troca integral autorizada"
            />
          </div>

          {refundSaleTarget &&
            Number(refundSaleTarget.deposit_deducted_amount) > 0 && (
              <label className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-950">
                <input
                  type="checkbox"
                  checked={refundDepositToo}
                  onChange={(e) => setRefundDepositToo(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-input"
                />
                <span>
                  <strong>
                    Devolver também o sinal do agendamento (
                    {formatCurrencyBRL(
                      refundSaleTarget.deposit_deducted_amount
                    )}
                    )
                  </strong>
                  <br />
                  Se desmarcado, o sinal será retido pelo estúdio (FORFEITED) e
                  apenas os pagamentos do checkout serão devolvidos.
                </span>
              </label>
            )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => setRefundSaleTarget(null)}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={refundSaleMutation.isPending}
            >
              {refundSaleMutation.isPending
                ? "Processando estorno..."
                : "Confirmar Estorno"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}
