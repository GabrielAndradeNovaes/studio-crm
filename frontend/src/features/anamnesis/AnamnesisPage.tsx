import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Copy,
  ExternalLink,
  Eye,
  FileSignature,
  Link2,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { SignaturePad } from "@/components/ui/SignaturePad";
import { useAuth } from "@/features/auth/AuthContext";
import { DynamicAnamnesisFields } from "./PublicAnamnesisPage";
import { ApiError, apiFetch } from "@/lib/api";
import { buildWhatsAppUrl } from "@/lib/dates";
import type {
  AnamnesisRecordDetail,
  AnamnesisRecordSummary,
  AnamnesisTemplateItem,
  ClientRecord,
  PublicAnamnesisLinkCreated,
} from "@/lib/types";

export function AnamnesisPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const isOwner = currentStudio?.role === "OWNER";

  const [fillModalOpen, setFillModalOpen] = React.useState(false);
  const [linkModalOpen, setLinkModalOpen] = React.useState(false);
  const [templateModalOpen, setTemplateModalOpen] = React.useState(false);
  const [viewingRecordId, setViewingRecordId] = React.useState<string | null>(
    null
  );

  // Estado Preenchimento Interno
  const [selectedClientId, setSelectedClientId] = React.useState("");
  const [answers, setAnswers] = React.useState<Record<string, unknown>>({});
  const [guardianSignedName, setGuardianSignedName] = React.useState("");
  const [consentAccepted, setConsentAccepted] = React.useState(false);
  const [signaturePayload, setSignaturePayload] = React.useState("");
  const [formError, setFormError] = React.useState<string | null>(null);

  // Estado Link Público
  const [linkClientId, setLinkClientId] = React.useState("");
  const [createdLink, setCreatedLink] =
    React.useState<PublicAnamnesisLinkCreated | null>(null);

  // Estado Edição de Template (OWNER)
  const [tplTitle, setTplTitle] = React.useState("");
  const [tplConsentText, setTplConsentText] = React.useState("");

  const templatesQuery = useQuery({
    queryKey: ["anamnesis-templates", currentStudio?.studio_id],
    queryFn: () =>
      apiFetch<AnamnesisTemplateItem[]>("/anamnesis/templates?module=piercing"),
    enabled: Boolean(currentStudio),
  });

  const activeTemplate = React.useMemo(
    () => templatesQuery.data?.find((t) => t.is_active) || templatesQuery.data?.[0],
    [templatesQuery.data]
  );

  const recordsQuery = useQuery({
    queryKey: ["anamnesis-records", currentStudio?.studio_id],
    queryFn: () => apiFetch<AnamnesisRecordSummary[]>("/anamnesis/records"),
    enabled: Boolean(currentStudio),
  });

  const recordDetailQuery = useQuery({
    queryKey: ["anamnesis-record-detail", viewingRecordId],
    queryFn: () =>
      apiFetch<AnamnesisRecordDetail>(`/anamnesis/records/${viewingRecordId}`),
    enabled: Boolean(viewingRecordId),
  });

  const clientsQuery = useQuery({
    queryKey: ["clients-for-anamnesis", currentStudio?.studio_id],
    queryFn: () => apiFetch<ClientRecord[]>("/clients?limit=300"),
    enabled: Boolean(currentStudio && (fillModalOpen || linkModalOpen)),
  });

  const selectedClient = React.useMemo(
    () => clientsQuery.data?.find((c) => c.id === selectedClientId) || null,
    [clientsQuery.data, selectedClientId]
  );

  const createRecordMutation = useMutation({
    mutationFn: () => {
      if (!signaturePayload) {
        throw new ApiError(
          422,
          "SIGNATURE_REQUIRED",
          "Desenhe ou confirme a assinatura antes de salvar."
        );
      }
      return apiFetch<AnamnesisRecordDetail>("/anamnesis/records", {
        method: "POST",
        body: JSON.stringify({
          client_id: selectedClientId,
          template_id: activeTemplate?.id,
          module: "piercing",
          answers,
          guardian_signed_name: guardianSignedName.trim() || null,
          consent_accepted: consentAccepted,
          signature_payload: signaturePayload,
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["anamnesis-records"] });
      setFillModalOpen(false);
      setAnswers({});
      setGuardianSignedName("");
      setConsentAccepted(false);
      setSignaturePayload("");
      setFormError(null);
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiError ? err.detail : "Erro ao registrar anamnese."
      );
    },
  });

  const createLinkMutation = useMutation({
    mutationFn: () =>
      apiFetch<PublicAnamnesisLinkCreated>("/anamnesis/public-links", {
        method: "POST",
        body: JSON.stringify({
          client_id: linkClientId,
          module: "piercing",
          expires_in_hours: 48,
        }),
      }),
    onSuccess: (res) => {
      const fullUrl = `${window.location.origin}${res.public_path}`;
      navigator.clipboard?.writeText(fullUrl).catch(() => {});
      setCreatedLink(res);
      setFormError(null);
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiError ? err.detail : "Erro ao gerar link público."
      );
    },
  });

  const updateTemplateMutation = useMutation({
    mutationFn: () => {
      if (!activeTemplate) throw new Error("Modelo ausente");
      return apiFetch<AnamnesisTemplateItem>(
        `/anamnesis/templates/${activeTemplate.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            module: "piercing",
            title: tplTitle.trim(),
            fields_schema: activeTemplate.fields_schema,
            consent_text: tplConsentText.trim(),
          }),
        }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["anamnesis-templates"] });
      setTemplateModalOpen(false);
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Anamnese &amp; Termos (LGPD)
          </h1>
          <p className="text-sm text-muted-foreground">
            Fichas clínicas imutáveis pós-assinatura, trilha de auditoria e autoatendimento via link único.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {isOwner && activeTemplate && (
            <Button
              variant="outline"
              onClick={() => {
                setTplTitle(activeTemplate.title);
                setTplConsentText(activeTemplate.consent_text);
                setTemplateModalOpen(true);
              }}
            >
              <Settings2 className="h-4 w-4" aria-hidden="true" />
              Modelo Ativo (v{activeTemplate.version})
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() => {
              setCreatedLink(null);
              setFormError(null);
              setLinkModalOpen(true);
            }}
          >
            <Link2 className="h-4 w-4" aria-hidden="true" />
            Gerar Link p/ Celular
          </Button>
          <Button
            onClick={() => {
              setAnswers({});
              setSignaturePayload("");
              setConsentAccepted(false);
              setFormError(null);
              setFillModalOpen(true);
            }}
          >
            <FileSignature className="h-4 w-4" aria-hidden="true" />
            Preencher no Tablet
          </Button>
        </div>
      </div>

      <Card className="overflow-hidden">
        <div
          tabIndex={0}
          role="region"
          aria-labelledby="anamnesis-table-caption"
          className="table-wrapper"
        >
          <table
            className="responsive-data-table text-sm"
            style={
              {
                "--label-2": '"Versão"',
                "--label-3": '"Origem / Responsável"',
                "--label-4": '"Data Aceite"',
                "--label-5": '"Ação"',
              } as React.CSSProperties
            }
          >
            <caption id="anamnesis-table-caption" className="sr-only">
              Fichas de anamnese assinadas no estúdio
            </caption>
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-muted-foreground">
              <tr>
                <th className="px-5 py-3.5">Cliente</th>
                <th className="px-5 py-3.5">Módulo / Versão</th>
                <th className="px-5 py-3.5">Origem &amp; Responsável</th>
                <th className="px-5 py-3.5">Aceite Imutável</th>
                <th className="px-5 py-3.5 text-right">Auditoria</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {recordsQuery.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-muted-foreground">
                    Nenhuma ficha de anamnese registrada até o momento.
                  </td>
                </tr>
              )}

              {recordsQuery.data?.map((rec) => (
                <tr key={rec.id} className="hover:bg-slate-50/70">
                  <th scope="row" className="px-5 py-3.5 text-left font-semibold text-slate-900">
                    {rec.client_name}
                  </th>
                  <td className="px-5 py-3.5">
                    <Badge tone="info">
                      {rec.module} v{rec.template_version}
                    </Badge>
                  </td>
                  <td className="px-5 py-3.5 text-xs">
                    <div>
                      {rec.created_by ? "Balcão / Equipe" : "Link Público (Cliente)"}
                    </div>
                    {rec.guardian_signed_name && (
                      <div className="font-medium text-amber-800">
                        Resp.: {rec.guardian_signed_name}
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-slate-700">
                    {rec.consent_accepted_at
                      ? new Date(rec.consent_accepted_at).toLocaleString("pt-BR")
                      : "—"}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setViewingRecordId(rec.id)}
                    >
                      <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                      Ver Ficha (LGPD)
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal Preencher no Balcão / Tablet */}
      <ModalDialog
        open={fillModalOpen}
        onClose={() => setFillModalOpen(false)}
        title="Preencher Ficha de Anamnese"
        description="Após assinar e confirmar, esta ficha torna-se estritamente imutável."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createRecordMutation.mutate();
          }}
          className="max-h-[75vh] space-y-4 overflow-y-auto pr-1"
        >
          {formError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {formError}
            </div>
          )}

          <div>
            <Label htmlFor="anam-client">Cliente *</Label>
            <select
              id="anam-client"
              required
              value={selectedClientId}
              onChange={(e) => {
                const id = e.target.value;
                setSelectedClientId(id);
                const cli = clientsQuery.data?.find((c) => c.id === id);
                setGuardianSignedName(cli?.guardian_name || "");
              }}
              className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value="">Selecione o cliente...</option>
              {clientsQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name} {c.is_minor ? "(Menor <18)" : ""}
                </option>
              ))}
            </select>
          </div>

          {selectedClient?.is_minor && (
            <div className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3.5 text-sm text-amber-950">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                Cliente menor de 18 anos ({selectedClient.age} anos)
              </div>
              <div>
                <Label htmlFor="int-guardian-sig">
                  Nome do Responsável Legal presente *
                </Label>
                <Input
                  id="int-guardian-sig"
                  required
                  value={guardianSignedName}
                  onChange={(e) => setGuardianSignedName(e.target.value)}
                />
              </div>
            </div>
          )}

          {activeTemplate && (
            <>
              <DynamicAnamnesisFields
                schema={activeTemplate.fields_schema}
                answers={answers}
                onChange={setAnswers}
              />

              <div className="max-h-36 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-slate-50 p-3 text-xs text-slate-700">
                {activeTemplate.consent_text}
              </div>
            </>
          )}

          <label className="flex items-start gap-2.5 text-sm font-medium">
            <input
              type="checkbox"
              required
              checked={consentAccepted}
              onChange={(e) => setConsentAccepted(e.target.checked)}
              className="mt-1 h-4 w-4 accent-slate-900"
            />
            <span>
              Declaro que li e concordo com o Termo de Consentimento acima. *
            </span>
          </label>

          <SignaturePad
            value={signaturePayload}
            onChange={setSignaturePayload}
            signerLabel={
              selectedClient?.is_minor
                ? "Assinatura do Responsável Legal"
                : "Assinatura do Cliente"
            }
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setFillModalOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={createRecordMutation.isPending}>
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              {createRecordMutation.isPending
                ? "Salvando aceite..."
                : "Assinar e Registrar"}
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Modal Gerar e Copiar Link Público */}
      <ModalDialog
        open={linkModalOpen}
        onClose={() => setLinkModalOpen(false)}
        title="Gerar e Copiar Link de Anamnese"
        description="Gera um link seguro de uso único (válido por 48h) para o cliente assinar no próprio celular."
      >
        {!createdLink ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createLinkMutation.mutate();
            }}
            className="space-y-4"
          >
            {formError && (
              <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
                {formError}
              </div>
            )}
            <div>
              <Label htmlFor="link-client">Selecione o Cliente *</Label>
              <select
                id="link-client"
                required
                value={linkClientId}
                onChange={(e) => setLinkClientId(e.target.value)}
                className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm"
              >
                <option value="">Escolha um cliente...</option>
                {clientsQuery.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.full_name} — {c.whatsapp}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setLinkModalOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={createLinkMutation.isPending}>
                Gerar e Copiar Link
              </Button>
            </div>
          </form>
        ) : (
          <div className="space-y-4 text-sm">
            <p className="font-medium text-emerald-800">
              Link gerado e copiado para a área de transferência!
            </p>
            <Input
              readOnly
              value={`${window.location.origin}${createdLink.public_path}`}
            />
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="outline"
                onClick={() =>
                  navigator.clipboard?.writeText(
                    `${window.location.origin}${createdLink.public_path}`
                  )
                }
              >
                <Copy className="h-4 w-4" aria-hidden="true" />
                Copiar novamente
              </Button>
              <a
                href={buildWhatsAppUrl(
                  createdLink.client_whatsapp,
                  `Olá ${createdLink.client_name.split(" ")[0]}! Preencha e assine sua ficha de anamnese antes do atendimento neste link seguro: ${window.location.origin}${createdLink.public_path}`
                )}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-800"
              >
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                Abrir no WhatsApp
              </a>
            </div>
          </div>
        )}
      </ModalDialog>

      {/* Modal Visualização Auditada (READ_SENSITIVE) */}
      <ModalDialog
        open={Boolean(viewingRecordId)}
        onClose={() => setViewingRecordId(null)}
        title="Ficha de Anamnese Assinada (Acesso Auditado LGPD)"
      >
        {recordDetailQuery.data ? (
          <div className="max-h-[75vh] space-y-4 overflow-y-auto pr-1 text-sm">
            <div className="rounded-lg border border-border bg-slate-50 p-3 text-xs">
              <p>
                <strong>Cliente:</strong> {recordDetailQuery.data.client_name} •{" "}
                <strong>Versão:</strong> v{recordDetailQuery.data.template_version}
              </p>
              {recordDetailQuery.data.guardian_signed_name && (
                <p className="text-amber-900">
                  <strong>Responsável Signatário:</strong>{" "}
                  {recordDetailQuery.data.guardian_signed_name}
                </p>
              )}
              <p className="text-muted-foreground">
                Aceite UTC:{" "}
                {recordDetailQuery.data.consent_accepted_at
                  ? new Date(
                      recordDetailQuery.data.consent_accepted_at
                    ).toLocaleString("pt-BR")
                  : "—"}{" "}
                • IP: {recordDetailQuery.data.consent_ip || "—"}
              </p>
            </div>

            <div className="space-y-2">
              {recordDetailQuery.data.fields_schema.map((f) => {
                const rawVal = recordDetailQuery.data.answers[f.key];
                let formatted = "—";
                if (typeof rawVal === "boolean") {
                  formatted = rawVal ? "Sim" : "Não";
                } else if (
                  rawVal &&
                  typeof rawVal === "object" &&
                  "value" in rawVal
                ) {
                  const obj = rawVal as { value?: boolean; details?: string };
                  formatted = obj.value
                    ? `Sim (${obj.details || "sem detalhes"})`
                    : "Não";
                } else if (rawVal) {
                  formatted = String(rawVal);
                }
                return (
                  <div
                    key={f.key}
                    className="rounded-md border border-border p-2.5 text-xs"
                  >
                    <p className="font-medium text-slate-700">{f.label}</p>
                    <p className="mt-0.5 font-semibold text-slate-900">
                      {formatted}
                    </p>
                  </div>
                );
              })}
            </div>

            {recordDetailQuery.data.signature_payload && (
              <div className="rounded-lg border border-border p-3">
                <p className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground">
                  Registro de Assinatura Imutável
                </p>
                {recordDetailQuery.data.signature_payload.startsWith(
                  "data:image/"
                ) ? (
                  <img
                    src={recordDetailQuery.data.signature_payload}
                    alt="Assinatura digitalizada do signatário"
                    className="max-h-28 rounded border border-slate-200 bg-white"
                  />
                ) : (
                  <p className="font-mono text-xs text-slate-900">
                    {recordDetailQuery.data.signature_payload}
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Carregando dados auditados...</p>
        )}
      </ModalDialog>

      {/* Modal Editar Modelo Versionado (OWNER) */}
      <ModalDialog
        open={templateModalOpen}
        onClose={() => setTemplateModalOpen(false)}
        title="Atualizar Termo / Modelo de Anamnese"
        description="Se já existirem fichas assinadas nesta versão, uma nova versão será gerada automaticamente sem alterar o histórico."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            updateTemplateMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="tpl-title">Título do Formulário *</Label>
            <Input
              id="tpl-title"
              required
              value={tplTitle}
              onChange={(e) => setTplTitle(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="tpl-consent">Texto do Termo de Consentimento *</Label>
            <textarea
              id="tpl-consent"
              rows={7}
              required
              value={tplConsentText}
              onChange={(e) => setTplConsentText(e.target.value)}
              className="w-full rounded-md border border-input bg-card p-3 text-xs leading-relaxed"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setTemplateModalOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={updateTemplateMutation.isPending}>
              Salvar modelo versionado
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}
