import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, UserPlus, UserX } from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import type {
  StudioRole,
  TeamMemberDirectory,
  TeamMemberOwner,
} from "@/lib/types";

export function TeamPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const isOwner = currentStudio?.role === "OWNER";

  const [createOpen, setCreateOpen] = React.useState(false);
  const [editingMember, setEditingMember] = React.useState<TeamMemberOwner | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [role, setRole] = React.useState<StudioRole>("PROFESSIONAL");
  const [servicePct, setServicePct] = React.useState("40.00");
  const [productPct, setProductPct] = React.useState("10.00");
  const [isActive, setIsActive] = React.useState(true);

  const ownerTeamQuery = useQuery({
    queryKey: ["team-owner", currentStudio?.studio_id],
    queryFn: () => apiFetch<TeamMemberOwner[]>("/team"),
    enabled: Boolean(currentStudio && isOwner),
  });

  const directoryQuery = useQuery({
    queryKey: ["team-directory", currentStudio?.studio_id],
    queryFn: () => apiFetch<TeamMemberDirectory[]>("/team/directory"),
    enabled: Boolean(currentStudio && !isOwner),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<TeamMemberOwner>("/team", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          password: password || null,
          role,
          commission_service_pct: servicePct,
          commission_product_pct: productPct,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-owner"] });
      setCreateOpen(false);
      setName("");
      setEmail("");
      setPassword("");
      setFormError(null);
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.detail : "Erro ao adicionar membro.");
    },
  });

  const updateMutation = useMutation({
    mutationFn: (membershipId: string) =>
      apiFetch<TeamMemberOwner>(`/team/${membershipId}`, {
        method: "PATCH",
        body: JSON.stringify({
          role,
          commission_service_pct: servicePct,
          commission_product_pct: productPct,
          is_active: isActive,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-owner"] });
      queryClient.invalidateQueries({ queryKey: ["team-me"] });
      setEditingMember(null);
      setFormError(null);
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.detail : "Erro ao atualizar membro.");
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (membershipId: string) =>
      apiFetch<void>(`/team/${membershipId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-owner"] });
    },
    onError: (err) => {
      alert(err instanceof ApiError ? err.detail : "Não foi possível desativar.");
    },
  });

  const openEditModal = (member: TeamMemberOwner) => {
    setFormError(null);
    setRole(member.role);
    setServicePct(member.commission_service_pct);
    setProductPct(member.commission_product_pct);
    setIsActive(member.is_active);
    setEditingMember(member);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Equipe &amp; Comissões
          </h1>
          <p className="text-sm text-muted-foreground">
            {isOwner
              ? "Gerencie acessos RBAC e percentuais separados de perfuração e venda de joias."
              : "Diretório de profissionais ativos deste estúdio."}
          </p>
        </div>

        {isOwner && (
          <Button
            onClick={() => {
              setFormError(null);
              setRole("PROFESSIONAL");
              setServicePct("40.00");
              setProductPct("10.00");
              setCreateOpen(true);
            }}
          >
            <UserPlus className="h-4 w-4" aria-hidden="true" />
            Adicionar Membro
          </Button>
        )}
      </div>

      <Card className="overflow-hidden">
        <div
          tabIndex={0}
          role="region"
          aria-labelledby="team-table-caption"
          className="table-wrapper"
        >
          <table
            className="responsive-data-table text-sm"
            style={
              {
                "--label-2": '"Papel"',
                "--label-3": '"Comissões"',
                "--label-4": '"Status"',
                "--label-5": '"Ações"',
              } as React.CSSProperties
            }
          >
            <caption id="team-table-caption" className="sr-only">
              Membros vinculados ao estúdio atual
            </caption>
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-muted-foreground">
              <tr>
                <th className="px-5 py-3.5">Profissional</th>
                <th className="px-5 py-3.5">Papel</th>
                {isOwner && <th className="px-5 py-3.5">Comissões (Serviço / Joia)</th>}
                <th className="px-5 py-3.5">Status</th>
                {isOwner && <th className="px-5 py-3.5 text-right">Ações</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isOwner
                ? ownerTeamQuery.data?.map((member) => (
                    <tr key={member.membership_id} className="hover:bg-slate-50/70">
                      <th scope="row" className="px-5 py-3.5 text-left font-medium">
                        <div className="font-semibold text-slate-900">{member.name}</div>
                        <div className="text-xs font-normal text-muted-foreground">
                          {member.email}
                        </div>
                      </th>
                      <td className="px-5 py-3.5">
                        <Badge tone="info">{member.role}</Badge>
                      </td>
                      <td className="px-5 py-3.5 font-medium text-slate-800">
                        {member.commission_service_pct}% perf. /{" "}
                        {member.commission_product_pct}% joia
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge tone={member.is_active ? "success" : "danger"}>
                          {member.is_active ? "Ativo" : "Inativo"}
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <div className="inline-flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openEditModal(member)}
                          >
                            <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                            Editar
                          </Button>
                          {member.is_active && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => deactivateMutation.mutate(member.membership_id)}
                            >
                              <UserX className="h-3.5 w-3.5" aria-hidden="true" />
                              Desativar
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                : directoryQuery.data?.map((member) => (
                    <tr key={member.membership_id}>
                      <th scope="row" className="px-5 py-3.5 text-left font-medium">
                        <div className="font-semibold text-slate-900">{member.name}</div>
                        <div className="text-xs font-normal text-muted-foreground">
                          {member.email}
                        </div>
                      </th>
                      <td className="px-5 py-3.5">
                        <Badge tone="info">{member.role}</Badge>
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge tone="success">Ativo</Badge>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal Criar Membro */}
      <ModalDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Adicionar membro à equipe"
        description="Se o profissional já possuir conta em outro estúdio, deixe a senha em branco para vinculá-lo."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
          className="space-y-4"
        >
          {formError && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {formError}
            </p>
          )}
          <div>
            <Label htmlFor="member-name">Nome completo *</Label>
            <Input
              id="member-name"
              name="name"
              autoComplete="name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="member-email">E-mail *</Label>
            <Input
              id="member-email"
              name="email"
              type="email"
              spellCheck={false}
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="member-password">
              Senha inicial (obrigatória apenas para novos usuários)
            </Label>
            <Input
              id="member-password"
              name="new-password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mínimo 8 caracteres"
            />
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-foreground">
              Papel de Acesso (RBAC)
            </legend>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {(["PROFESSIONAL", "RECEPTION", "OWNER"] as StudioRole[]).map((r) => (
                <label
                  key={r}
                  className="flex min-h-[48px] cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
                >
                  <input
                    type="radio"
                    name="role"
                    value={r}
                    checked={role === r}
                    onChange={() => setRole(r)}
                  />
                  <span>{r}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="comm-service">% Comissão Serviço</Label>
              <Input
                id="comm-service"
                name="commission_service_pct"
                inputMode="decimal"
                value={servicePct}
                onChange={(e) => setServicePct(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="comm-product">% Comissão Joia</Label>
              <Input
                id="comm-product"
                name="commission_product_pct"
                inputMode="decimal"
                value={productPct}
                onChange={(e) => setProductPct(e.target.value)}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Salvando..." : "Vincular membro"}
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Modal Editar Membro */}
      <ModalDialog
        open={Boolean(editingMember)}
        onClose={() => setEditingMember(null)}
        title={`Editar vínculo: ${editingMember?.name || ""}`}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (editingMember) {
              updateMutation.mutate(editingMember.membership_id);
            }
          }}
          className="space-y-4"
        >
          {formError && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {formError}
            </p>
          )}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-foreground">Papel</legend>
            <div className="grid grid-cols-3 gap-2">
              {(["PROFESSIONAL", "RECEPTION", "OWNER"] as StudioRole[]).map((r) => (
                <label
                  key={r}
                  className="flex min-h-[48px] cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
                >
                  <input
                    type="radio"
                    name="edit-role"
                    value={r}
                    checked={role === r}
                    onChange={() => setRole(r)}
                  />
                  <span>{r}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="edit-comm-service">% Comissão Serviço</Label>
              <Input
                id="edit-comm-service"
                name="commission_service_pct"
                inputMode="decimal"
                value={servicePct}
                onChange={(e) => setServicePct(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="edit-comm-product">% Comissão Joia</Label>
              <Input
                id="edit-comm-product"
                name="commission_product_pct"
                inputMode="decimal"
                value={productPct}
                onChange={(e) => setProductPct(e.target.value)}
              />
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <input
              id="edit-member-active"
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 accent-slate-900"
            />
            <label htmlFor="edit-member-active" className="text-sm font-medium">
              Vínculo ativo neste estúdio
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setEditingMember(null)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Salvando..." : "Salvar alterações"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}
