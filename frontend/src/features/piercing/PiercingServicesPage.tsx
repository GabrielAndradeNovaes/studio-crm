import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Clock, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import { formatCurrencyBRL } from "@/lib/dates";
import type { PiercingServiceItem } from "@/lib/types";

const COMMON_ANATOMICAL_SITES = [
  "Helix",
  "Conch",
  "Tragus",
  "Daith",
  "Rook",
  "Flat / Scapha",
  "Lóbulo",
  "Septo",
  "Nostril (Aba Nasal)",
  "Sobrancelha",
  "Labret / Lábio",
  "Língua",
  "Umbigo",
  "Mamilo",
  "Microdermal",
];

export function PiercingServicesPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const isOwner = currentStudio?.role === "OWNER";

  const [searchTerm, setSearchTerm] = React.useState("");
  const [siteFilter, setSiteFilter] = React.useState("");

  const [modalOpen, setModalOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<PiercingServiceItem | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  const [name, setName] = React.useState("");
  const [anatomicalSite, setAnatomicalSite] = React.useState("Helix");
  const [durationMinutes, setDurationMinutes] = React.useState("30");
  const [basePrice, setBasePrice] = React.useState("100.00");
  const [returnDays, setReturnDays] = React.useState("35");
  const [aftercare, setAftercare] = React.useState("");
  const [isActive, setIsActive] = React.useState(true);

  const servicesQuery = useQuery({
    queryKey: ["piercing-services", currentStudio?.studio_id, searchTerm, siteFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (searchTerm.trim()) params.set("q", searchTerm.trim());
      if (siteFilter) params.set("anatomical_site", siteFilter);
      const qs = params.toString();
      return apiFetch<PiercingServiceItem[]>(
        `/piercing/services${qs ? `?${qs}` : ""}`
      );
    },
    enabled: Boolean(currentStudio),
  });

  const openCreate = () => {
    setEditing(null);
    setName("");
    setAnatomicalSite("Helix");
    setDurationMinutes("30");
    setBasePrice("100.00");
    setReturnDays("35");
    setAftercare("");
    setIsActive(true);
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (svc: PiercingServiceItem) => {
    setEditing(svc);
    setName(svc.name);
    setAnatomicalSite(svc.anatomical_site);
    setDurationMinutes(String(svc.duration_minutes));
    setBasePrice(svc.base_price);
    setReturnDays(
      svc.return_days_downsize !== null ? String(svc.return_days_downsize) : ""
    );
    setAftercare(svc.aftercare_instructions || "");
    setIsActive(svc.is_active);
    setFormError(null);
    setModalOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        name: name.trim(),
        anatomical_site: anatomicalSite.trim(),
        duration_minutes: Number(durationMinutes),
        base_price: basePrice,
        return_days_downsize: returnDays.trim() ? Number(returnDays) : null,
        aftercare_instructions: aftercare.trim() || null,
        is_active: isActive,
      };
      if (editing) {
        return apiFetch<PiercingServiceItem>(`/piercing/services/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      }
      return apiFetch<PiercingServiceItem>("/piercing/services", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["piercing-services"] });
      setModalOpen(false);
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiError ? err.detail : "Erro ao salvar serviço."
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/piercing/services/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["piercing-services"] });
    },
    onError: (err) => {
      alert(err instanceof ApiError ? err.detail : "Erro ao remover serviço.");
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Catálogo de Perfurações
          </h1>
          <p className="text-sm text-muted-foreground">
            Serviços por local anatômico, tempo médio, preço base e recomendação de downsize.
          </p>
        </div>

        {isOwner && (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Novo Serviço
          </Button>
        )}
      </div>

      <search aria-label="Filtrar serviços de perfuração">
        <Card className="p-4">
          <form
            onSubmit={(e) => e.preventDefault()}
            className="grid grid-cols-1 gap-3 sm:grid-cols-2"
          >
            <div className="relative">
              <Label htmlFor="svc-search" className="sr-only">
                Buscar perfuração
              </Label>
              <Search
                className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id="svc-search"
                type="search"
                enterKeyHint="search"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Buscar por nome ou local anatômico..."
                className="pl-9"
              />
            </div>

            <div>
              <Label htmlFor="svc-site-filter" className="sr-only">
                Filtrar por local anatômico
              </Label>
              <select
                id="svc-site-filter"
                value={siteFilter}
                onChange={(e) => setSiteFilter(e.target.value)}
                className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-sm"
              >
                <option value="">Todos os locais anatômicos</option>
                {COMMON_ANATOMICAL_SITES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </form>
        </Card>
      </search>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {servicesQuery.data?.length === 0 && (
          <Card className="col-span-full p-8 text-center text-sm text-muted-foreground">
            Nenhum serviço de perfuração cadastrado ainda.
          </Card>
        )}

        {servicesQuery.data?.map((svc) => (
          <Card key={svc.id} className="flex flex-col justify-between p-5">
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="font-semibold text-slate-900">{svc.name}</h2>
                  <p className="text-xs text-muted-foreground">
                    Local: <strong>{svc.anatomical_site}</strong>
                  </p>
                </div>
                <Badge tone={svc.is_active ? "success" : "neutral"}>
                  {svc.is_active ? "Ativo" : "Inativo"}
                </Badge>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-700">
                <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 font-medium">
                  <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                  {svc.duration_minutes} min
                </span>
                {svc.return_days_downsize !== null && (
                  <span className="inline-flex items-center gap-1 rounded-md bg-sky-50 px-2.5 py-1 font-medium text-sky-900">
                    <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />
                    Downsize: {svc.return_days_downsize} dias
                  </span>
                )}
              </div>

              {svc.aftercare_instructions && (
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {svc.aftercare_instructions}
                </p>
              )}
            </div>

            <div className="mt-4 flex items-center justify-between border-t border-border pt-3.5">
              <span className="text-lg font-bold text-slate-900">
                {formatCurrencyBRL(svc.base_price)}
              </span>

              {isOwner && (
                <div className="inline-flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openEdit(svc)}
                  >
                    <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                    Editar
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => deleteMutation.mutate(svc.id)}
                    aria-label={`Arquivar ${svc.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-red-600" aria-hidden="true" />
                  </Button>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>

      <ModalDialog
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Editar Serviço de Perfuração" : "Novo Serviço de Perfuração"}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveMutation.mutate();
          }}
          className="space-y-4"
        >
          {formError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {formError}
            </div>
          )}

          <div>
            <Label htmlFor="svc-name">Nome do Procedimento *</Label>
            <Input
              id="svc-name"
              name="name"
              required
              minLength={2}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex.: Perfuração Conch com Titânio"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="svc-site">Local Anatômico *</Label>
              <Input
                id="svc-site"
                name="anatomical_site"
                list="anatomical-sites-datalist"
                required
                value={anatomicalSite}
                onChange={(e) => setAnatomicalSite(e.target.value)}
              />
              <datalist id="anatomical-sites-datalist">
                {COMMON_ANATOMICAL_SITES.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>
            <div>
              <Label htmlFor="svc-price">Preço Base (R$) *</Label>
              <Input
                id="svc-price"
                name="base_price"
                inputMode="decimal"
                required
                value={basePrice}
                onChange={(e) => setBasePrice(e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="svc-duration">Tempo Médio (minutos) *</Label>
              <Input
                id="svc-duration"
                name="duration_minutes"
                inputMode="numeric"
                required
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="svc-downsize">Retorno / Downsize (dias)</Label>
              <Input
                id="svc-downsize"
                name="return_days_downsize"
                inputMode="numeric"
                value={returnDays}
                onChange={(e) => setReturnDays(e.target.value)}
                placeholder="Ex.: 35"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="svc-aftercare">Orientações de Cicatrização / Pós</Label>
            <textarea
              id="svc-aftercare"
              name="aftercare_instructions"
              rows={3}
              value={aftercare}
              onChange={(e) => setAftercare(e.target.value)}
              className="w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-sm"
            />
          </div>

          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 accent-slate-900"
            />
            Serviço ativo para agendamento e PDV
          </label>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setModalOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Salvando..." : "Salvar serviço"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}
