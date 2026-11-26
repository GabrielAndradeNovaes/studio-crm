import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Copy,
  DollarSign,
  ExternalLink,
  Link2,
  Plus,
} from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import {
  buildWhatsAppUrl,
  formatCurrencyBRL,
  formatPlainCalendarDate,
  formatUtcInStudioTimezone,
  shiftPlainDateIso,
  studioLocalDateTimeToUtcIso,
  todayIsoInTimezone,
} from "@/lib/dates";
import type {
  AppointmentItem,
  AppointmentStatus,
  ClientRecord,
  PaymentMethodCode,
  PaymentMethodConfig,
  PiercingServiceItem,
  PublicAnamnesisLinkCreated,
  TeamMemberDirectory,
} from "@/lib/types";

const STATUS_OPTIONS: {
  value: AppointmentStatus;
  label: string;
  tone: "neutral" | "info" | "warning" | "success" | "danger";
}[] = [
  { value: "AGENDADO", label: "Agendado", tone: "info" },
  { value: "CONFIRMADO", label: "Confirmado", tone: "success" },
  { value: "EM_ATENDIMENTO", label: "Em Atendimento", tone: "warning" },
  { value: "CONCLUIDO", label: "Concluído", tone: "success" },
  { value: "CANCELADO", label: "Cancelado", tone: "neutral" },
  { value: "FALTOU", label: "Faltou", tone: "danger" },
];

export function AppointmentsPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const studioTz = currentStudio?.timezone || "America/Sao_Paulo";
  const isProfessional = currentStudio?.role === "PROFESSIONAL";
  const canManageAll =
    currentStudio?.role === "OWNER" || currentStudio?.role === "RECEPTION";

  const [viewMode, setViewMode] = React.useState<"day" | "week">("day");
  const [anchorDate, setAnchorDate] = React.useState(() =>
    todayIsoInTimezone(studioTz)
  );
  const [profFilter, setProfFilter] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");

  const dateTo =
    viewMode === "day" ? anchorDate : shiftPlainDateIso(anchorDate, 6);

  // Modais
  const [createOpen, setCreateOpen] = React.useState(false);
  const [depositTarget, setDepositTarget] =
    React.useState<AppointmentItem | null>(null);
  const [generatedLink, setGeneratedLink] =
    React.useState<PublicAnamnesisLinkCreated | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  // Form Novo Agendamento
  const [clientId, setClientId] = React.useState("");
  const [professionalId, setProfessionalId] = React.useState("");
  const [serviceId, setServiceId] = React.useState("");
  const [apptDate, setApptDate] = React.useState(anchorDate);
  const [startTime, setStartTime] = React.useState("14:00");
  const [notes, setNotes] = React.useState("");

  // Form Sinal
  const [depositAmount, setDepositAmount] = React.useState("50.00");
  const [depositMethod, setDepositMethod] =
    React.useState<PaymentMethodCode>("PIX");

  const appointmentsQuery = useQuery({
    queryKey: [
      "appointments",
      currentStudio?.studio_id,
      anchorDate,
      dateTo,
      profFilter,
      statusFilter,
    ],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("date_from", anchorDate);
      params.set("date_to", dateTo);
      if (!isProfessional && profFilter) {
        params.set("professional_id", profFilter);
      }
      if (statusFilter) params.set("status", statusFilter);
      return apiFetch<AppointmentItem[]>(`/appointments?${params.toString()}`);
    },
    enabled: Boolean(currentStudio),
  });

  const directoryQuery = useQuery({
    queryKey: ["team-directory", currentStudio?.studio_id],
    queryFn: () => apiFetch<TeamMemberDirectory[]>("/team/directory"),
    enabled: Boolean(currentStudio && canManageAll),
  });

  const clientsQuery = useQuery({
    queryKey: ["clients-list-select", currentStudio?.studio_id],
    queryFn: () => apiFetch<ClientRecord[]>("/clients?limit=300"),
    enabled: Boolean(currentStudio && createOpen),
  });

  const servicesQuery = useQuery({
    queryKey: ["piercing-services-select", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PiercingServiceItem[]>("/piercing/services?active_only=true"),
    enabled: Boolean(
      currentStudio &&
        createOpen &&
        currentStudio.enabled_modules.includes("piercing")
    ),
  });

  const paymentMethodsQuery = useQuery({
    queryKey: ["payment-methods", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<PaymentMethodConfig[]>("/studios/current/payment-methods"),
    enabled: Boolean(currentStudio && depositTarget),
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const startAtUtc = studioLocalDateTimeToUtcIso(
        apptDate,
        startTime,
        studioTz
      );
      return apiFetch<AppointmentItem>("/appointments", {
        method: "POST",
        body: JSON.stringify({
          client_id: clientId,
          professional_id: professionalId,
          module: "piercing",
          service_id: serviceId || null,
          start_at: startAtUtc,
          notes: notes.trim() || null,
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      setCreateOpen(false);
      setNotes("");
      setFormError(null);
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiError ? err.detail : "Erro ao criar agendamento."
      );
    },
  });

  const statusMutation = useMutation({
    mutationFn: (payload: { id: string; status: AppointmentStatus }) =>
      apiFetch<AppointmentItem>(`/appointments/${payload.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: payload.status }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
    },
    onError: (err) => {
      alert(err instanceof ApiError ? err.detail : "Erro ao atualizar status.");
    },
  });

  const depositMutation = useMutation({
    mutationFn: () => {
      if (!depositTarget) throw new Error("Agendamento inválido");
      return apiFetch<AppointmentItem>(
        `/appointments/${depositTarget.id}/deposit`,
        {
          method: "POST",
          body: JSON.stringify({
            amount: depositAmount,
            payment_method: depositMethod,
          }),
        }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      setDepositTarget(null);
      setFormError(null);
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiError ? err.detail : "Erro ao registrar sinal."
      );
    },
  });

  const generateLinkMutation = useMutation({
    mutationFn: (appt: AppointmentItem) =>
      apiFetch<PublicAnamnesisLinkCreated>("/anamnesis/public-links", {
        method: "POST",
        body: JSON.stringify({
          client_id: appt.client_id,
          appointment_id: appt.id,
          expires_in_hours: 48,
        }),
      }),
    onSuccess: (link) => {
      const fullUrl = `${window.location.origin}${link.public_path}`;
      navigator.clipboard?.writeText(fullUrl).catch(() => {});
      setGeneratedLink(link);
    },
    onError: (err) => {
      alert(err instanceof ApiError ? err.detail : "Erro ao gerar link.");
    },
  });

  const stepDays = viewMode === "day" ? 1 : 7;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Agenda Operacional
          </h1>
          <p className="text-sm text-muted-foreground">
            Horários exibidos no fuso do estúdio (<strong>{studioTz}</strong>).
          </p>
        </div>

        {canManageAll && (
          <Button
            onClick={() => {
              setApptDate(anchorDate);
              setFormError(null);
              setCreateOpen(true);
            }}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Novo Agendamento
          </Button>
        )}
      </div>

      {/* Controles de Período e Filtros */}
      <search aria-label="Navegação e filtros da agenda">
        <Card className="p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-md border border-border bg-secondary p-0.5">
                <button
                  type="button"
                  onClick={() => setViewMode("day")}
                  className={`rounded px-3 py-1.5 text-xs font-semibold ${
                    viewMode === "day"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground"
                  }`}
                >
                  Diária
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("week")}
                  className={`rounded px-3 py-1.5 text-xs font-semibold ${
                    viewMode === "week"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground"
                  }`}
                >
                  Semanal (7 dias)
                </button>
              </div>

              <div className="inline-flex items-center gap-1">
                <Button
                  size="sm"
                  variant="outline"
                  aria-label="Período anterior"
                  onClick={() =>
                    setAnchorDate((d) => shiftPlainDateIso(d, -stepDays))
                  }
                >
                  <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                </Button>
                <Input
                  type="date"
                  aria-label="Data base da agenda"
                  value={anchorDate}
                  onChange={(e) => setAnchorDate(e.target.value)}
                  className="min-h-[40px] w-40 py-1 text-sm"
                />
                <Button
                  size="sm"
                  variant="outline"
                  aria-label="Próximo período"
                  onClick={() =>
                    setAnchorDate((d) => shiftPlainDateIso(d, stepDays))
                  }
                >
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setAnchorDate(todayIsoInTimezone(studioTz))}
                >
                  Hoje
                </Button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {canManageAll && (
                <select
                  aria-label="Filtrar por profissional"
                  value={profFilter}
                  onChange={(e) => setProfFilter(e.target.value)}
                  className="min-h-[42px] rounded-md border border-input bg-card px-3 text-sm"
                >
                  <option value="">Todos os profissionais</option>
                  {directoryQuery.data?.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name} ({m.role})
                    </option>
                  ))}
                </select>
              )}

              <select
                aria-label="Filtrar por status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="min-h-[42px] rounded-md border border-input bg-card px-3 text-sm"
              >
                <option value="">Todos os status</option>
                {STATUS_OPTIONS.map((st) => (
                  <option key={st.value} value={st.value}>
                    {st.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <p className="mt-2.5 text-xs text-muted-foreground">
            Exibindo:{" "}
            <strong>
              {viewMode === "day"
                ? formatPlainCalendarDate(anchorDate)
                : `${formatPlainCalendarDate(anchorDate)} até ${formatPlainCalendarDate(dateTo)}`}
            </strong>
          </p>
        </Card>
      </search>

      {/* Lista de Agendamentos */}
      <div className="space-y-3">
        {appointmentsQuery.data?.length === 0 && (
          <Card className="p-8 text-center text-sm text-muted-foreground">
            <Calendar
              className="mx-auto mb-2 h-8 w-8 text-slate-400"
              aria-hidden="true"
            />
            Nenhum agendamento encontrado neste período.
          </Card>
        )}

        {appointmentsQuery.data?.map((appt) => {
          const startFmt = formatUtcInStudioTimezone(appt.start_at, studioTz);
          const endFmt = formatUtcInStudioTimezone(appt.end_at, studioTz);
          const statusMeta =
            STATUS_OPTIONS.find((s) => s.value === appt.status) ||
            STATUS_OPTIONS[0];

          return (
            <Card key={appt.id} className="p-4 sm:p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-slate-900 px-2.5 py-1 text-xs font-bold text-white">
                      {viewMode === "week" ? `${startFmt.dateLabel} • ` : ""}
                      {startFmt.timeLabel} – {endFmt.timeLabel}
                    </span>
                    <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
                    {appt.client_is_minor && (
                      <Badge tone="warning" className="gap-1">
                        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                        Menor (&lt; 18)
                      </Badge>
                    )}
                    {appt.deposit_status === "PAID" && (
                      <Badge tone="success">
                        Sinal Pago: {formatCurrencyBRL(appt.deposit_amount)} (
                        {appt.deposit_payment_method})
                      </Badge>
                    )}
                  </div>

                  <p className="text-base font-semibold text-slate-900">
                    {appt.client_name}
                    {appt.service_name ? (
                      <span className="font-normal text-muted-foreground">
                        {" "}
                        • {appt.service_name}
                      </span>
                    ) : null}
                  </p>

                  <p className="text-xs text-muted-foreground">
                    Profissional: <strong>{appt.professional_name}</strong>
                    {appt.notes ? ` • Obs.: ${appt.notes}` : ""}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <select
                    aria-label={`Status de ${appt.client_name}`}
                    value={appt.status}
                    onChange={(e) =>
                      statusMutation.mutate({
                        id: appt.id,
                        status: e.target.value as AppointmentStatus,
                      })
                    }
                    className="min-h-[40px] rounded-md border border-input bg-card px-2.5 text-xs font-medium"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>

                  {canManageAll && appt.deposit_status === "NONE" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setFormError(null);
                        setDepositAmount("50.00");
                        setDepositMethod("PIX");
                        setDepositTarget(appt);
                      }}
                    >
                      <DollarSign className="h-3.5 w-3.5" aria-hidden="true" />
                      Registrar Sinal
                    </Button>
                  )}

                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => generateLinkMutation.mutate(appt)}
                  >
                    <Link2 className="h-3.5 w-3.5" aria-hidden="true" />
                    Link Anamnese
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Modal Novo Agendamento */}
      <ModalDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Novo Agendamento"
        description="Conflitos de horário por profissional são verificados automaticamente."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
          className="space-y-4"
        >
          {formError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {formError}
            </div>
          )}

          <div>
            <Label htmlFor="appt-client">Cliente *</Label>
            <select
              id="appt-client"
              required
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="">Selecione um cliente...</option>
              {clientsQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name} {c.is_minor ? "(Menor <18)" : ""} — {c.whatsapp}
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="appt-prof">Profissional *</Label>
            <select
              id="appt-prof"
              required
              value={professionalId}
              onChange={(e) => setProfessionalId(e.target.value)}
              className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="">Selecione o profissional...</option>
              {directoryQuery.data?.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name} ({m.role})
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="appt-service">
              Serviço Principal (calcula duração automaticamente)
            </Label>
            <select
              id="appt-service"
              value={serviceId}
              onChange={(e) => setServiceId(e.target.value)}
              className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="">Atendimento avulso (30 min padrão)</option>
              {servicesQuery.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.duration_minutes} min —{" "}
                  {formatCurrencyBRL(s.base_price)})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="appt-date">Data *</Label>
              <Input
                id="appt-date"
                type="date"
                required
                value={apptDate}
                onChange={(e) => setApptDate(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="appt-time">Horário ({studioTz}) *</Label>
              <Input
                id="appt-time"
                type="time"
                required
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="appt-notes">Observações</Label>
            <Input
              id="appt-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Preferência de joia, avaliação de anatomia..."
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Agendando..." : "Confirmar horário"}
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Modal Registrar Sinal */}
      <ModalDialog
        open={Boolean(depositTarget)}
        onClose={() => setDepositTarget(null)}
        title={`Registrar Sinal — ${depositTarget?.client_name || ""}`}
        description="Este valor ficará vinculado ao agendamento para abatimento automático no fechamento da venda (PDV)."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            depositMutation.mutate();
          }}
          className="space-y-4"
        >
          {formError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {formError}
            </div>
          )}

          <div>
            <Label htmlFor="dep-amount">Valor do Sinal (R$) *</Label>
            <Input
              id="dep-amount"
              inputMode="decimal"
              required
              value={depositAmount}
              onChange={(e) => setDepositAmount(e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="dep-method">Meio de Pagamento *</Label>
            <select
              id="dep-method"
              value={depositMethod}
              onChange={(e) =>
                setDepositMethod(e.target.value as PaymentMethodCode)
              }
              className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              {(paymentMethodsQuery.data || [])
                .filter((m) => m.is_active)
                .map((m) => (
                  <option key={m.method} value={m.method}>
                    {m.label}
                  </option>
                ))}
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setDepositTarget(null)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={depositMutation.isPending}>
              {depositMutation.isPending
                ? "Registrando..."
                : "Confirmar recebimento"}
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Modal Link de Anamnese Gerado */}
      <ModalDialog
        open={Boolean(generatedLink)}
        onClose={() => setGeneratedLink(null)}
        title="Link Público de Anamnese Gerado"
        description="Link temporário de uso único copiado! Envie para o cliente assinar pelo celular."
      >
        {generatedLink && (
          <div className="space-y-4 text-sm">
            <Input
              readOnly
              value={`${window.location.origin}${generatedLink.public_path}`}
            />
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="outline"
                onClick={() =>
                  navigator.clipboard?.writeText(
                    `${window.location.origin}${generatedLink.public_path}`
                  )
                }
              >
                <Copy className="h-4 w-4" aria-hidden="true" />
                Copiar Link
              </Button>
              <a
                href={buildWhatsAppUrl(
                  generatedLink.client_whatsapp,
                  `Olá ${generatedLink.client_name.split(" ")[0]}! Para agilizar seu atendimento no ${currentStudio?.studio_name}, preencha e assine sua ficha de anamnese neste link seguro: ${window.location.origin}${generatedLink.public_path}`
                )}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-800"
              >
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                Enviar no WhatsApp
              </a>
            </div>
          </div>
        )}
      </ModalDialog>
    </div>
  );
}
