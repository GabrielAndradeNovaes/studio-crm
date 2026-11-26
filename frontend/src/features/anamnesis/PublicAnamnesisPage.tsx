import * as React from "react";
import { useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ShieldCheck, Sparkles } from "lucide-react";
import { Button, Card, Input, Label } from "@/components/ui/primitives";
import { SignaturePad } from "@/components/ui/SignaturePad";
import { ApiError, apiFetch } from "@/lib/api";
import type { AnamnesisFieldSchema, PublicAnamnesisFormView } from "@/lib/types";

export function DynamicAnamnesisFields({
  schema,
  answers,
  onChange,
}: {
  schema: AnamnesisFieldSchema[];
  answers: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}) {
  return (
    <div className="space-y-4">
      {schema.map((field) => {
        if (field.type === "boolean") {
          const currentVal = answers[field.key];
          return (
            <fieldset
              key={field.key}
              className="rounded-lg border border-border bg-slate-50/60 p-3.5"
            >
              <legend className="text-sm font-medium text-slate-900">
                {field.label} {field.required && "*"}
              </legend>
              <div className="mt-2 flex gap-3">
                {[
                  { label: "Sim", val: true },
                  { label: "Não", val: false },
                ].map((opt) => (
                  <label
                    key={String(opt.val)}
                    className="flex min-h-[44px] flex-1 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium"
                  >
                    <input
                      type="radio"
                      name={`field-${field.key}`}
                      required={field.required}
                      checked={currentVal === opt.val}
                      onChange={() =>
                        onChange({ ...answers, [field.key]: opt.val })
                      }
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          );
        }

        if (field.type === "boolean_with_details") {
          const obj = (answers[field.key] as {
            value?: boolean;
            details?: string;
          }) || { value: undefined, details: "" };

          return (
            <fieldset
              key={field.key}
              className="space-y-2.5 rounded-lg border border-border bg-slate-50/60 p-3.5"
            >
              <legend className="text-sm font-medium text-slate-900">
                {field.label} {field.required && "*"}
              </legend>
              <div className="flex gap-3">
                {[
                  { label: "Sim", val: true },
                  { label: "Não", val: false },
                ].map((opt) => (
                  <label
                    key={String(opt.val)}
                    className="flex min-h-[44px] flex-1 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium"
                  >
                    <input
                      type="radio"
                      name={`field-${field.key}`}
                      required={field.required}
                      checked={obj.value === opt.val}
                      onChange={() =>
                        onChange({
                          ...answers,
                          [field.key]: {
                            value: opt.val,
                            details: opt.val ? obj.details || "" : "",
                          },
                        })
                      }
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
              {obj.value === true && (
                <Input
                  required
                  value={obj.details || ""}
                  onChange={(e) =>
                    onChange({
                      ...answers,
                      [field.key]: { value: true, details: e.target.value },
                    })
                  }
                  placeholder={field.details_placeholder || "Especifique..."}
                />
              )}
            </fieldset>
          );
        }

        if (field.type === "textarea") {
          return (
            <div key={field.key}>
              <Label htmlFor={`f-${field.key}`}>
                {field.label} {field.required && "*"}
              </Label>
              <textarea
                id={`f-${field.key}`}
                required={field.required}
                rows={3}
                value={String(answers[field.key] ?? "")}
                onChange={(e) =>
                  onChange({ ...answers, [field.key]: e.target.value })
                }
                placeholder={field.placeholder || ""}
                className="w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-sm"
              />
            </div>
          );
        }

        return (
          <div key={field.key}>
            <Label htmlFor={`f-${field.key}`}>
              {field.label} {field.required && "*"}
            </Label>
            <Input
              id={`f-${field.key}`}
              required={field.required}
              value={String(answers[field.key] ?? "")}
              onChange={(e) =>
                onChange({ ...answers, [field.key]: e.target.value })
              }
              placeholder={field.placeholder || ""}
            />
          </div>
        );
      })}
    </div>
  );
}

export function PublicAnamnesisPage() {
  const { token } = useParams<{ token: string }>();

  const [loading, setLoading] = React.useState(true);
  const [formView, setFormView] = React.useState<PublicAnamnesisFormView | null>(
    null
  );
  const [loadError, setLoadError] = React.useState<string | null>(null);

  const [answers, setAnswers] = React.useState<Record<string, unknown>>({});
  const [guardianSignedName, setGuardianSignedName] = React.useState("");
  const [consentAccepted, setConsentAccepted] = React.useState(false);
  const [signaturePayload, setSignaturePayload] = React.useState("");
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [submittedAt, setSubmittedAt] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      if (!token) return;
      try {
        const data = await apiFetch<PublicAnamnesisFormView>(
          `/public/anamnesis/${token}`,
          { skipAuthRefresh: true }
        );
        if (active) setFormView(data);
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiError
              ? err.detail
              : "Não foi possível carregar este link de anamnese."
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [token]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token || !formView) return;
    if (!signaturePayload) {
      setSubmitError("Por favor, desenhe ou confirme sua assinatura antes de enviar.");
      return;
    }
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const res = await apiFetch<{
        record_id: string;
        consent_accepted_at: string;
        message: string;
      }>(`/public/anamnesis/${token}`, {
        method: "POST",
        body: JSON.stringify({
          answers,
          guardian_signed_name: guardianSignedName.trim() || null,
          consent_accepted: consentAccepted,
          signature_payload: signaturePayload,
        }),
        skipAuthRefresh: true,
      });
      setSubmittedAt(res.consent_accepted_at);
    } catch (err) {
      setSubmitError(
        err instanceof ApiError ? err.detail : "Falha ao registrar a ficha."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4 text-sm text-muted-foreground">
        Carregando ficha segura...
      </main>
    );
  }

  if (submittedAt) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <Card className="max-w-md p-6 text-center">
          <CheckCircle2
            className="mx-auto h-12 w-12 text-emerald-600"
            aria-hidden="true"
          />
          <h1 className="mt-3 text-xl font-bold text-slate-900">
            Ficha Assinada com Sucesso!
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Sua declaração de saúde e termo de consentimento foram registrados de forma segura e imutável em{" "}
            <strong>{formView?.studio_name}</strong>.
          </p>
        </Card>
      </main>
    );
  }

  if (loadError || !formView) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <Card className="max-w-md p-6 text-center">
          <AlertTriangle
            className="mx-auto h-11 w-11 text-amber-600"
            aria-hidden="true"
          />
          <h1 className="mt-3 text-lg font-bold text-slate-900">
            Link Indisponível
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {loadError || "Solicite um novo link à recepção do estúdio."}
          </p>
        </Card>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:py-10">
      <div className="mx-auto max-w-2xl space-y-5">
        <div className="text-center">
          <div className="mx-auto mb-2 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">
            {formView.studio_name}
          </h1>
          <p className="text-sm text-muted-foreground">
            Olá, <strong>{formView.client_first_name}</strong>! Preencha sua{" "}
            {formView.template_title} (v{formView.template_version}).
          </p>
        </div>

        <Card className="p-5 sm:p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {submitError && (
              <div
                role="alert"
                className="rounded-lg border border-red-200 bg-red-50 p-3.5 text-sm text-red-900"
              >
                {submitError}
              </div>
            )}

            {formView.is_minor && (
              <div className="space-y-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle
                    className="mt-0.5 h-5 w-5 shrink-0"
                    aria-hidden="true"
                  />
                  <div>
                    <p className="font-semibold">
                      Atendimento de Menor de 18 Anos
                    </p>
                    <p className="text-xs">
                      Esta ficha deve ser validada e assinada pelo responsável legal cadastrado.
                    </p>
                  </div>
                </div>
                <div>
                  <Label htmlFor="pub-guardian-name">
                    Nome completo do Responsável Legal que está assinando *
                  </Label>
                  <Input
                    id="pub-guardian-name"
                    name="guardian_signed_name"
                    autoComplete="name"
                    required
                    minLength={3}
                    value={guardianSignedName}
                    onChange={(e) => setGuardianSignedName(e.target.value)}
                  />
                </div>
              </div>
            )}

            <DynamicAnamnesisFields
              schema={formView.fields_schema}
              answers={answers}
              onChange={setAnswers}
            />

            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-900">
                Termo de Consentimento Livre e Esclarecido (LGPD)
              </h2>
              <div className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg border border-border bg-slate-50 p-3.5 text-xs leading-relaxed text-slate-700">
                {formView.consent_text}
              </div>

              <label className="flex min-h-[48px] cursor-pointer items-start gap-2.5 pt-2 text-sm font-medium text-slate-900">
                <input
                  type="checkbox"
                  required
                  checked={consentAccepted}
                  onChange={(e) => setConsentAccepted(e.target.checked)}
                  className="mt-1 h-4 w-4 accent-slate-900"
                />
                <span>
                  Li e concordo integralmente com o Termo de Consentimento e confirmo a veracidade das informações prestadas. *
                </span>
              </label>
            </div>

            <SignaturePad
              value={signaturePayload}
              onChange={setSignaturePayload}
              signerLabel={
                formView.is_minor
                  ? "Assinatura do Responsável Legal"
                  : "Sua Assinatura"
              }
            />

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              {isSubmitting
                ? "Registrando aceite seguro..."
                : "Confirmar e Assinar Ficha"}
            </Button>
          </form>
        </Card>
      </div>
    </main>
  );
}
