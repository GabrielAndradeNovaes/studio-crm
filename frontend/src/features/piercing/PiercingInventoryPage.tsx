import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpDown,
  History,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import { formatCurrencyBRL } from "@/lib/dates";
import type {
  InventoryMovementItem,
  InventoryMovementType,
  PiercingItemType,
  PiercingProductItem,
} from "@/lib/types";

const MATERIALS = [
  "Titânio ASTM F136",
  "Ouro 18k",
  "Nióbio",
  "Aço 316L",
  "Bioplast / PTFE",
  "N/A",
];

const THREADING_TYPES = [
  "Rosca Interna",
  "Push-in / Threadless",
  "Clicker / Argola",
  "Rosca Externa",
  "N/A",
];

export function PiercingInventoryPage() {
  const { currentStudio } = useAuth();
  const queryClient = useQueryClient();
  const isOwner = currentStudio?.role === "OWNER";

  // Filtros combinados
  const [searchTerm, setSearchTerm] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("");
  const [materialFilter, setMaterialFilter] = React.useState("");
  const [gaugeFilter, setGaugeFilter] = React.useState("");
  const [sizeFilter, setSizeFilter] = React.useState("");
  const [lowStockOnly, setLowStockOnly] = React.useState(false);

  // Modais
  const [productModalOpen, setProductModalOpen] = React.useState(false);
  const [editingProduct, setEditingProduct] =
    React.useState<PiercingProductItem | null>(null);
  const [kardexProduct, setKardexProduct] =
    React.useState<PiercingProductItem | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  // Form Produto
  const [sku, setSku] = React.useState("");
  const [name, setName] = React.useState("");
  const [itemType, setItemType] = React.useState<PiercingItemType>("JEWELRY");
  const [categorySite, setCategorySite] = React.useState("Auricular");
  const [material, setMaterial] = React.useState("Titânio ASTM F136");
  const [threadingType, setThreadingType] = React.useState("Rosca Interna");
  const [gaugeThickness, setGaugeThickness] = React.useState("1.2mm");
  const [lengthDiameter, setLengthDiameter] = React.useState("8mm");
  const [costPrice, setCostPrice] = React.useState("25.00");
  const [salePrice, setSalePrice] = React.useState("120.00");
  const [initialStock, setInitialStock] = React.useState("5");
  const [minStockAlert, setMinStockAlert] = React.useState("2");
  const [isActive, setIsActive] = React.useState(true);

  // Form Kardex Movement
  const [movType, setMovType] = React.useState<InventoryMovementType>("IN_PURCHASE");
  const [movDelta, setMovDelta] = React.useState("5");
  const [movUnitCost, setMovUnitCost] = React.useState("");
  const [movReason, setMovReason] = React.useState("");
  const [movError, setMovError] = React.useState<string | null>(null);

  const productsQuery = useQuery({
    queryKey: [
      "piercing-products",
      currentStudio?.studio_id,
      searchTerm,
      typeFilter,
      materialFilter,
      gaugeFilter,
      sizeFilter,
      lowStockOnly,
    ],
    queryFn: () => {
      const params = new URLSearchParams();
      if (searchTerm.trim()) params.set("q", searchTerm.trim());
      if (typeFilter) params.set("item_type", typeFilter);
      if (materialFilter) params.set("material", materialFilter);
      if (gaugeFilter.trim()) params.set("gauge_thickness", gaugeFilter.trim());
      if (sizeFilter.trim()) params.set("length_diameter", sizeFilter.trim());
      if (lowStockOnly) params.set("low_stock_only", "true");
      const qs = params.toString();
      return apiFetch<PiercingProductItem[]>(
        `/piercing/products${qs ? `?${qs}` : ""}`
      );
    },
    enabled: Boolean(currentStudio),
  });

  const movementsQuery = useQuery({
    queryKey: ["piercing-movements", kardexProduct?.id],
    queryFn: () =>
      apiFetch<InventoryMovementItem[]>(
        `/piercing/products/${kardexProduct!.id}/movements`
      ),
    enabled: Boolean(kardexProduct),
  });

  const openCreateProduct = () => {
    setEditingProduct(null);
    setSku("");
    setName("");
    setItemType("JEWELRY");
    setCategorySite("Auricular");
    setMaterial("Titânio ASTM F136");
    setThreadingType("Rosca Interna");
    setGaugeThickness("1.2mm");
    setLengthDiameter("8mm");
    setCostPrice("25.00");
    setSalePrice("120.00");
    setInitialStock("5");
    setMinStockAlert("2");
    setIsActive(true);
    setFormError(null);
    setProductModalOpen(true);
  };

  const openEditProduct = (p: PiercingProductItem) => {
    setEditingProduct(p);
    setSku(p.sku || "");
    setName(p.name);
    setItemType(p.item_type);
    setCategorySite(p.category_site || "");
    setMaterial(p.material || "");
    setThreadingType(p.threading_type || "");
    setGaugeThickness(p.gauge_thickness || "");
    setLengthDiameter(p.length_diameter || "");
    setCostPrice(p.cost_price ?? "0.00");
    setSalePrice(p.sale_price);
    setMinStockAlert(String(p.min_stock_alert));
    setIsActive(p.is_active);
    setFormError(null);
    setProductModalOpen(true);
  };

  const saveProductMutation = useMutation({
    mutationFn: () => {
      if (editingProduct) {
        return apiFetch<PiercingProductItem>(
          `/piercing/products/${editingProduct.id}`,
          {
            method: "PATCH",
            body: JSON.stringify({
              sku: sku.trim() || null,
              name: name.trim(),
              item_type: itemType,
              category_site: categorySite.trim() || null,
              material: material.trim() || null,
              threading_type: threadingType.trim() || null,
              gauge_thickness: gaugeThickness.trim() || null,
              length_diameter: lengthDiameter.trim() || null,
              cost_price: costPrice,
              sale_price: salePrice,
              min_stock_alert: Number(minStockAlert),
              is_active: isActive,
            }),
          }
        );
      }
      return apiFetch<PiercingProductItem>("/piercing/products", {
        method: "POST",
        body: JSON.stringify({
          sku: sku.trim() || null,
          name: name.trim(),
          item_type: itemType,
          category_site: categorySite.trim() || null,
          material: material.trim() || null,
          threading_type: threadingType.trim() || null,
          gauge_thickness: gaugeThickness.trim() || null,
          length_diameter: lengthDiameter.trim() || null,
          cost_price: costPrice,
          sale_price: salePrice,
          initial_stock: Number(initialStock),
          min_stock_alert: Number(minStockAlert),
          is_active: isActive,
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["piercing-products"] });
      setProductModalOpen(false);
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiError ? err.detail : "Erro ao salvar produto."
      );
    },
  });

  const createMovementMutation = useMutation({
    mutationFn: () => {
      if (!kardexProduct) throw new Error("Produto inválido");
      return apiFetch<InventoryMovementItem>(
        `/piercing/products/${kardexProduct.id}/movements`,
        {
          method: "POST",
          body: JSON.stringify({
            movement_type: movType,
            quantity_delta: Number(movDelta),
            unit_cost: movUnitCost.trim() ? movUnitCost.trim() : null,
            reason: movReason.trim(),
          }),
        }
      );
    },
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["piercing-products"] });
      queryClient.invalidateQueries({
        queryKey: ["piercing-movements", kardexProduct?.id],
      });
      setKardexProduct((prev) =>
        prev ? { ...prev, stock_quantity: created.resulting_stock } : null
      );
      setMovReason("");
      setMovUnitCost("");
      setMovError(null);
    },
    onError: (err) => {
      setMovError(
        err instanceof ApiError ? err.detail : "Erro ao registrar movimentação."
      );
    },
  });

  const deleteProductMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/piercing/products/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["piercing-products"] });
    },
    onError: (err) => {
      alert(err instanceof ApiError ? err.detail : "Erro ao arquivar item.");
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Estoque de Joias &amp; Kardex
          </h1>
          <p className="text-sm text-muted-foreground">
            Controle de joias (Titânio ASTM F136, Ouro 18k), insumos pós-piercing e rastreabilidade imutável.
          </p>
        </div>

        {isOwner && (
          <Button onClick={openCreateProduct}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nova Joia / Produto
          </Button>
        )}
      </div>

      {/* Filtros combinados em <search> */}
      <search aria-label="Filtrar estoque de joias e produtos">
        <Card className="p-4">
          <form
            onSubmit={(e) => e.preventDefault()}
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6"
          >
            <div className="relative lg:col-span-2">
              <Label htmlFor="inv-search" className="sr-only">
                Buscar por nome ou SKU
              </Label>
              <Search
                className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id="inv-search"
                type="search"
                enterKeyHint="search"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Nome, SKU ou categoria..."
                className="pl-9"
              />
            </div>

            <div>
              <Label htmlFor="inv-type" className="sr-only">
                Tipo de item
              </Label>
              <select
                id="inv-type"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 py-2.5 text-sm"
              >
                <option value="">Todos os tipos</option>
                <option value="JEWELRY">Joia de Perfuração</option>
                <option value="AFTERCARE_PRODUCT">Insumo Pós-Piercing</option>
              </select>
            </div>

            <div>
              <Label htmlFor="inv-mat" className="sr-only">
                Material
              </Label>
              <select
                id="inv-mat"
                value={materialFilter}
                onChange={(e) => setMaterialFilter(e.target.value)}
                className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 py-2.5 text-sm"
              >
                <option value="">Qualquer material</option>
                {MATERIALS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <Input
                aria-label="Filtrar por calibre"
                value={gaugeFilter}
                onChange={(e) => setGaugeFilter(e.target.value)}
                placeholder="1.2mm"
              />
              <Input
                aria-label="Filtrar por tamanho"
                value={sizeFilter}
                onChange={(e) => setSizeFilter(e.target.value)}
                placeholder="8mm"
              />
            </div>

            <label className="flex min-h-[48px] cursor-pointer items-center gap-2 rounded-md border border-amber-300 bg-amber-50/60 px-3 text-xs font-semibold text-amber-950">
              <input
                type="checkbox"
                checked={lowStockOnly}
                onChange={(e) => setLowStockOnly(e.target.checked)}
                className="h-4 w-4 accent-slate-900"
              />
              <span>Estoque Crítico / Zerado</span>
            </label>
          </form>
        </Card>
      </search>

      <Card className="overflow-hidden">
        <div
          tabIndex={0}
          role="region"
          aria-labelledby="inventory-table-caption"
          className="table-wrapper"
        >
          <table
            className="responsive-data-table text-sm"
            style={
              {
                "--label-2": '"Especificação"',
                "--label-3": isOwner ? '"Custo / Venda"' : '"Preço Venda"',
                "--label-4": '"Saldo"',
                "--label-5": '"Ações"',
              } as React.CSSProperties
            }
          >
            <caption id="inventory-table-caption" className="sr-only">
              Catálogo e saldo de estoque de joias e produtos pós-piercing
            </caption>
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-muted-foreground">
              <tr>
                <th className="px-5 py-3.5">Joia / Produto</th>
                <th className="px-5 py-3.5">Material &amp; Medidas</th>
                <th className="px-5 py-3.5">
                  {isOwner ? "Custo / Preço Venda" : "Preço de Venda"}
                </th>
                <th className="px-5 py-3.5">Saldo Atual</th>
                <th className="px-5 py-3.5 text-right">Ações / Kardex</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {productsQuery.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-muted-foreground">
                    Nenhum item encontrado com os filtros selecionados.
                  </td>
                </tr>
              )}

              {productsQuery.data?.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/70">
                  <th scope="row" className="px-5 py-3.5 text-left font-medium">
                    <div className="font-semibold text-slate-900">{item.name}</div>
                    <div className="text-xs font-normal text-muted-foreground">
                      {item.sku ? `SKU: ${item.sku} • ` : ""}
                      {item.item_type === "JEWELRY" ? "Joia" : "Pós-Piercing"}
                      {item.category_site ? ` • ${item.category_site}` : ""}
                    </div>
                  </th>
                  <td className="px-5 py-3.5 text-xs text-slate-700">
                    <div>{item.material || "—"}</div>
                    <div className="text-muted-foreground">
                      {[
                        item.threading_type,
                        item.gauge_thickness,
                        item.length_diameter,
                      ]
                        .filter(Boolean)
                        .join(" • ") || "—"}
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="font-semibold text-slate-900">
                      {formatCurrencyBRL(item.sale_price)}
                    </div>
                    {isOwner && item.cost_price !== undefined && (
                      <div className="text-xs text-muted-foreground">
                        Custo: {formatCurrencyBRL(item.cost_price)}
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-bold text-slate-900">
                        {item.stock_quantity} un
                      </span>
                      {item.stock_quantity === 0 ? (
                        <Badge tone="danger">Zerado</Badge>
                      ) : item.is_low_stock ? (
                        <Badge tone="warning" className="gap-1">
                          <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                          Mín: {item.min_stock_alert}
                        </Badge>
                      ) : (
                        <Badge tone="success">OK</Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <div className="inline-flex flex-wrap justify-end gap-1.5">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          setMovError(null);
                          setMovType("IN_PURCHASE");
                          setMovDelta("5");
                          setMovReason("");
                          setMovUnitCost("");
                          setKardexProduct(item);
                        }}
                      >
                        {isOwner ? (
                          <>
                            <ArrowUpDown className="h-3.5 w-3.5" aria-hidden="true" />
                            Movimentar / Kardex
                          </>
                        ) : (
                          <>
                            <History className="h-3.5 w-3.5" aria-hidden="true" />
                            Ver Kardex
                          </>
                        )}
                      </Button>

                      {isOwner && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openEditProduct(item)}
                          >
                            <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                            Editar
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={`Arquivar ${item.name}`}
                            onClick={() => deleteProductMutation.mutate(item.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5 text-red-600" aria-hidden="true" />
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal Cadastro / Edição Cadastral de Produto (sem edição direta de saldo!) */}
      <ModalDialog
        open={productModalOpen}
        onClose={() => setProductModalOpen(false)}
        title={
          editingProduct ? "Editar Joia / Produto" : "Cadastrar Joia / Produto"
        }
        description={
          editingProduct
            ? "O saldo de estoque só pode ser alterado via Movimentação (Kardex)."
            : "Se o estoque inicial for maior que zero, o registro inicial no Kardex será criado automaticamente."
        }
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveProductMutation.mutate();
          }}
          className="max-h-[75vh] space-y-4 overflow-y-auto pr-1"
        >
          {formError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900">
              {formError}
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="sm:col-span-2">
              <Label htmlFor="prod-name">Nome do Item *</Label>
              <Input
                id="prod-name"
                name="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex.: Labret Titânio Topo Opala"
              />
            </div>
            <div>
              <Label htmlFor="prod-sku">SKU (opcional)</Label>
              <Input
                id="prod-sku"
                name="sku"
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                placeholder="TIT-LAB-08"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="prod-type">Tipo *</Label>
              <select
                id="prod-type"
                value={itemType}
                onChange={(e) => setItemType(e.target.value as PiercingItemType)}
                className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3.5 py-2.5 text-sm"
              >
                <option value="JEWELRY">Joia de Perfuração</option>
                <option value="AFTERCARE_PRODUCT">Insumo Pós-Piercing</option>
              </select>
            </div>
            <div>
              <Label htmlFor="prod-cat">Categoria / Local</Label>
              <Input
                id="prod-cat"
                value={categorySite}
                onChange={(e) => setCategorySite(e.target.value)}
                placeholder="Auricular, Nasal, Cuidados..."
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="prod-mat">Material</Label>
              <Input
                id="prod-mat"
                list="materials-datalist"
                value={material}
                onChange={(e) => setMaterial(e.target.value)}
              />
              <datalist id="materials-datalist">
                {MATERIALS.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
            <div>
              <Label htmlFor="prod-thread">Fecho / Rosca</Label>
              <Input
                id="prod-thread"
                list="threading-datalist"
                value={threadingType}
                onChange={(e) => setThreadingType(e.target.value)}
              />
              <datalist id="threading-datalist">
                {THREADING_TYPES.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="prod-gauge">Espessura / Calibre</Label>
              <Input
                id="prod-gauge"
                value={gaugeThickness}
                onChange={(e) => setGaugeThickness(e.target.value)}
                placeholder="Ex.: 1.2mm (16G)"
              />
            </div>
            <div>
              <Label htmlFor="prod-size">Comprimento / Diâmetro</Label>
              <Input
                id="prod-size"
                value={lengthDiameter}
                onChange={(e) => setLengthDiameter(e.target.value)}
                placeholder="Ex.: 8mm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="prod-cost">Preço de Custo (R$) *</Label>
              <Input
                id="prod-cost"
                inputMode="decimal"
                required
                value={costPrice}
                onChange={(e) => setCostPrice(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="prod-sale">Preço de Venda (R$) *</Label>
              <Input
                id="prod-sale"
                inputMode="decimal"
                required
                value={salePrice}
                onChange={(e) => setSalePrice(e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {!editingProduct && (
              <div>
                <Label htmlFor="prod-init-stock">Saldo Inicial *</Label>
                <Input
                  id="prod-init-stock"
                  inputMode="numeric"
                  required
                  value={initialStock}
                  onChange={(e) => setInitialStock(e.target.value)}
                />
              </div>
            )}
            <div>
              <Label htmlFor="prod-min-stock">Alerta Estoque Mínimo *</Label>
              <Input
                id="prod-min-stock"
                inputMode="numeric"
                required
                value={minStockAlert}
                onChange={(e) => setMinStockAlert(e.target.value)}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setProductModalOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saveProductMutation.isPending}>
              {saveProductMutation.isPending ? "Salvando..." : "Salvar item"}
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Modal Kardex & Movimentação de Estoque */}
      <ModalDialog
        open={Boolean(kardexProduct)}
        onClose={() => setKardexProduct(null)}
        title={`Kardex: ${kardexProduct?.name || ""}`}
        description={`Saldo atual: ${kardexProduct?.stock_quantity ?? 0} unidade(s)`}
      >
        <div className="max-h-[75vh] space-y-5 overflow-y-auto pr-1">
          {isOwner && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMovementMutation.mutate();
              }}
              className="space-y-3 rounded-lg border border-border bg-slate-50 p-4"
            >
              <h2 className="text-sm font-semibold text-slate-900">
                Registrar Nova Movimentação
              </h2>
              {movError && (
                <p role="alert" className="rounded-md bg-red-50 p-2.5 text-xs text-red-900">
                  {movError}
                </p>
              )}

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="mov-type">Tipo de Movimento *</Label>
                  <select
                    id="mov-type"
                    value={movType}
                    onChange={(e) =>
                      setMovType(e.target.value as InventoryMovementType)
                    }
                    className="flex min-h-[48px] w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
                  >
                    <option value="IN_PURCHASE">Entrada de Compra (+)</option>
                    <option value="ADJUSTMENT">Ajuste / Avaria (+ ou -)</option>
                    <option value="RETURN_REFUND">Devolução (+)</option>
                  </select>
                </div>
                <div>
                  <Label htmlFor="mov-delta">
                    Quantidade ({movType === "ADJUSTMENT" ? "ex.: -2 ou 3" : "ex.: 5"}) *
                  </Label>
                  <Input
                    id="mov-delta"
                    required
                    value={movDelta}
                    onChange={(e) => setMovDelta(e.target.value)}
                  />
                </div>
              </div>

              {movType === "IN_PURCHASE" && (
                <div>
                  <Label htmlFor="mov-cost">
                    Novo Custo Unitário (R$ — opcional)
                  </Label>
                  <Input
                    id="mov-cost"
                    inputMode="decimal"
                    value={movUnitCost}
                    onChange={(e) => setMovUnitCost(e.target.value)}
                    placeholder="Deixe vazio para manter o custo atual"
                  />
                </div>
              )}

              <div>
                <Label htmlFor="mov-reason">Motivo / Documento *</Label>
                <Input
                  id="mov-reason"
                  required
                  minLength={2}
                  value={movReason}
                  onChange={(e) => setMovReason(e.target.value)}
                  placeholder="Ex.: NF Fornecedor #410 ou Esterilização danificada"
                />
              </div>

              <div className="flex justify-end">
                <Button type="submit" size="sm" disabled={createMovementMutation.isPending}>
                  {createMovementMutation.isPending
                    ? "Lançando..."
                    : "Confirmar movimentação"}
                </Button>
              </div>
            </form>
          )}

          <div>
            <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Histórico Imutável (Kardex)
            </h2>
            <div className="space-y-2">
              {movementsQuery.data?.map((mov) => (
                <div
                  key={mov.id}
                  className="flex items-center justify-between rounded-md border border-border bg-card p-3 text-xs"
                >
                  <div>
                    <div className="flex items-center gap-2 font-semibold text-slate-900">
                      <Badge
                        tone={mov.quantity_delta > 0 ? "success" : "warning"}
                      >
                        {mov.quantity_delta > 0
                          ? `+${mov.quantity_delta}`
                          : mov.quantity_delta}
                      </Badge>
                      <span>{mov.movement_type}</span>
                    </div>
                    <p className="mt-1 text-muted-foreground">{mov.reason}</p>
                    <p className="text-[11px] text-slate-400">
                      {new Date(mov.created_at).toLocaleString("pt-BR")}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-slate-900">
                      Saldo: {mov.resulting_stock} un
                    </div>
                    {isOwner && mov.unit_cost_snapshot !== undefined && (
                      <div className="text-muted-foreground">
                        Custo: {formatCurrencyBRL(mov.unit_cost_snapshot)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </ModalDialog>
    </div>
  );
}
