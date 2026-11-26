import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Sparkles } from "lucide-react";
import { Button, Card, Input, Label } from "@/components/ui/primitives";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "./AuthContext";

const BRAZIL_TIMEZONES = [
  { value: "America/Sao_Paulo", label: "Brasília / São Paulo (UTC-3)" },
  { value: "America/Manaus", label: "Amazonas / Manaus (UTC-4)" },
  { value: "America/Cuiaba", label: "Mato Grosso / Cuiabá (UTC-4)" },
  { value: "America/Fortaleza", label: "Nordeste / Fortaleza (UTC-3)" },
  { value: "America/Rio_Branco", label: "Acre / Rio Branco (UTC-5)" },
];

export function OnboardingPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [studioName, setStudioName] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [document, setDocument] = React.useState("");
  const [timezone, setTimezone] = React.useState("America/Sao_Paulo");
  const [ownerName, setOwnerName] = React.useState("");
  const [ownerEmail, setOwnerEmail] = React.useState("");
  const [ownerPassword, setOwnerPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);

  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsSubmitting(true);

    try {
      await apiFetch("/studios/onboarding", {
        method: "POST",
        body: JSON.stringify({
          studio_name: studioName.trim(),
          phone: phone.trim() || null,
          document: document.trim() || null,
          timezone,
          owner_name: ownerName.trim(),
          owner_email: ownerEmail.trim(),
          owner_password: ownerPassword,
        }),
        skipAuthRefresh: true,
      });

      const session = await login(ownerEmail.trim(), ownerPassword);
      navigate(session.requires_studio_selection ? "/login" : "/", { replace: true });
    } catch (err) {
      setErrorMsg(
        err instanceof ApiError
          ? err.detail
          : "Não foi possível concluir o cadastro do estúdio."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 sm:py-12">
      <div className="mx-auto w-full max-w-lg">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-white">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">
            Cadastrar Novo Estúdio
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Comece com o Módulo de Piercing ativo e taxas padrão configuradas.
          </p>
        </div>

        <Card className="p-6">
          {errorMsg && (
            <div
              role="alert"
              className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3.5 text-sm text-red-900"
            >
              {errorMsg}
            </div>
          )}

          <form method="post" action="/onboarding" onSubmit={handleSubmit} className="space-y-4">
            <fieldset className="space-y-3 border-b border-border pb-4">
              <legend className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                1. Dados do Estúdio
              </legend>
              <div>
                <Label htmlFor="studio-name">Nome do Estúdio *</Label>
                <Input
                  id="studio-name"
                  name="organization"
                  autoComplete="organization"
                  required
                  minLength={2}
                  value={studioName}
                  onChange={(e) => setStudioName(e.target.value)}
                  placeholder="Ex.: Aurora Body Piercing"
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="studio-phone">WhatsApp Comercial</Label>
                  <Input
                    id="studio-phone"
                    name="phone"
                    type="tel"
                    autoComplete="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="(11) 99999-0000"
                  />
                </div>
                <div>
                  <Label htmlFor="studio-doc">CNPJ ou CPF (opcional)</Label>
                  <Input
                    id="studio-doc"
                    name="document"
                    value={document}
                    onChange={(e) => setDocument(e.target.value)}
                    placeholder="00.000.000/0001-00"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="studio-tz">Fuso Horário do Caixa</Label>
                <select
                  id="studio-tz"
                  name="timezone"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-foreground"
                >
                  {BRAZIL_TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value}>
                      {tz.label}
                    </option>
                  ))}
                </select>
              </div>
            </fieldset>

            <fieldset className="space-y-3">
              <legend className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                2. Proprietário (OWNER)
              </legend>

              <div>
                <Label htmlFor="owner-name">Nome completo *</Label>
                <Input
                  id="owner-name"
                  name="name"
                  autoComplete="name"
                  required
                  minLength={2}
                  value={ownerName}
                  onChange={(e) => setOwnerName(e.target.value)}
                  placeholder="Seu nome completo"
                />
              </div>

              <div>
                <Label htmlFor="owner-email">E-mail de acesso *</Label>
                <Input
                  id="owner-email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  spellCheck={false}
                  required
                  value={ownerEmail}
                  onChange={(e) => setOwnerEmail(e.target.value)}
                  placeholder="contato@estudio.com.br"
                />
              </div>

              <div>
                <Label htmlFor="owner-password">Senha (mínimo 8 caracteres) *</Label>
                <div className="relative">
                  <Input
                    id="owner-password"
                    name="new-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    aria-describedby="pwd-hint"
                    minLength={8}
                    required
                    value={ownerPassword}
                    onChange={(e) => setOwnerPassword(e.target.value)}
                    className="pr-12"
                  />
                  <button
                    type="button"
                    aria-pressed={showPassword}
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute inset-y-0 right-1 my-auto inline-flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
                <p id="pwd-hint" className="mt-1 text-xs text-muted-foreground">
                  Se você já possui conta em outro estúdio, informe sua senha atual para vincular esta filial.
                </p>
              </div>
            </fieldset>

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Criando estúdio..." : "Criar estúdio e iniciar avaliação"}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              Já possui acesso?{" "}
              <Link
                to="/login"
                className="font-semibold text-slate-900 underline-offset-2 hover:underline"
              >
                Voltar para o login
              </Link>
            </p>
          </form>
        </Card>
      </div>
    </main>
  );
}
