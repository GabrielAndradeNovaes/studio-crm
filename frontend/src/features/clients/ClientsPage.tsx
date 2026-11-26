import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Eye,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import {
  computeAgeAndMinorInTimezone,
  formatPlainCalendarDate,
  formatUtcInStudioTimezone,
} from "@/lib/dates";
import type {
  AnamnesisRecordSummary,
  AppointmentItem,
  ClientRecord,
  LeadSource,
  PiercingProcedureItem,
} from "@/lib/types";

const LEAD_SOURCES: { value: LeadSource; label: string }[] = [
  { value: "INSTAGRAM", label: "Instagram" },
  { value: "INDICACAO", label: "Indicação" },
  { value: "GOOGLE", label: "Google" },
  { value: "PASSANTE", label: "Passante / Fachada" },
  { value: "OUTRO", label: "Outro" },
];

function formatWhatsAppDisplay(digits: string): string {
  if (digits.length === 11) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }
  return digits;
}

export function ClientsPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const studioTz = currentStudio?.timezone || "America/Sao_Paulo";
  const canDelete =
    currentStudio?.role === "OWNER" || currentStudio?.role === "RECEPTION";

  // Filtros
  const [searchTerm, setSearchTerm] = React.useState("");
  const [sourceFilter, setSourceFilter] = React.useState<string>("");
  const [tagFilter, setTagFilter] = React.useState("");
  const [onlyMinors, setOnlyMinors] = React.useState(false);

  // Modais
  const [formOpen, setFormOpen] = React.useState(false);
  const [editingClient, setEditingClient] = React.useState<ClientRecord | null>(null);
  const [viewingClient, setViewingClient] = React.useState<ClientRecord | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  // Estado do formulário
  const [fullName, setFullName] = React.useState("");
  const [whatsapp, setWhatsapp] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [birthDate, setBirthDate] = React.useState("");
  const [cpf, setCpf] = React.useState("");
  const [leadSource, setLeadSource] = React.useState<LeadSource>("INSTAGRAM");
  const [tagsInput, setTagsInput] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [guardianName, setGuardianName] = React.useState("");
  const [guardianCpf, setGuardianCpf] = React.useState("");
  const [guardianWhatsapp, setGuardianWhatsapp] = React.useState("");
  const [guardianRelationship, setGuardianRelationship] = React.useState("");

  const liveMinorInfo = React.useMemo(
    () => computeAgeAndMinorInTimezone(birthDate, studioTz),
    [birthDate, studioTz]
  );
  const isMinorPreview = Boolean(liveMinorInfo?.isMinor);

  const clientsQuery = useQuery({
    queryKey: [
      "clients",
      currentStudio?.studio_id,
      searchTerm,
      sourceFilter,
      tagFilter,
      onlyMinors,
    ],
    queryFn: () => {
      const params = new URLSearchParams();
      if (searchTerm.trim()) params.set("q", searchTerm.trim());
      if (sourceFilter) params.set("lead_source", sourceFilter);
      if (tagFilter.trim()) params.set("tag", tagFilter.trim());
      if (onlyMinors) params.set("only_minors", "true");
      const qs = params.toString();
      return apiFetch<ClientRecord[]>(`/clients${qs ? `?${qs}` : ""}`);
    },
    enabled: Boolean(currentStudio),
  });

  const resetForm = () => {
    setFullName("");
    setWhatsapp("");
    setEmail("");
    setBirthDate("");
    setCpf("");
    setLeadSource("INSTAGRAM");
    setTagsInput("");
    setNotes("");
    setGuardianName("");
    setGuardianCpf("");
    setGuardianWhatsapp("");
    setGuardianRelationship("");
    setFormError(null);
    setEditingClient(null);
  };

  const openCreate = () => {
    resetForm();
    setFormOpen(true);
  };

  const openEdit = (c: ClientRecord) => {
    setEditingClient(c);
    setFullName(c.full_name);
    setWhatsapp(c.whatsapp);
    setEmail(c.email || "");
    setBirthDate(c.birth_date);
    setCpf(c.cpf || "");
    setLeadSource(c.lead_source);
    setTagsInput(c.tags.join(", "));
    setNotes(c.notes || "");
    setGuardianName(c.guardian_name || "");
    setGuardianCpf(c.guardian_cpf || "");
    setGuardianWhatsapp(c.guardian_whatsapp || "");
    setGuardianRelationship(c.guardian_relationship || "");
    setFormError(null);
    setFormOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const parsedTags = tagsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const body = {
        full_name: fullName.trim(),
        whatsapp: whatsapp.trim(),
        email: email.trim() || null,
        birth_date: birthDate,
        cpf: cpf.trim() || null,
        lead_source: leadSource,
        tags: parsedTags,
        notes: notes.trim() || null,
        guardian_name: guardianName.trim() || null,
        guardian_cpf: guardianCpf.trim() || null,
        guardian_whatsapp: guardianWhatsapp.trim() || null,
        guardian_relationship: guardianRelationship.trim() || null,
      };
      if (editingClient) {
        return apiFetch<ClientRecord>(`/clients/${editingClient.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      }
      return apiFetch<ClientRecord>("/clients", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setFormOpen(false);
      resetForm();
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiError ? err.detail : "Não foi possível salvar o cliente."
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (clientId: string) =>
      apiFetch<void>(`/clients/${clientId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setViewingClient(null);
    },
    onError: (err) => {
      alert(err instanceof ApiError ? err.detail : "Erro ao arquivar cliente.");
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">CRM de Clientes</h1>
          <p className="text-sm text-muted-foreground">
            Busca rápida por nome ou WhatsApp, tags e validação automática de menoridade (&lt; 18 anos).
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Novo Cliente
        </Button>
      </div>

      {/* Barra semântica <search> */}
      <search aria-label="Filtrar clientes">
        <Card className="p-4">
          <form
            onSubmit={(e) => e.preventDefault()}
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
          >
            <div className="relative">
              <Label htmlFor="client-search" className="sr-only">
                Buscar por nome ou WhatsApp
              </Label>
              <Search
                className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id="client-search"
                name="q"
                type="search"
                enterKeyHint="search"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Nome, WhatsApp ou e-mail..."
                className="pl-9"
              />
            </div>

            <div>
              <Label htmlFor="client-source-filter" className="sr-only">
                Origem do cliente
              </Label>
              <select
                id="client-source-filter"
                name="lead_source"
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-sm"
              >
                <option value="">Todas as origens</option>
                {LEAD_SOURCES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label htmlFor="client-tag-filter" className="sr-only">
                Filtrar por tag
              </Label>
              <Input
                id="client-tag-filter"
                name="tag"
                value={tagFilter}
                onChange={(e) => setTagFilter(e.target.value)}
                placeholder="Filtrar por tag (ex.: VIP, Orelha)"
              />
            </div>

            <label className="flex min-h-[48px] cursor-pointer items-center gap-2.5 rounded-md border border-border bg-slate-50 px-3.5 text-sm font-medium text-slate-800">
              <input
                type="checkbox"
                checked={onlyMinors}
                onChange={(e) => setOnlyMinors(e.target.checked)}
                className="h-4 w-4 accent-slate-900"
              />
              <span>Apenas menores (&lt; 18)</span>
            </label>
          </form>
        </Card>
      </search>

      <Card className="overflow-hidden">
        <div
          tabIndex={0}
          role="region"
          aria-labelledby="clients-table-caption"
          className="table-wrapper"
        >
          <table
            className="responsive-data-table text-sm"
            style={
              {
                "--label-2": '"WhatsApp"',
                "--label-3": '"Idade"',
                "--label-4": '"Origem / Tags"',
                "--label-5": '"Ações"',
              } as React.CSSProperties
            }
          >
            <caption id="clients-table-caption" className="sr-only">
              Lista de clientes cadastrados no estúdio
            </caption>
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-muted-foreground">
              <tr>
                <th className="px-5 py-3.5">Cliente</th>
                <th className="px-5 py-3.5">WhatsApp</th>
                <th className="px-5 py-3.5">Idade / Maioridade</th>
                <th className="px-5 py-3.5">Origem &amp; Tags</th>
                <th className="px-5 py-3.5 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {clientsQuery.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-muted-foreground">
                    Nenhum cliente encontrado para os filtros informados.
                  </td>
                </tr>
              )}
              {clientsQuery.data?.map((client) => (
                <tr key={client.id} className="hover:bg-slate-50/70">
                  <th scope="row" className="px-5 py-3.5 text-left font-medium">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-slate-900">
                        {client.full_name}
                      </span>
                      {client.is_minor && (
                        <Badge tone="warning" className="gap-1">
                          <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                          Menor de 18 anos
                        </Badge>
                      )}
                    </div>
                    {client.email && (
                      <div className="text-xs font-normal text-muted-foreground">
                        {client.email}
                      </div>
                    )}
                  </th>
                  <td className="px-5 py-3.5 font-medium text-slate-800">
                    {formatWhatsAppDisplay(client.whatsapp)}
                  </td>
                  <td className="px-5 py-3.5">
                    <span>
                      {client.age} anos ({formatPlainCalendarDate(client.birth_date)})
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex flex-wrap items-center gap-1">
                      <Badge tone="neutral">{client.lead_source}</Badge>
                      {client.tags.map((t) => (
                        <Badge key={t} tone="info">
                          {t}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <div className="inline-flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setViewingClient(client)}
                      >
                        <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                        Ficha
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openEdit(client)}
                      >
                        <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                        Editar
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal Criar / Editar Cliente */}
      <ModalDialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingClient ? "Editar Cliente" : "Novo Cliente"}
        description="Campos com * são obrigatórios. Menores de 18 anos exigem responsável legal."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveMutation.mutate();
          }}
          className="max-h-[75vh] space-y-4 overflow-y-auto pr-1"
        >
          {formError && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900"
            >
              {formError}
            </div>
          )}

          <div>
            <Label htmlFor="cli-name">Nome completo *</Label>
            <Input
              id="cli-name"
              name="full_name"
              autoComplete="name"
              required
              minLength={2}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="cli-whatsapp">WhatsApp *</Label>
              <Input
                id="cli-whatsapp"
                name="whatsapp"
                type="tel"
                autoComplete="tel"
                required
                value={whatsapp}
                onChange={(e) => setWhatsapp(e.target.value)}
                placeholder="(11) 99999-0000"
              />
            </div>
            <div>
              <Label htmlFor="cli-birth">Data de nascimento *</Label>
              <Input
                id="cli-birth"
                name="birth_date"
                type="date"
                required
                value={birthDate}
                onChange={(e) => setBirthDate(e.target.value)}
              />
            </div>
          </div>

          {liveMinorInfo && isMinorPreview && (
            <div
              role="status"
              className="flex items-start gap-2.5 rounded-lg border border-amber-300 bg-amber-50 p-3.5 text-sm text-amber-950"
            >
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-semibold">
                  Cliente menor de 18 anos ({liveMinorInfo.age} anos)
                </p>
                <p className="text-xs">
                  Pela política de segurança e LGPD, preencha obrigatoriamente os dados do responsável legal abaixo.
                </p>
              </div>
            </div>
          )}

          {isMinorPreview && (
            <fieldset className="space-y-3 rounded-lg border border-amber-300 bg-amber-50/40 p-4">
              <legend className="px-1 text-xs font-bold uppercase tracking-wide text-amber-900">
                Responsável Legal (Obrigatório)
              </legend>
              <div>
                <Label htmlFor="cli-guard-name">Nome do Responsável *</Label>
                <Input
                  id="cli-guard-name"
                  name="guardian_name"
                  required={isMinorPreview}
                  value={guardianName}
                  onChange={(e) => setGuardianName(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="cli-guard-cpf">CPF do Responsável *</Label>
                  <Input
                    id="cli-guard-cpf"
                    name="guardian_cpf"
                    inputMode="numeric"
                    required={isMinorPreview}
                    value={guardianCpf}
                    onChange={(e) => setGuardianCpf(e.target.value)}
                    placeholder="000.000.000-00"
                  />
                </div>
                <div>
                  <Label htmlFor="cli-guard-zap">WhatsApp do Responsável *</Label>
                  <Input
                    id="cli-guard-zap"
                    name="guardian_whatsapp"
                    type="tel"
                    required={isMinorPreview}
                    value={guardianWhatsapp}
                    onChange={(e) => setGuardianWhatsapp(e.target.value)}
                    placeholder="(11) 99999-0000"
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="cli-guard-rel">Grau de Parentesco</Label>
                <Input
                  id="cli-guard-rel"
                  name="guardian_relationship"
                  value={guardianRelationship}
                  onChange={(e) => setGuardianRelationship(e.target.value)}
                  placeholder="Ex.: Mãe, Pai, Tutor legal"
                />
              </div>
            </fieldset>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="cli-email">E-mail</Label>
              <Input
                id="cli-email"
                name="email"
                type="email"
                spellCheck={false}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cli-cpf">CPF do Cliente (opcional)</Label>
              <Input
                id="cli-cpf"
                name="cpf"
                inputMode="numeric"
                value={cpf}
                onChange={(e) => setCpf(e.target.value)}
                placeholder="000.000.000-00"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="cli-source">Origem do Lead</Label>
              <select
                id="cli-source"
                name="lead_source"
                value={leadSource}
                onChange={(e) => setLeadSource(e.target.value as LeadSource)}
                className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-sm"
              >
                {LEAD_SOURCES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="cli-tags">Tags (separadas por vírgula)</Label>
              <Input
                id="cli-tags"
                name="tags"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="VIP, Titânio, Auricular"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="cli-notes">Observações Clínicas / Preferências</Label>
            <textarea
              id="cli-notes"
              name="notes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-sm"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Salvando..." : "Salvar cliente"}
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Modal Detalhes do Cliente */}
      <ModalDialog
        open={Boolean(viewingClient)}
        onClose={() => setViewingClient(null)}
        title={viewingClient?.full_name || "Perfil do Cliente"}
      >
        {viewingClient && (
          <div className="max-h-[75vh] space-y-4 overflow-y-auto pr-1 text-sm">
            {viewingClient.is_minor && (
              <div className="flex items-start gap-2.5 rounded-lg border border-amber-300 bg-amber-50 p-3.5 text-amber-950">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
                <div>
                  <p className="font-semibold">
                    Atenção: Menor de 18 anos ({viewingClient.age} anos)
                  </p>
                  <p className="mt-0.5 text-xs">
                    Responsável: <strong>{viewingClient.guardian_name}</strong> • CPF:{" "}
                    {viewingClient.guardian_cpf} • WhatsApp:{" "}
                    {viewingClient.guardian_whatsapp
                      ? formatWhatsAppDisplay(viewingClient.guardian_whatsapp)
                      : "-"}
                    {viewingClient.guardian_relationship
                      ? ` (${viewingClient.guardian_relationship})`
                      : ""}
                  </p>
                </div>
              </div>
            )}

            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-semibold uppercase text-muted-foreground">
                  WhatsApp
                </dt>
                <dd className="font-medium text-slate-900">
                  {formatWhatsAppDisplay(viewingClient.whatsapp)}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase text-muted-foreground">
                  Nascimento
                </dt>
                <dd className="font-medium text-slate-900">
                  {formatPlainCalendarDate(viewingClient.birth_date)} ({viewingClient.age} anos)
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase text-muted-foreground">
                  E-mail
                </dt>
                <dd>{viewingClient.email || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase text-muted-foreground">
                  CPF
                </dt>
                <dd>{viewingClient.cpf || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase text-muted-foreground">
                  Origem
                </dt>
                <dd>{viewingClient.lead_source}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase text-muted-foreground">
                  Tags
                </dt>
                <dd className="flex flex-wrap gap-1 pt-0.5">
                  {viewingClient.tags.length > 0
                    ? viewingClient.tags.map((t) => (
                        <Badge key={t} tone="info">
                          {t}
                        </Badge>
                      ))
                    : "—"}
                </dd>
              </div>
            </dl>

            {viewingClient.notes && (
              <div className="rounded-md bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase text-muted-foreground">
                  Observações
                </p>
                <p className="mt-1 whitespace-pre-wrap text-slate-800">
                  {viewingClient.notes}
                </p>
              </div>
            )}

            <ClientClinicalHistory
              clientId={viewingClient.id}
              studioTz={studioTz}
              hasPiercing={Boolean(
                currentStudio?.enabled_modules?.includes("piercing")
              )}
            />

            <div className="flex items-center justify-between border-t border-border pt-4">
              {canDelete ? (
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(viewingClient.id)}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  Arquivar cliente
                </Button>
              ) : (
                <span />
              )}
              <Button variant="outline" onClick={() => setViewingClient(null)}>
                Fechar
              </Button>
            </div>
          </div>
        )}
      </ModalDialog>
    </div>
  );
}

function ClientClinicalHistory({
  clientId,
  studioTz,
  hasPiercing,
}: {
  clientId: string;
  studioTz: string;
  hasPiercing: boolean;
}) {
  const appointmentsQuery = useQuery({
    queryKey: ["client-history-appts", clientId],
    queryFn: () =>
      apiFetch<AppointmentItem[]>(`/appointments?client_id=${clientId}`),
  });

  const anamnesesQuery = useQuery({
    queryKey: ["client-history-anamneses", clientId],
    queryFn: () =>
      apiFetch<AnamnesisRecordSummary[]>(
        `/anamnesis/records?client_id=${clientId}`
      ),
  });

  const proceduresQuery = useQuery({
    queryKey: ["client-history-procedures", clientId],
    queryFn: () =>
      apiFetch<PiercingProcedureItem[]>(
        `/piercing/procedures?client_id=${clientId}`
      ),
    enabled: hasPiercing,
  });

  return (
    <div className="space-y-3 border-t border-border pt-3 text-xs">
      <div>
        <h3 className="font-bold uppercase tracking-wider text-muted-foreground">
          Agendamentos ({appointmentsQuery.data?.length ?? 0})
        </h3>
        <div className="mt-1.5 space-y-1.5">
          {appointmentsQuery.data?.slice(0, 5).map((a) => {
            const fmt = formatUtcInStudioTimezone(a.start_at, studioTz);
            return (
              <div
                key={a.id}
                className="flex items-center justify-between rounded border border-border bg-slate-50 px-2.5 py-1.5"
              >
                <span>
                  {fmt.dateLabel} às {fmt.timeLabel} • {a.service_name || a.module}
                </span>
                <Badge tone="neutral">{a.status}</Badge>
              </div>
            );
          })}
          {appointmentsQuery.data?.length === 0 && (
            <p className="text-muted-foreground">Nenhum agendamento registrado.</p>
          )}
        </div>
      </div>

      <div>
        <h3 className="font-bold uppercase tracking-wider text-muted-foreground">
          Anamneses Assinadas ({anamnesesQuery.data?.length ?? 0})
        </h3>
        <div className="mt-1.5 space-y-1.5">
          {anamnesesQuery.data?.slice(0, 5).map((rec) => (
            <div
              key={rec.id}
              className="flex items-center justify-between rounded border border-border bg-slate-50 px-2.5 py-1.5"
            >
              <span>
                {rec.module} v{rec.template_version} •{" "}
                {rec.consent_accepted_at
                  ? new Date(rec.consent_accepted_at).toLocaleDateString("pt-BR")
                  : "—"}
              </span>
              <Badge tone="success">Assinada</Badge>
            </div>
          ))}
          {anamnesesQuery.data?.length === 0 && (
            <p className="text-muted-foreground">Nenhuma ficha assinada.</p>
          )}
        </div>
      </div>

      {hasPiercing && (
        <div>
          <h3 className="font-bold uppercase tracking-wider text-muted-foreground">
            Procedimentos &amp; Downsize ({proceduresQuery.data?.length ?? 0})
          </h3>
          <div className="mt-1.5 space-y-1.5">
            {proceduresQuery.data?.slice(0, 5).map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between rounded border border-border bg-slate-50 px-2.5 py-1.5"
              >
                <div>
                  <span className="font-medium text-slate-900">
                    {p.anatomical_site_detail}
                  </span>
                  {p.jewelry_name ? ` • ${p.jewelry_name}` : ""}
                </div>
                <Badge
                  tone={
                    p.downsize_completed_at
                      ? "success"
                      : p.is_overdue
                      ? "danger"
                      : "info"
                  }
                >
                  {p.downsize_completed_at
                    ? "Downsize OK"
                    : p.downsize_reminder_date
                    ? `Downsize: ${formatPlainCalendarDate(p.downsize_reminder_date)}`
                    : "Registrado"}
                </Badge>
              </div>
            ))}
            {proceduresQuery.data?.length === 0 && (
              <p className="text-muted-foreground">
                Nenhum procedimento registrado.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
