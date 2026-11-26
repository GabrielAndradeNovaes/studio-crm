import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { AuthProvider, useAuth } from "@/features/auth/AuthContext";
import { LoginPage } from "@/features/auth/LoginPage";
import { OnboardingPage } from "@/features/auth/OnboardingPage";
import { ClientsPage } from "@/features/clients/ClientsPage";
import { PiercingInventoryPage } from "@/features/piercing/PiercingInventoryPage";
import { PiercingServicesPage } from "@/features/piercing/PiercingServicesPage";
import { OverviewPage } from "@/features/studio/OverviewPage";
import { StudioSettingsPage } from "@/features/studio/StudioSettingsPage";
import { SuperAdminPage } from "@/features/studio/SuperAdminPage";
import { TeamPage } from "@/features/studio/TeamPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isBootstrapping, isAuthenticated } = useAuth();
  if (isBootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Carregando sessão segura...
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function OwnerRoute({ children }: { children: React.ReactNode }) {
  const { currentStudio } = useAuth();
  if (currentStudio?.role !== "OWNER") {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

function ModuleRoute({
  moduleName,
  children,
}: {
  moduleName: string;
  children: React.ReactNode;
}) {
  const { currentStudio } = useAuth();
  if (!currentStudio?.enabled_modules?.includes(moduleName)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

function SuperAdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user?.is_superadmin) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/onboarding" element={<OnboardingPage />} />

            <Route
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<OverviewPage />} />
              <Route path="/clients" element={<ClientsPage />} />
              <Route
                path="/piercing/services"
                element={
                  <ModuleRoute moduleName="piercing">
                    <PiercingServicesPage />
                  </ModuleRoute>
                }
              />
              <Route
                path="/piercing/inventory"
                element={
                  <ModuleRoute moduleName="piercing">
                    <PiercingInventoryPage />
                  </ModuleRoute>
                }
              />
              <Route path="/team" element={<TeamPage />} />
              <Route
                path="/settings"
                element={
                  <OwnerRoute>
                    <StudioSettingsPage />
                  </OwnerRoute>
                }
              />
              <Route
                path="/admin"
                element={
                  <SuperAdminRoute>
                    <SuperAdminPage />
                  </SuperAdminRoute>
                }
              />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
