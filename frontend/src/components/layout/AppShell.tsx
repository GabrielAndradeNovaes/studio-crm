import * as React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Building2,
  LayoutDashboard,
  LogOut,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { Badge, Button } from "@/components/ui/primitives";
import { useAuth } from "@/features/auth/AuthContext";

export function AppShell() {
  const {
    user,
    currentStudio,
    availableStudios,
    switchStudio,
    logout,
  } = useAuth();
  const navigate = useNavigate();
  const [isSwitching, setIsSwitching] = React.useState(false);

  const handleStudioChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextStudioId = e.target.value;
    if (!nextStudioId || nextStudioId === currentStudio?.studio_id) return;
    setIsSwitching(true);
    try {
      await switchStudio(nextStudioId);
      navigate("/");
    } finally {
      setIsSwitching(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const navItems = [
    ...(currentStudio
      ? [
          {
            to: "/",
            label: "Visão Geral",
            icon: LayoutDashboard,
            end: true,
          },
          {
            to: "/team",
            label: "Equipe",
            icon: Users,
          },
          ...(currentStudio.role === "OWNER"
            ? [
                {
                  to: "/settings",
                  label: "Estúdio & Taxas",
                  icon: Settings,
                },
              ]
            : []),
        ]
      : []),
    ...(user?.is_superadmin
      ? [
          {
            to: "/admin",
            label: "SuperAdmin SaaS",
            icon: ShieldCheck,
          },
        ]
      : []),
  ];

  const operationalStudios = availableStudios.filter((s) => s.is_operational);

  return (
    <div className="min-h-screen bg-background pb-20 md:pb-0">
      {/* Mobile Header */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-card px-4 py-3 md:hidden">
        <div className="flex items-center gap-2.5">
          <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-slate-900 text-white">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-bold leading-tight text-foreground">
              {currentStudio?.studio_name || "Administração SaaS"}
            </p>
            <p className="text-xs text-muted-foreground">
              {currentStudio ? currentStudio.role : "SUPERADMIN"}
            </p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Sair
        </Button>
      </header>

      <div className="mx-auto flex max-w-7xl">
        {/* Desktop Sidebar */}
        <aside className="hidden min-h-screen w-64 shrink-0 flex-col border-r border-border bg-card p-5 md:flex">
          <div className="mb-6 flex items-center gap-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="font-bold text-slate-900">Studio Flow</p>
              <p className="text-xs text-muted-foreground">SaaS Multi-Tenant</p>
            </div>
          </div>

          {operationalStudios.length > 0 && (
            <div className="mb-6 rounded-lg border border-border bg-slate-50 p-3">
              <label
                htmlFor="studio-switcher"
                className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
                Estúdio Ativo
              </label>
              {operationalStudios.length > 1 ? (
                <select
                  id="studio-switcher"
                  disabled={isSwitching}
                  value={currentStudio?.studio_id || ""}
                  onChange={handleStudioChange}
                  className="w-full rounded-md border border-input bg-white px-2.5 py-2 text-sm font-medium text-slate-900"
                >
                  {!currentStudio && (
                    <option value="">Selecione um estúdio...</option>
                  )}
                  {operationalStudios.map((st) => (
                    <option key={st.studio_id} value={st.studio_id}>
                      {st.studio_name} ({st.role})
                    </option>
                  ))}
                </select>
              ) : (
                <p className="text-sm font-semibold text-slate-900">
                  {currentStudio?.studio_name || operationalStudios[0].studio_name}
                </p>
              )}

              {currentStudio && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone="info">{currentStudio.role}</Badge>
                  <Badge
                    tone={
                      currentStudio.subscription_status === "ACTIVE"
                        ? "success"
                        : currentStudio.subscription_status === "PAST_DUE"
                        ? "warning"
                        : "neutral"
                    }
                  >
                    {currentStudio.subscription_status}
                  </Badge>
                </div>
              )}
            </div>
          )}

          <nav aria-label="Navegação principal" className="flex-1 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `flex min-h-[44px] items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                      isActive
                        ? "bg-slate-900 text-white"
                        : "text-slate-700 hover:bg-secondary"
                    }`
                  }
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>

          <div className="mt-6 border-t border-border pt-4">
            <p className="truncate text-sm font-semibold text-slate-900">
              {user?.name}
            </p>
            <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3 w-full"
              onClick={handleLogout}
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Encerrar sessão
            </Button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
          {operationalStudios.length > 1 && (
            <div className="mb-4 md:hidden">
              <label
                htmlFor="mobile-studio-switcher"
                className="mb-1 block text-xs font-semibold text-muted-foreground"
              >
                Alternar Estúdio
              </label>
              <select
                id="mobile-studio-switcher"
                disabled={isSwitching}
                value={currentStudio?.studio_id || ""}
                onChange={handleStudioChange}
                className="min-h-[48px] w-full rounded-md border border-input bg-card px-3 text-sm font-medium"
              >
                {operationalStudios.map((st) => (
                  <option key={st.studio_id} value={st.studio_id}>
                    {st.studio_name} ({st.role})
                  </option>
                ))}
              </select>
            </div>
          )}
          <Outlet />
        </main>
      </div>

      {/* Mobile Bottom Navigation */}
      <nav
        aria-label="Navegação móvel"
        className="fixed inset-x-0 bottom-0 z-20 flex items-center justify-around border-t border-border bg-card px-2 py-1.5 md:hidden"
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex min-h-[48px] min-w-[68px] flex-col items-center justify-center rounded-md px-2 text-xs font-medium ${
                  isActive ? "text-slate-900 font-semibold" : "text-muted-foreground"
                }`
              }
            >
              <Icon className="mb-0.5 h-5 w-5" aria-hidden="true" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
