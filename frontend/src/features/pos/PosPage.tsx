import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  CheckCircle2,
  CreditCard,
  Gem,
  Plus,
  ShoppingBag,
  Syringe,
  Trash2,
} from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import { formatCurrencyBRL } from "@/lib/dates";
import type {
  AppointmentItem,
  ClientRecord,
  PaymentMethodCode,
  PaymentMethodConfig,
  PiercingProductItem,
  PiercingServiceItem,
  SaleItemKind,
  SaleRecord,
  TeamMemberDirectory,
} from "@/lib/types";

interface CartLine {
  uid: string;
  itemKind: SaleItemKind;
  serviceId: string | null;
  productId: string | null;
  label: string;
  professionalId: string;
  quantity: number;
  maxStock: number | null;
  unitPrice: string;
  discountAmount: string;
}

interface PaymentSplitLine {
  uid: string;
  method: PaymentMethodCode;
  amount: string;
}

function toCents(val: string | number): number {
  const cleaned = String(val ?? "0").replace(",", ".");
  const parsed = Number(cleaned);
  if (!Number.isFinite(parsed)) return 0;
  return Math.round(parsed * 100);
}

function centsToFixed(cents: number): string {
  return (cents / 100).toFixed(2);
}

const METHOD_LABELS: Record<PaymentMethodCode, string> = {
  PIX: "PIX",
  CREDIT_CARD: "Cartão de Crédito",
  DEBIT_CARD: "Cartão de Débito",
  CASH: "Dinheiro",
};

export function PosPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const linkedAppointmentParam = searchParams.get("appointmentId") || "";

  const [appointmentId, setAppointmentId] = React.useState(
    linkedAppointmentParam
  );
  const [clientId, setClientId] = React.useState("");
  const [defaultProfId, setDefaultProfId] = React.useState("");
  const [saleDiscount, setSaleDiscount] = React.useState("0.00");
  const [notes, setNotes] = React.useState("");
  const [cart, setCart] = React.useState<CartLine[]>([]);
  const [payments, setPayments] = React.useState<PaymentSplitLine[]>([
    { uid: "pay-1", method: "PIX", amount: "0.00" },
  ]);
  const [selectedServiceToAdd, setSelectedServiceToAdd] = React.useState("");
  const [selectedProductToAdd, setSelectedProductToAdd] = React.useState("");
  const [checkoutError, setCheckoutError] = React.useState<string | null>(null);
  const [completedSale, setCompletedSale] = React.useState<SaleRecord | null>(
    null
  );
  const hydratedAppointmentRef = React.useRef<string | null>(null);

  const hasPiercing = Boolean(
    currentStudio?.enabled_modules?.includes("piercing")
  );

  const clientsQuery = useQuery({
    queryKey: ["clients-pos", currentStudio?.studio_id],
    queryFn: () => apiFetch<ClientRecord[]>("/clients?limit=300"),
    enabled: Boolean(currentStudio),
  });

  const directoryQuery = useQuery({
    queryKey: ["team-directory", currentStudio?.studio_id],
    queryFn: () => apiFetch<TeamMemberDirectory[]>("/team/directory"),
    enabled: Boolean(currentStudio),
  });

  const servicesQuery = useQuery({
    queryKey: ["piercing-services-pos", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PiercingServiceItem[]>("/piercing/services?active_only=true"),
    enabled: Boolean(currentStudio && hasPiercing),
  });

  const productsQuery = useQuery({
    queryKey: ["piercing-products-pos", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PiercingProductItem[]>("/piercing/products?active_only=true"),
    enabled: Boolean(currentStudio && hasPiercing),
  });

  const paymentMethodsQuery = useQuery({
    queryKey: ["payment-methods", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PaymentMethodConfig[]>("/studios/current/payment-methods"),
    enabled: Boolean(currentStudio),
  });

  const linkedAppointmentQuery = useQuery({
    queryKey: ["pos-appointment-detail", currentStudio?.studio_id, appointmentId],
    queryFn: () => apiFetch<AppointmentItem>(`/appointments/${appointmentId}`),
    enabled: Boolean(currentStudio && appointmentId),
  });

  // Preenche automaticamente dados quando vem de ?appointmentId=
  React.useEffect(() => {
    const appt = linkedAppointmentQuery.data;
    if (!appt || hydratedAppointmentRef.current === appt.id) return;
    // Se há serviço principal, aguarda catálogo carregar para já adicionar ao carrinho
    if (appt.service_id && hasPiercing && !servicesQuery.data) return;

    hydratedAppointmentRef.current = appt.id;
    setClientId(appt.client_id);
    setDefaultProfId(appt.professional_id);

    if (appt.service_id && servicesQuery.data) {
      const svc = servicesQuery.data.find((s) => s.id === appt.service_id);
      if (svc) {
        setCart((prev) => {
          if (prev.length > 0) return prev;
          return [
            {
              uid: `svc-${Date.now()}`,
              itemKind: "PIERCING_SERVICE",
              serviceId: svc.id,
              productId: null,
              label: `${svc.name} (${svc.anatomical_site})`,
              professionalId: appt.professional_id,
              quantity: 1,
              maxStock: null,
              unitPrice: svc.base_price,
              discountAmount: "0.00",
            },
          ];
        });
      }
    }
  }, [linkedAppointmentQuery.data, servicesQuery.data, hasPiercing]);

  const linkedAppt = linkedAppointmentQuery.data;
  const depositDeductedCents =
    linkedAppt && linkedAppt.deposit_status === "PAID"
      ? toCents(linkedAppt.deposit_amount)
      : 0;

  const subtotalCents = cart.reduce((acc, line) => {
    const lineTotal = Math.max(
      0,
      line.quantity * toCents(line.unitPrice) - toCents(line.discountAmount)
    );
    return acc + lineTotal;
  }, 0);

  const discountCents = toCents(saleDiscount);
  const netSaleValueCents = Math.max(0, subtotalCents - discountCents);
  const totalDueCents = Math.max(0, netSaleValueCents - depositDeductedCents);

  // Mantém valor sincronizado automaticamente quando há apenas 1 linha de pagamento
  React.useEffect(() => {
    if (totalDueCents === 0) {
      setPayments([]);
      return;
    }
    setPayments((prev) => {
      if (prev.length === 0) {
        return [
          {
            uid: `pay-${Date.now()}`,
            method: "PIX",
            amount: centsToFixed(totalDueCents),
          },
        ];
      }
      if (prev.length === 1) {
        const nextAmt = centsToFixed(totalDueCents);
        if (prev[0].amount === nextAmt) return prev;
        return [{ ...prev[0], amount: nextAmt }];
      }
      return prev;
    });
  }, [totalDueCents]);

  const paidSumCents = payments.reduce((acc, p) => acc + toCents(p.amount), 0);
  const remainingSplitCents = totalDueCents - paidSumCents;

  const addServiceToCart = () => {
    if (!selectedServiceToAdd || !servicesQuery.data) return;
    const svc = servicesQuery.data.find((s) => s.id === selectedServiceToAdd);
    if (!svc) return;
    const fallbackProf =
      defaultProfId || directoryQuery.data?.[0]?.user_id || "";
    setCart((prev) => [
      ...prev,
      {
        uid: `svc-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        itemKind: "PIERCING_SERVICE",
        serviceId: svc.id,
        productId: null,
        label: `${svc.name} (${svc.anatomical_site})`,
        professionalId: fallbackProf,
        quantity: 1,
        maxStock: null,
        unitPrice: svc.base_price,
        discountAmount: "0.00",
      },
    ]);
    setSelectedServiceToAdd("");
  };

  const addProductToCart = () => {
    if (!selectedProductToAdd || !productsQuery.data) return;
    const prod = productsQuery.data.find((p) => p.id === selectedProductToAdd);
    if (!prod || prod.stock_quantity <= 0) return;

    const alreadyInCartQty = cart
      .filter((c) => c.productId === prod.id)
      .reduce((acc, c) => acc + c.quantity, 0);
    if (alreadyInCartQty >= prod.stock_quantity) {
      setCheckoutError(
        `Saldo máximo disponível de "${prod.name}" (${prod.stock_quantity} un.) já está no carrinho.`
      );
      return;
    }

    const fallbackProf =
      defaultProfId || directoryQuery.data?.[0]?.user_id || "";
    setCart((prev) => [
      ...prev,
      {
        uid: `prd-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        itemKind: "PIERCING_PRODUCT",
        serviceId: null,
        productId: prod.id,
        label: `${prod.name}${prod.material ? ` • ${prod.material}` : ""}`,
        professionalId: fallbackProf,
        quantity: 1,
        maxStock: prod.stock_quantity,
        unitPrice: prod.sale_price,
        discountAmount: "0.00",
      },
    ]);
    setSelectedProductToAdd("");
    setCheckoutError(null);
  };

  const updateCartLine = (uid: string, patch: Partial<CartLine>) => {
    setCart((prev) =>
      prev.map((line) => (line.uid === uid ? { ...line, ...patch } : line))
    );
  };

  const removeCartLine = (uid: string) => {
    setCart((prev) => prev.filter((line) => line.uid !== uid));
  };

  const addPaymentRow = () => {
    const activeMethods = (paymentMethodsQuery.data || []).filter(
      (m) => m.is_active
    );
    const fallbackMethod: PaymentMethodCode =
      activeMethods[1]?.method || activeMethods[0]?.method || "CREDIT_CARD";
    const suggested = Math.max(0, remainingSplitCents);
    setPayments((prev) => [
      ...prev,
      {
        uid: `pay-${Date.now()}-${Math.random().toString(36).slice(2, 5)}`,
        method: fallbackMethod,
        amount: centsToFixed(suggested > 0 ? suggested : 0),
      },
    ]);
  };

  const checkoutMutation = useMutation({
    mutationFn: () => {
      return apiFetch<SaleRecord>("/finance/sales", {
        method: "POST",
        body: JSON.stringify({
          client_id: clientId || null,
          appointment_id: appointmentId || null,
          professional_id: defaultProfId || null,
          discount_amount: centsToFixed(discountCents),
          notes: notes.trim() || null,
          items: cart.map((line) => ({
            item_kind: line.itemKind,
            service_id: line.serviceId,
            product_id: line.productId,
            professional_id: line.professionalId || null,
            quantity: line.quantity,
            unit_price: centsToFixed(toCents(line.unitPrice)),
            discount_amount: centsToFixed(toCents(line.discountAmount)),
          })),
          payments:
            totalDueCents === 0
              ? []
              : payments.map((p) => ({
                  method: p.method,
                  amount: centsToFixed(toCents(p.amount)),
                })),
        }),
      });
    },
    onSuccess: (sale) => {
      queryClient.invalidateQueries({ queryKey: ["piercing-products-pos"] });
      queryClient.invalidateQueries({ queryKey: ["piercing-products"] });
      queryClient.invalidateQueries({ queryKey: ["piercing-low-stock"] });
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      queryClient.invalidateQueries({ queryKey: ["finance-sales"] });
      queryClient.invalidateQueries({ queryKey: ["finance-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["finance-daily-register"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["finance-commissions"] });
      setCheckoutError(null);
      setCompletedSale(sale);
    },
    onError: (err) => {
      setCheckoutError(
        err instanceof ApiError
          ? err.detail
          : "Não foi possível concluir o fechamento da venda."
      );
    },
  });

  const resetPosForNewSale = () => {
    setCompletedSale(null);
    hydratedAppointmentRef.current = null;
    setAppointmentId("");
    setSearchParams({});
    setClientId("");
    setSaleDiscount("0.00");
    setNotes("");
    setCart([]);
    setPayments([{ uid: "pay-1", method: "PIX", amount: "0.00" }]);
    setCheckoutError(null);
  };

  const activeMethods = (paymentMethodsQuery.data || []).filter(
    (m) => m.is_active
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            PDV — Fechamento de Venda
          </h1>
          <p className="text-sm text-muted-foreground">
            Combine perfurações e joias com baixa atômica de estoque, abatimento
            automático de sinal e split de pagamento.
          </p>
        </div>
        {appointmentId && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              hydratedAppointmentRef.current = null;
              setAppointmentId("");
              setSearchParams({});
            }}
          >
            Desvincular agendamento (Venda Avulsa)
          </Button>
        )}
      </div>

      {linkedAppt && (
        <Card className="border-emerald-300 bg-emerald-50/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-emerald-900">
                Atendimento Vinculado da Agenda
              </p>
              <p className="text-sm font-semibold text-slate-900">
                {linkedAppt.client_name} • Profissional:{" "}
                {linkedAppt.professional_name}
                {linkedAppt.service_name ? ` • ${linkedAppt.service_name}` : ""}
              </p>
            </div>
            {linkedAppt.deposit_status === "PAID" ? (
              <Badge tone="success">
                Sinal já Pago Abatido:{" "}
                {formatCurrencyBRL(linkedAppt.deposit_amount)} (
                {linkedAppt.deposit_payment_method})
              </Badge>
            ) : (
              <Badge tone="neutral">Sem sinal pendente de abatimento</Badge>
            )}
          </div>
        </Card>
      )}

      {checkoutError && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3.5 text-sm font-medium text-red-900"
        >
          {checkoutError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Coluna Esquerda: Identificação e Carrinho */}
        <div className="space-y-6 lg:col-span-7">
          <Card className="space-y-4 p-5">
            <h2 className="text-base font-bold text-slate-900">
              1. Cliente & Profissional Responsável
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="pos-client">Cliente (opcional em balcão)</Label>
                <select
                  id="pos-client"
                  value={clientId}
                  disabled={Boolean(linkedAppt)}
                  onChange={(e) => setClientId(e.target.value)}
                  className="flex min-h-[46px] w-full rounded-md border border-input bg-card px-3 text-sm disabled:opacity-70"
                >
                  <option value="">Venda avulsa no balcão</option>
                  {clientsQuery.data?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.full_name} — {c.whatsapp}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <Label htmlFor="pos-default-prof">
                  Profissional Padrão dos Itens *
                </Label>
                <select
                  id="pos-default-prof"
                  value={defaultProfId}
                  onChange={(e) => setDefaultProfId(e.target.value)}
                  className="flex min-h-[46px] w-full rounded-md border border-input bg-card px-3 text-sm"
                >
                  <option value="">Selecione o profissional...</option>
                  {directoryQuery.data?.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name} ({m.role})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </Card>

          {/* Adição de Itens */}
          <Card className="space-y-4 p-5">
            <h2 className="text-base font-bold text-slate-900">
              2. Itens da Venda (Perfurações & Joias/Produtos)
            </h2>

            {hasPiercing && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="pos-add-service">
                    <span className="inline-flex items-center gap-1.5">
                      <Syringe className="h-3.5 w-3.5" aria-hidden="true" />
                      Adicionar Serviço
                    </span>
                  </Label>
                  <div className="flex gap-2">
                    <select
                      id="pos-add-service"
                      value={selectedServiceToAdd}
                      onChange={(e) => setSelectedServiceToAdd(e.target.value)}
                      className="flex min-h-[44px] min-w-0 flex-1 rounded-md border border-input bg-card px-2.5 text-sm"
                    >
                      <option value="">Escolha uma perfuração...</option>
                      {servicesQuery.data?.map((svc) => (
                        <option key={svc.id} value={svc.id}>
                          {svc.name} — {formatCurrencyBRL(svc.base_price)}
                        </option>
                      ))}
                    </select>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={!selectedServiceToAdd}
                      onClick={addServiceToCart}
                      aria-label="Adicionar serviço selecionado"
                    >
                      <Plus className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="pos-add-product">
                    <span className="inline-flex items-center gap-1.5">
                      <Gem className="h-3.5 w-3.5" aria-hidden="true" />
                      Adicionar Joia / Pós-Piercing
                    </span>
                  </Label>
                  <div className="flex gap-2">
                    <select
                      id="pos-add-product"
                      value={selectedProductToAdd}
                      onChange={(e) => setSelectedProductToAdd(e.target.value)}
                      className="flex min-h-[44px] min-w-0 flex-1 rounded-md border border-input bg-card px-2.5 text-sm"
                    >
                      <option value="">Escolha do estoque...</option>
                      {productsQuery.data?.map((prod) => (
                        <option
                          key={prod.id}
                          value={prod.id}
                          disabled={prod.stock_quantity <= 0}
                        >
                          {prod.name} ({prod.stock_quantity} disp.) —{" "}
                          {formatCurrencyBRL(prod.sale_price)}
                        </option>
                      ))}
                    </select>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={!selectedProductToAdd}
                      onClick={addProductToCart}
                      aria-label="Adicionar produto selecionado"
                    >
                      <Plus className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {cart.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                <ShoppingBag
                  className="mx-auto mb-2 h-7 w-7 text-slate-400"
                  aria-hidden="true"
                />
                Adicione ao menos um serviço ou joia para calcular o fechamento.
              </div>
            ) : (
              <div className="space-y-3">
                {cart.map((line) => {
                  const lineTotalCents = Math.max(
                    0,
                    line.quantity * toCents(line.unitPrice) -
                      toCents(line.discountAmount)
                  );
                  return (
                    <div
                      key={line.uid}
                      className="rounded-lg border border-border bg-slate-50/70 p-3.5 space-y-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge
                              tone={
                                line.itemKind === "PIERCING_SERVICE"
                                  ? "info"
                                  : "warning"
                              }
                            >
                              {line.itemKind === "PIERCING_SERVICE"
                                ? "Serviço"
                                : "Estoque"}
                            </Badge>
                            {line.maxStock !== null && (
                              <span className="text-xs text-muted-foreground">
                                Estoque atual: {line.maxStock} un.
                              </span>
                            )}
                          </div>
                          <p className="mt-1 text-sm font-semibold text-slate-900">
                            {line.label}
                          </p>
                        </div>

                        <button
                          type="button"
                          onClick={() => removeCartLine(line.uid)}
                          aria-label={`Remover ${line.label}`}
                          className="rounded-md p-1.5 text-muted-foreground hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                        <div>
                          <Label htmlFor={`qty-${line.uid}`}>Qtd.</Label>
                          <Input
                            id={`qty-${line.uid}`}
                            type="number"
                            min={1}
                            max={line.maxStock ?? 500}
                            value={line.quantity}
                            onChange={(e) => {
                              const raw = Math.max(
                                1,
                                Number(e.target.value) || 1
                              );
                              const clamped =
                                line.maxStock !== null
                                  ? Math.min(raw, line.maxStock)
                                  : raw;
                              updateCartLine(line.uid, { quantity: clamped });
                            }}
                            className="min-h-[40px]"
                          />
                        </div>

                        <div>
                          <Label htmlFor={`price-${line.uid}`}>
                            Unitário (R$)
                          </Label>
                          <Input
                            id={`price-${line.uid}`}
                            inputMode="decimal"
                            value={line.unitPrice}
                            onChange={(e) =>
                              updateCartLine(line.uid, {
                                unitPrice: e.target.value,
                              })
                            }
                            className="min-h-[40px]"
                          />
                        </div>

                        <div>
                          <Label htmlFor={`disc-${line.uid}`}>Desc. Item</Label>
                          <Input
                            id={`disc-${line.uid}`}
                            inputMode="decimal"
                            value={line.discountAmount}
                            onChange={(e) =>
                              updateCartLine(line.uid, {
                                discountAmount: e.target.value,
                              })
                            }
                            className="min-h-[40px]"
                          />
                        </div>

                        <div>
                          <Label htmlFor={`prof-${line.uid}`}>Comissão p/</Label>
                          <select
                            id={`prof-${line.uid}`}
                            value={line.professionalId}
                            onChange={(e) =>
                              updateCartLine(line.uid, {
                                professionalId: e.target.value,
                              })
                            }
                            className="flex min-h-[40px] w-full rounded-md border border-input bg-card px-2 text-xs"
                          >
                            <option value="">Sem comissão</option>
                            {directoryQuery.data?.map((m) => (
                              <option key={m.user_id} value={m.user_id}>
                                {m.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div className="flex justify-end border-t border-border/60 pt-2 text-xs">
                        <span className="text-muted-foreground">
                          Total do item:{" "}
                          <strong className="text-sm text-slate-900">
                            {formatCurrencyBRL(centsToFixed(lineTotalCents))}
                          </strong>
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        {/* Coluna Direita: Resumo Contábil e Split de Pagamentos */}
        <div className="space-y-6 lg:col-span-5">
          <Card className="space-y-4 p-5">
            <h2 className="text-base font-bold text-slate-900">
              3. Resumo & Abatimento de Sinal
            </h2>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="pos-sale-discount">
                  Desconto Geral da Venda (R$)
                </Label>
                <Input
                  id="pos-sale-discount"
                  inputMode="decimal"
                  value={saleDiscount}
                  onChange={(e) => setSaleDiscount(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="pos-notes">Observações do Recibo</Label>
                <Input
                  id="pos-notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Ex.: Upgrade titânio PVD..."
                />
              </div>
            </div>

            <div className="space-y-2 rounded-lg bg-slate-900 p-4 text-sm text-slate-100">
              <div className="flex justify-between">
                <span className="text-slate-300">Subtotal dos Itens</span>
                <span>{formatCurrencyBRL(centsToFixed(subtotalCents))}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-300">(-) Desconto Geral</span>
                <span>{formatCurrencyBRL(centsToFixed(discountCents))}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-emerald-300">
                  (-) Sinal Pago Abatido
                </span>
                <span className="font-semibold text-emerald-300">
                  {formatCurrencyBRL(centsToFixed(depositDeductedCents))}
                </span>
              </div>
              <div className="flex items-baseline justify-between border-t border-slate-700 pt-2.5 text-base font-bold text-white">
                <span>Restante a Pagar Agora</span>
                <span className="text-xl">
                  {formatCurrencyBRL(centsToFixed(totalDueCents))}
                </span>
              </div>
            </div>
          </Card>

          <Card className="space-y-4 p-5">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-bold text-slate-900">
                <CreditCard className="h-4 w-4" aria-hidden="true" />
                4. Pagamento no Checkout
              </h2>
              {totalDueCents > 0 && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={addPaymentRow}
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  Dividir (Split)
                </Button>
              )}
            </div>

            {totalDueCents === 0 ? (
              <div className="rounded-md bg-emerald-50 p-3 text-xs font-medium text-emerald-900">
                Valor restante zerado (100% coberto pelo sinal já recebido ou
                desconto). Nenhum pagamento adicional será cobrado no caixa.
              </div>
            ) : (
              <div className="space-y-3">
                {payments.map((pay, idx) => {
                  const cfg = activeMethods.find((m) => m.method === pay.method);
                  return (
                    <div
                      key={pay.uid}
                      className="flex flex-wrap items-end gap-2 rounded-lg border border-border p-3"
                    >
                      <div className="min-w-[140px] flex-1">
                        <Label htmlFor={`pay-method-${pay.uid}`}>
                          Meio #{idx + 1}
                        </Label>
                        <select
                          id={`pay-method-${pay.uid}`}
                          value={pay.method}
                          onChange={(e) =>
                            setPayments((prev) =>
                              prev.map((row) =>
                                row.uid === pay.uid
                                  ? {
                                      ...row,
                                      method: e.target
                                        .value as PaymentMethodCode,
                                    }
                                  : row
                              )
                            )
                          }
                          className="flex min-h-[42px] w-full rounded-md border border-input bg-card px-2.5 text-sm"
                        >
                          {(activeMethods.length > 0
                            ? activeMethods
                            : [
                                {
                                  method: "PIX" as PaymentMethodCode,
                                  label: "PIX",
                                  fee_percentage: "0.00",
                                },
                              ]
                          ).map((m) => (
                            <option key={m.method} value={m.method}>
                              {m.label} (taxa {m.fee_percentage}%)
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="w-36">
                        <Label htmlFor={`pay-amt-${pay.uid}`}>Valor (R$)</Label>
                        <Input
                          id={`pay-amt-${pay.uid}`}
                          inputMode="decimal"
                          value={pay.amount}
                          onChange={(e) =>
                            setPayments((prev) =>
                              prev.map((row) =>
                                row.uid === pay.uid
                                  ? { ...row, amount: e.target.value }
                                  : row
                              )
                            )
                          }
                          className="min-h-[42px]"
                        />
                      </div>

                      {payments.length > 1 && (
                        <button
                          type="button"
                          aria-label={`Remover parcela ${idx + 1}`}
                          onClick={() =>
                            setPayments((prev) =>
                              prev.filter((row) => row.uid !== pay.uid)
                            )
                          }
                          className="mb-1 rounded-md p-2 text-muted-foreground hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                      )}

                      {cfg && (
                        <p className="w-full text-[11px] text-muted-foreground">
                          Taxa configurada: {cfg.fee_percentage}% +{" "}
                          {formatCurrencyBRL(cfg.fixed_fee)}
                        </p>
                      )}
                    </div>
                  );
                })}

                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">
                    Soma informada:{" "}
                    <strong>
                      {formatCurrencyBRL(centsToFixed(paidSumCents))}
                    </strong>
                  </span>
                  {remainingSplitCents !== 0 ? (
                    <span className="font-semibold text-amber-700">
                      Diferença:{" "}
                      {formatCurrencyBRL(centsToFixed(remainingSplitCents))}
                    </span>
                  ) : (
                    <span className="font-semibold text-emerald-700">
                      Split conferido (R$ 0,00 pendente)
                    </span>
                  )}
                </div>
              </div>
            )}

            <Button
              type="button"
              className="w-full"
              disabled={
                cart.length === 0 ||
                (totalDueCents > 0 && remainingSplitCents !== 0) ||
                checkoutMutation.isPending
              }
              onClick={() => checkoutMutation.mutate()}
            >
              <ShoppingBag className="h-4 w-4" aria-hidden="true" />
              {checkoutMutation.isPending
                ? "Processando baixa e livro-caixa..."
                : "Finalizar Venda & Baixar Estoque"}
            </Button>
          </Card>
        </div>
      </div>

      {/* Modal de Venda Concluída */}
      <ModalDialog
        open={Boolean(completedSale)}
        onClose={resetPosForNewSale}
        title="Venda Concluída com Sucesso"
        description="Estoque atualizado no Kardex, livro-caixa escriturado e comissões calculadas."
      >
        {completedSale && (
          <div className="space-y-4 text-sm">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-emerald-900">
                <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
                Recibo #{completedSale.id.slice(0, 8).toUpperCase()}
              </div>
              <p className="text-xs text-emerald-800">
                Cliente:{" "}
                <strong>{completedSale.client_name || "Balcão (Avulso)"}</strong>
              </p>
              <p className="text-xs text-emerald-800">
                Subtotal: {formatCurrencyBRL(completedSale.subtotal_amount)} •
                Sinal abatido:{" "}
                {formatCurrencyBRL(completedSale.deposit_deducted_amount)} •
                Cobrado no checkout:{" "}
                <strong>
                  {formatCurrencyBRL(completedSale.total_due_amount)}
                </strong>
              </p>
            </div>

            {completedSale.payments.length > 0 && (
              <div className="space-y-1 text-xs text-muted-foreground">
                <p className="font-semibold text-slate-900">
                  Pagamentos registrados:
                </p>
                {completedSale.payments.map((p) => (
                  <p key={p.id}>
                    • {METHOD_LABELS[p.method]}:{" "}
                    {formatCurrencyBRL(p.gross_amount)} (líquido:{" "}
                    {formatCurrencyBRL(p.net_amount)})
                  </p>
                ))}
              </div>
            )}

            <div className="flex flex-wrap justify-end gap-2 pt-2">
              <Button
                variant="outline"
                onClick={() => navigate("/finance/cashflow")}
              >
                Ver Caixa
              </Button>
              <Button onClick={resetPosForNewSale}>Nova Venda no PDV</Button>
            </div>
          </div>
        )}
      </ModalDialog>
    </div>
  );
}
