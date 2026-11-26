import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { ApiError, apiFetch } from "@/lib/api";
import type { StudioDetails, SubscriptionStatus } from "@/lib/types";

export function SuperAdminPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  const [name, setName] = React.useState("");
  const [ownerName, setOwnerName] = React.useState("");
  const [ownerEmail, setOwnerEmail] = React.useState("");
  const [ownerPassword, setOwnerPassword] = React.useState("");
  const [enableTattoo, setEnableTattoo] = React.useState(false);

  const studiosQuery = useQuery({
    queryKey: ["superadmin-studios"],
    queryFn: () => apiFetch<StudioDetails[]>("/admin/studios"),
  });

  const createStudioMutation = useMutation({
    mutationFn: () =>
      apiFetch<StudioDetails>("/admin/studios", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          enabled_modules: enableTattoo ? ["piercing", "tattoo"] : ["piercing"],
          subscription_status: "ACTIVE",
          owner_name: ownerName.trim(),
          owner_email: ownerEmail.trim(),
          owner_password: ownerPassword || null,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["superadmin-studios"] });
      setCreateOpen(false);
      setName("");
      setOwnerName("");
      setOwnerEmail("");
      setOwnerPassword("");
      setErrorMsg(null);
    },
    onError: (err) => {
      setErrorMsg(err instanceof ApiError ? err.detail : "Erro ao criar estúdio.");
    },
  });

  const patchGovernanceMutation = useMutation({
    mutationFn: (payload: {
      studioId: string;
      subscription_status?: SubscriptionStatus;
      is_active?: boolean;
      enabled_modules?: string[];
    }) =>
      apiFetch<StudioDetails>(`/admin/studios/${payload.studioId}`, {
        method: "PATCH",
        body: JSON.stringify({
          subscription_status: payload.subscription_status,
          is_active: payload.is_active,
          enabled_modules: payload.enabled_modules,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["superadmin-studios"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Governança Comercial SaaS (SuperAdmin)
          </h1>
          <p className="text-sm text-muted-foreground">
            Gerencie estúdios clientes, status de assinatura e ativação modular (Piercing / Tatuagem).
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Provisionar Estúdio Cliente
        </Button>
      </div>

      <Card className="overflow-hidden">
        <div
          tabIndex={0}
          role="region"
          aria-labelledby="sa-studios-caption"
          className="table-wrapper"
        >
          <table
            className="responsive-data-table text-sm"
            style={
              {
                "--label-2": '"Assinatura"',
                "--label-3": '"Módulos"',
                "--label-4": '"Fuso"',
                "--label-5": '"Ações"',
              } as React.CSSProperties
            }
          >
            <caption id="sa-studios-caption" className="sr-only">
              Todos os estúdios provisionados na plataforma SaaS
            </caption>
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-muted-foreground">
              <tr>
                <th className="px-5 py-3.5">Estúdio</th>
                <th className="px-5 py-3.5">Assinatura</th>
                <th className="px-5 py-3.5">Módulos</th>
                <th className="px-5 py-3.5">Fuso</th>
                <th className="px-5 py-3.5 text-right">Governança</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {studiosQuery.data?.map((st) => {
                const hasTattoo = st.enabled_modules.includes("tattoo");
                return (
                  <tr key={st.id}>
                    <th scope="row" className="px-5 py-3.5 text-left font-medium">
                      <div className="font-semibold text-slate-900">{st.name}</div>
                      <div className="text-xs font-normal text-muted-foreground">
                        /{st.slug}
                      </div>
                    </th>
                    <td className="px-5 py-3.5">
                      <Badge
                        tone={
                          !st.is_active || st.subscription_status === "SUSPENDED"
                            ? "danger"
                            : st.subscription_status === "ACTIVE"
                            ? "success"
                            : "warning"
                        }
                      >
                        {!st.is_active ? "INACTIVE" : st.subscription_status}
                      </Badge>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex flex-wrap gap-1">
                        {st.enabled_modules.map((m) => (
                          <Badge key={m} tone="info">
                            {m}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-muted-foreground">{st.timezone}</td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="inline-flex flex-wrap justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            patchGovernanceMutation.mutate({
                              studioId: st.id,
                              enabled_modules: hasTattoo
                                ? ["piercing"]
                                : ["piercing", "tattoo"],
                            })
                          }
                        >
                          {hasTattoo ? "Desativar Tattoo" : "Ativar Tattoo"}
                        </Button>
                        <Button
                          size="sm"
                          variant={
                            st.subscription_status === "SUSPENDED"
                              ? "primary"
                              : "destructive"
                          }
                          onClick={() =>
                            patchGovernanceMutation.mutate({
                              studioId: st.id,
                              subscription_status:
                                st.subscription_status === "SUSPENDED"
                                  ? "ACTIVE"
                                  : "SUSPENDED",
                            })
                          }
                        >
                          {st.subscription_status === "SUSPENDED"
                            ? "Reativar"
                            : "Suspender"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <ModalDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Provisionar Novo Estúdio Cliente"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createStudioMutation.mutate();
          }}
          className="space-y-4"
        >
          {errorMsg && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {errorMsg}
            </p>
          )}
          <div>
            <Label htmlFor="sa-studio-name">Nome do Estúdio *</Label>
            <Input
              id="sa-studio-name"
              name="name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="sa-owner-name">Nome do Proprietário *</Label>
            <Input
              id="sa-owner-name"
              name="owner_name"
              required
              value={ownerName}
              onChange={(e) => setOwnerName(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="sa-owner-email">E-mail do Proprietário *</Label>
            <Input
              id="sa-owner-email"
              name="owner_email"
              type="email"
              spellCheck={false}
              required
              value={ownerEmail}
              onChange={(e) => setOwnerEmail(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="sa-owner-pwd">Senha Inicial</Label>
            <Input
              id="sa-owner-pwd"
              name="owner_password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={ownerPassword}
              onChange={(e) => setOwnerPassword(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={enableTattoo}
              onChange={(e) => setEnableTattoo(e.target.checked)}
              className="h-4 w-4 accent-slate-900"
            />
            Habilitar também o Módulo Tatuagem
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={createStudioMutation.isPending}>
              {createStudioMutation.isPending ? "Criando..." : "Criar estúdio"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}
