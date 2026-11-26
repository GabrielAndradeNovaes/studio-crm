import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CreditCard } from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import type { PaymentMethodConfig, StudioDetails } from "@/lib/types";

export function StudioSettingsPage() {
  const { currentStudio, reloadSession } = useAuth();
  const queryClient = useQueryClient();

  const studioQuery = useQuery({
    queryKey: ["studio-current", currentStudio?.studio_id],
    queryFn: () => apiFetch<StudioDetails>("/studios/current"),
    enabled: Boolean(currentStudio),
  });

  const paymentMethodsQuery = useQuery({
    queryKey: ["payment-methods", currentStudio?.studio_id],
    queryFn: () => apiFetch<PaymentMethodConfig[]>("/studios/current/payment-methods"),
    enabled: Boolean(currentStudio),
  });

  const [name, setName] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [document, setDocument] = React.useState("");
  const [timezone, setTimezone] = React.useState("America/Sao_Paulo");
  const [deductsFee, setDeductsFee] = React.useState(false);
  const [savedNotice, setSavedNotice] = React.useState<string | null>(null);
  const [errorNotice, setErrorNotice] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (studioQuery.data) {
      setName(studioQuery.data.name);
      setPhone(studioQuery.data.phone || "");
      setDocument(studioQuery.data.document || "");
      setTimezone(studioQuery.data.timezone);
      setDeductsFee(studioQuery.data.commission_deducts_payment_fee);
    }
  }, [studioQuery.data]);

  const updateStudioMutation = useMutation({
    mutationFn: () =>
      apiFetch<StudioDetails>("/studios/current", {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          phone: phone.trim() || null,
          document: document.trim() || null,
          timezone: timezone.trim(),
          commission_deducts_payment_fee: deductsFee,
        }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["studio-current"] });
      await reloadSession();
      setErrorNotice(null);
      setSavedNotice("Configurações do estúdio salvas com sucesso.");
    },
    onError: (err) => {
      setSavedNotice(null);
      setErrorNotice(err instanceof ApiError ? err.detail : "Erro ao salvar.");
    },
  });

  const updateFeeMutation = useMutation({
    mutationFn: (payload: {
      id: string;
      fee_percentage: string;
      fixed_fee: string;
      is_active: boolean;
    }) =>
      apiFetch<PaymentMethodConfig>(`/studios/current/payment-methods/${payload.id}`, {
        method: "PUT",
        body: JSON.stringify({
          fee_percentage: payload.fee_percentage,
          fixed_fee: payload.fixed_fee,
          is_active: payload.is_active,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["payment-methods"] });
      setSavedNotice("Taxa do meio de pagamento atualizada.");
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          Configurações do Estúdio &amp; Taxas
        </h1>
        <p className="text-sm text-muted-foreground">
          Defina fuso horário de fechamento de caixa, regras de comissão e taxas de maquininha.
        </p>
      </div>

      {savedNotice && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3.5 text-sm text-emerald-900"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
          {savedNotice}
        </div>
      )}

      {errorNotice && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3.5 text-sm text-red-900"
        >
          {errorNotice}
        </div>
      )}

      <Card className="p-6">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            updateStudioMutation.mutate();
          }}
          className="space-y-4"
        >
          <h2 className="text-lg font-semibold text-slate-900">
            Dados Operacionais &amp; Governança de Comissão
          </h2>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="cfg-name">Nome do Estúdio *</Label>
              <Input
                id="cfg-name"
                name="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cfg-tz">Fuso Horário (IANA) *</Label>
              <Input
                id="cfg-tz"
                name="timezone"
                required
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cfg-phone">WhatsApp Comercial</Label>
              <Input
                id="cfg-phone"
                name="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cfg-doc">CNPJ / CPF</Label>
              <Input
                id="cfg-doc"
                name="document"
                value={document}
                onChange={(e) => setDocument(e.target.value)}
              />
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-lg border border-border bg-slate-50 p-4">
            <input
              id="cfg-deducts-fee"
              type="checkbox"
              checked={deductsFee}
              onChange={(e) => setDeductsFee(e.target.checked)}
              className="mt-1 h-4 w-4 accent-slate-900"
            />
            <div>
              <label htmlFor="cfg-deducts-fee" className="text-sm font-semibold text-slate-900">
                Descontar taxa do meio de pagamento antes de calcular comissão
              </label>
              <p className="text-xs text-muted-foreground">
                Quando marcado, a comissão do profissional incide sobre o valor líquido após taxa da maquininha; quando desmarcado, incide sobre o valor bruto vendido.
              </p>
            </div>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={updateStudioMutation.isPending}>
              {updateStudioMutation.isPending ? "Salvando..." : "Salvar configurações"}
            </Button>
          </div>
        </form>
      </Card>

      <Card className="p-6">
        <div className="mb-4 flex items-center gap-2">
          <CreditCard className="h-5 w-5 text-slate-700" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-slate-900">
            Taxas por Meio de Pagamento (PDV)
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {paymentMethodsQuery.data?.map((pm) => (
            <PaymentMethodRow
              key={pm.id}
              item={pm}
              onSave={(values) => updateFeeMutation.mutate({ id: pm.id, ...values })}
            />
          ))}
        </div>
      </Card>
    </div>
  );
}

function PaymentMethodRow({
  item,
  onSave,
}: {
  item: PaymentMethodConfig;
  onSave: (values: {
    fee_percentage: string;
    fixed_fee: string;
    is_active: boolean;
  }) => void;
}) {
  const [feePct, setFeePct] = React.useState(item.fee_percentage);
  const [fixedFee, setFixedFee] = React.useState(item.fixed_fee);
  const [active, setActive] = React.useState(item.is_active);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ fee_percentage: feePct, fixed_fee: fixedFee, is_active: active });
      }}
      className="space-y-3 rounded-lg border border-border p-4"
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-slate-900">{item.label}</span>
        <Badge tone={active ? "success" : "neutral"}>{item.method}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor={`pct-${item.id}`}>Taxa (%)</Label>
          <Input
            id={`pct-${item.id}`}
            name="fee_percentage"
            inputMode="decimal"
            value={feePct}
            onChange={(e) => setFeePct(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`fix-${item.id}`}>Taxa Fixa (R$)</Label>
          <Input
            id={`fix-${item.id}`}
            name="fixed_fee"
            inputMode="decimal"
            value={fixedFee}
            onChange={(e) => setFixedFee(e.target.value)}
          />
        </div>
      </div>

      <div className="flex items-center justify-between pt-1">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
            className="h-4 w-4 accent-slate-900"
          />
          Habilitado no PDV
        </label>
        <Button type="submit" variant="outline" size="sm">
          Atualizar taxa
        </Button>
      </div>
    </form>
  );
}
