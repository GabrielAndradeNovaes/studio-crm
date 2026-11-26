import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Plus,
  Syringe,
} from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import { buildWhatsAppUrl, formatPlainCalendarDate } from "@/lib/dates";
import type {
  ClientRecord,
  PiercingProductItem,
  PiercingProcedureItem,
  PiercingServiceItem,
} from "@/lib/types";

type ReminderWindow = "all_pending" | "overdue" | "next_7_days" | "next_30_days";

export function DownsizePage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();

  const [windowFilter, setWindowFilter] =
    React.useState<ReminderWindow>("all_pending");
  const [createOpen, setCreateOpen] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);

  // Form Novo Procedimento Técnico
  const [clientId, setClientId] = React.useState("");
  const [serviceId, setServiceId] = React.useState("");
  const [jewelryProductId, setJewelryProductId] = React.useState("");
  const [siteDetail, setSiteDetail] = React.useState("");
  const [sterilizationLot, setSterilizationLot] = React.useState("");
  const [healingNotes, setHealingNotes] = React.useState("");
  const [customReminderDate, setCustomReminderDate] = React.useState("");

  const remindersQuery = useQuery({
    queryKey: ["downsize-reminders", currentStudio?.studio_id, windowFilter],
    queryFn: () =>
      apiFetch<PiercingProcedureItem[]>(
        `/piercing/procedures/downsize-reminders?window=${windowFilter}`
      ),
    enabled: Boolean(currentStudio),
  });

  const clientsQuery = useQuery({
    queryKey: ["clients-for-proc", currentStudio?.studio_id],
    queryFn: () => apiFetch<ClientRecord[]>("/clients?limit=300"),
    enabled: Boolean(currentStudio && createOpen),
  });

  const servicesQuery = useQuery({
    queryKey: ["services-for-proc", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PiercingServiceItem[]>("/piercing/services?active_only=true"),
    enabled: Boolean(currentStudio && createOpen),
  });

  const productsQuery = useQuery({
    queryKey: ["jewelry-for-proc", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PiercingProductItem[]>(
        "/piercing/products?item_type=JEWELRY&active_only=true"
      ),
    enabled: Boolean(currentStudio && createOpen),
  });

  const createProcedureMutation = useMutation({
    mutationFn: () =>
      apiFetch<PiercingProcedureItem>("/piercing/procedures", {
        method: "POST",
        body: JSON.stringify({
          client_id: clientId,
          service_id: serviceId,
          jewelry_product_id: jewelryProductId || null,
          anatomical_site_detail: siteDetail.trim(),
          sterilization_lot: sterilizationLot.trim() || null,
          healing_notes: healingNotes.trim() || null,
          downsize_reminder_date: customReminderDate || null,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["downsize-reminders"] });
      setCreateOpen(false);
      setSiteDetail("");
      setSterilizationLot("");
      setHealingNotes("");
      setCustomReminderDate("");
      setFormError(null);
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiError ? err.detail : "Erro ao registrar procedimento."
      );
    },
  });

  const completeDownsizeMutation = useMutation({
    mutationFn: (procedureId: string) =>
      apiFetch<PiercingProcedureItem>(
        `/piercing/procedures/${procedureId}/complete-downsize`,
        {
          method: "POST",
          body: JSON.stringify({
            notes: "Downsize concluído.",
          }),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["downsize-reminders"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Fichas Técnicas &amp; Retornos de Downsize
          </h1>
          <p className="text-sm text-muted-foreground">
            Rastreabilidade de joia aplicada, lote de autoclave e acompanhamento ativo de cicatrização.
          </p>
        </div>

        <Button
          onClick={() => {
            setFormError(null);
            setCreateOpen(true);
          }}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Registrar Procedimento
        </Button>
      </div>

      {/* Filtro de Janela de Retorno */}
      <search aria-label="Filtrar janela de retornos de downsize">
        <div className="flex flex-wrap gap-2">
          {(
            [
              { id: "all_pending", label: "Todos Pendentes" },
              { id: "overdue", label: "Atrasados" },
              { id: "next_7_days", label: "Próximos 7 dias" },
              { id: "next_30_days", label: "Próximos 30 dias" },
            ] as { id: ReminderWindow; label: string }[]
          ).map((tab) => (
            <Button
              key={tab.id}
              size="sm"
              variant={windowFilter === tab.id ? "primary" : "outline"}
              onClick={() => setWindowFilter(tab.id)}
            >
              {tab.label}
            </Button>
          ))}
        </div>
      </search>

      <div className="space-y-3">
        {remindersQuery.data?.length === 0 && (
          <Card className="p-8 text-center text-sm text-muted-foreground">
            <Syringe
              className="mx-auto mb-2 h-8 w-8 text-slate-400"
              aria-hidden="true"
            />
            Nenhum retorno pendente de downsize para esta janela.
          </Card>
        )}

        {remindersQuery.data?.map((proc) => (
          <Card key={proc.id} className="p-4 sm:p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-bold text-slate-900">
                    {proc.client_name}
                  </span>
                  {proc.is_overdue ? (
                    <Badge tone="danger" className="gap-1">
                      <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                      Atrasado ({Math.abs(proc.days_until_due || 0)}d)
                    </Badge>
                  ) : (
                    <Badge tone="info">
                      Retorno em{" "}
                      {proc.downsize_reminder_date
                        ? formatPlainCalendarDate(proc.downsize_reminder_date)
                        : "—"}
                    </Badge>
                  )}
                </div>

                <p className="text-sm text-slate-800">
                  <strong>{proc.anatomical_site_detail}</strong> •{" "}
                  {proc.service_name}
                  {proc.jewelry_name ? ` • Joia: ${proc.jewelry_name}` : ""}
                </p>

                <p className="text-xs text-muted-foreground">
                  Profissional: {proc.professional_name}
                  {proc.sterilization_lot
                    ? ` • Lote Autoclave: ${proc.sterilization_lot}`
                    : ""}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {proc.client_whatsapp && (
                  <a
                    href={buildWhatsAppUrl(
                      proc.client_whatsapp,
                      `Olá ${proc.client_name.split(" ")[0]}! Aqui é do ${currentStudio?.studio_name}. Chegou o período ideal para avaliarmos a cicatrização da sua perfuração (${proc.anatomical_site_detail}) e realizarmos o downsize (troca por haste menor). Vamos agendar seu horário?`
                    )}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-[40px] items-center justify-center gap-1.5 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-900 hover:bg-emerald-100"
                  >
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    Lembrar no WhatsApp
                  </a>
                )}

                <Button
                  size="sm"
                  onClick={() => completeDownsizeMutation.mutate(proc.id)}
                  disabled={completeDownsizeMutation.isPending}
                >
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Marcar Downsize Concluído
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Modal Registrar Procedimento Técnico */}
      <ModalDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Registrar Ficha Técnica de Perfuração"
        description="Registra rastreabilidade clínica e agenda o lembrete de downsize (não desconta estoque até a venda no PDV)."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createProcedureMutation.mutate();
          }}
          className="max-h-[75vh] space-y-4 overflow-y-auto pr-1"
        >
          {formError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {formError}
            </div>
          )}

          <div>
            <Label htmlFor="proc-client">Cliente *</Label>
            <select
              id="proc-client"
              required
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="">Selecione o cliente...</option>
              {clientsQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="proc-service">Serviço Realizado *</Label>
            <select
              id="proc-service"
              required
              value={serviceId}
              onChange={(e) => setServiceId(e.target.value)}
              className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="">Selecione o serviço...</option>
              {servicesQuery.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} (Downsize padrão: {s.return_days_downsize ?? "—"}d)
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="proc-jewelry">
              Joia Aplicada (Rastreabilidade — sem baixa automática de estoque)
            </Label>
            <select
              id="proc-jewelry"
              value={jewelryProductId}
              onChange={(e) => setJewelryProductId(e.target.value)}
              className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="">Nenhuma / Joia própria esterilizada</option>
              {productsQuery.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.material || ""} {p.gauge_thickness || ""}{" "}
                  {p.length_diameter || ""})
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="proc-site">Local Anatômico Detalhado *</Label>
            <Input
              id="proc-site"
              required
              value={siteDetail}
              onChange={(e) => setSiteDetail(e.target.value)}
              placeholder="Ex.: Orelha esquerda — Helix superior"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="proc-lot">Lote de Autoclave / Esterilização</Label>
              <Input
                id="proc-lot"
                value={sterilizationLot}
                onChange={(e) => setSterilizationLot(e.target.value)}
                placeholder="Ex.: AUTO-2026-1126"
              />
            </div>
            <div>
              <Label htmlFor="proc-rem-date">
                Data de Downsize (vazio = automática)
              </Label>
              <Input
                id="proc-rem-date"
                type="date"
                value={customReminderDate}
                onChange={(e) => setCustomReminderDate(e.target.value)}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="proc-notes">Observações Técnicas / Cicatrização</Label>
            <textarea
              id="proc-notes"
              rows={2}
              value={healingNotes}
              onChange={(e) => setHealingNotes(e.target.value)}
              className="w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-sm"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={createProcedureMutation.isPending}>
              {createProcedureMutation.isPending
                ? "Salvando..."
                : "Salvar ficha técnica"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}
