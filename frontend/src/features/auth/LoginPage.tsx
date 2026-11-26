import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Building2, Eye, EyeOff, Lock, ShieldAlert, Sparkles } from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAuth } from "./AuthContext";
import { ApiError, apiFetch } from "@/lib/api";

export function LoginPage() {
  const {
    login,
    selectStudio,
    requiresStudioSelection,
    availableStudios,
    cancelStudioSelection,
    user,
  } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);
  const [errorCode, setErrorCode] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const [forgotOpen, setForgotOpen] = React.useState(false);
  const [forgotEmail, setForgotEmail] = React.useState("");
  const [forgotFeedback, setForgotFeedback] = React.useState<string | null>(null);
  const [isSendingForgot, setIsSendingForgot] = React.useState(false);

  const handleSignIn = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMsg(null);
    setErrorCode(null);
    setIsSubmitting(true);

    try {
      const session = await login(email.trim(), password);
      if (!session.requires_studio_selection) {
        navigate(
          session.user.is_superadmin && !session.current_studio ? "/admin" : "/",
          { replace: true }
        );
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorCode(err.code);
        setErrorMsg(err.detail);
      } else {
        setErrorMsg("Não foi possível realizar login no momento.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectStudio = async (studioId: string) => {
    setErrorMsg(null);
    setErrorCode(null);
    setIsSubmitting(true);
    try {
      await selectStudio(studioId);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorCode(err.code);
        setErrorMsg(err.detail);
      } else {
        setErrorMsg("Falha ao selecionar o estúdio.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleForgotSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSendingForgot(true);
    setForgotFeedback(null);
    try {
      const res = await apiFetch<{ message: string }>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: forgotEmail.trim() }),
        skipAuthRefresh: true,
      });
      setForgotFeedback(res.message);
    } catch (err) {
      setForgotFeedback(
        err instanceof ApiError
          ? err.detail
          : "Não foi possível enviar a solicitação."
      );
    } finally {
      setIsSendingForgot(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 sm:py-14">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-slate-900 text-white shadow-sm">
            <Sparkles className="h-6 w-6" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Studio Flow SaaS
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            CRM, Agenda, Estoque e Financeiro para Estúdios de Piercing &amp; Tatuagem
          </p>
        </div>

        <Card className="p-6">
          {errorMsg && (
            <div
              role="alert"
              aria-live="polite"
              className={`mb-5 flex items-start gap-3 rounded-lg border p-3.5 text-sm ${
                errorCode === "STUDIO_SUSPENDED" || errorCode === "STUDIO_INACTIVE"
                  ? "border-amber-300 bg-amber-50 text-amber-950"
                  : "border-red-200 bg-red-50 text-red-900"
              }`}
            >
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-semibold">
                  {errorCode === "STUDIO_SUSPENDED"
                    ? "Assinatura do Estúdio Suspensa"
                    : errorCode === "STUDIO_INACTIVE"
                    ? "Estúdio Desativado"
                    : "Atenção"}
                </p>
                <p className="mt-0.5">{errorMsg}</p>
              </div>
            </div>
          )}

          {!requiresStudioSelection ? (
            <form method="post" action="/login" onSubmit={handleSignIn} className="space-y-4">
              <div>
                <Label htmlFor="login-email">E-mail</Label>
                <Input
                  id="login-email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  spellCheck={false}
                  enterKeyHint="next"
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (errorMsg) setErrorMsg(null);
                  }}
                  placeholder="voce@estudio.com.br"
                />
              </div>

              <div>
                <div className="mb-1 flex items-center justify-between">
                  <Label htmlFor="login-password" className="mb-0">
                    Senha
                  </Label>
                  <button
                    type="button"
                    onClick={() => {
                      setForgotEmail(email);
                      setForgotFeedback(null);
                      setForgotOpen(true);
                    }}
                    className="text-xs font-medium text-slate-700 underline-offset-2 hover:underline"
                  >
                    Esqueci minha senha
                  </button>
                </div>
                <div className="relative">
                  <Input
                    id="login-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    enterKeyHint="done"
                    required
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (errorMsg) setErrorMsg(null);
                    }}
                    className="pr-12"
                  />
                  <button
                    type="button"
                    aria-pressed={showPassword}
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute inset-y-0 right-1 my-auto inline-flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                <Lock className="h-4 w-4" aria-hidden="true" />
                {isSubmitting ? "Autenticando..." : "Entrar no sistema"}
              </Button>

              <p className="pt-2 text-center text-sm text-muted-foreground">
                Novo estúdio?{" "}
                <Link
                  to="/onboarding"
                  className="font-semibold text-slate-900 underline-offset-2 hover:underline"
                >
                  Criar conta do estúdio
                </Link>
              </p>
            </form>
          ) : (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  Olá, {user?.name}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Sua conta atua em mais de um estúdio. Escolha onde deseja operar agora:
                </p>
              </div>

              <div className="space-y-2.5">
                {availableStudios.map((studio) => (
                  <button
                    key={studio.studio_id}
                    type="button"
                    disabled={!studio.is_operational || isSubmitting}
                    onClick={() => handleSelectStudio(studio.studio_id)}
                    className="flex w-full items-center justify-between rounded-lg border border-border bg-card p-4 text-left transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <div className="flex items-center gap-3">
                      <Building2 className="h-5 w-5 text-slate-700" aria-hidden="true" />
                      <div>
                        <p className="font-semibold text-slate-900">{studio.studio_name}</p>
                        <p className="text-xs text-muted-foreground">
                          Papel: {studio.role} • {studio.timezone}
                        </p>
                      </div>
                    </div>
                    <Badge
                      tone={
                        !studio.is_operational
                          ? "danger"
                          : studio.subscription_status === "ACTIVE"
                          ? "success"
                          : "info"
                      }
                    >
                      {!studio.is_studio_active
                        ? "Inativo"
                        : studio.subscription_status === "SUSPENDED"
                        ? "Suspenso"
                        : studio.subscription_status}
                    </Badge>
                  </button>
                ))}
              </div>

              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={cancelStudioSelection}
              >
                Trocar conta de usuário
              </Button>
            </div>
          )}
        </Card>
      </div>

      <ModalDialog
        open={forgotOpen}
        onClose={() => setForgotOpen(false)}
        title="Recuperar acesso"
        description="Informe seu e-mail cadastrado para receber instruções de redefinição."
      >
        <form onSubmit={handleForgotSubmit} className="space-y-4">
          <div>
            <Label htmlFor="forgot-email">E-mail da conta</Label>
            <Input
              id="forgot-email"
              name="email"
              type="email"
              autoComplete="username"
              spellCheck={false}
              required
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
            />
          </div>
          {forgotFeedback && (
            <p role="status" className="rounded-md bg-slate-100 p-3 text-sm text-slate-800">
              {forgotFeedback}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setForgotOpen(false)}>
              Fechar
            </Button>
            <Button type="submit" disabled={isSendingForgot}>
              {isSendingForgot ? "Enviando..." : "Enviar instruções"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </main>
  );
}
