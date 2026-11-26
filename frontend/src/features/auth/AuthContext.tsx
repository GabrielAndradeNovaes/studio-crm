import * as React from "react";
import { apiFetch, setAccessToken, silentRefreshSession } from "@/lib/api";
import type {
  AuthenticatedUserSummary,
  AuthSessionResponse,
  StudioMembershipOption,
} from "@/lib/types";

interface AuthContextValue {
  isBootstrapping: boolean;
  isAuthenticated: boolean;
  requiresStudioSelection: boolean;
  selectionToken: string | null;
  user: AuthenticatedUserSummary | null;
  currentStudio: StudioMembershipOption | null;
  availableStudios: StudioMembershipOption[];
  login: (email: string, password: string) => Promise<AuthSessionResponse>;
  selectStudio: (studioId: string) => Promise<AuthSessionResponse>;
  switchStudio: (studioId: string) => Promise<AuthSessionResponse>;
  reloadSession: () => Promise<void>;
  logout: () => Promise<void>;
  cancelStudioSelection: () => void;
}

const AuthContext = React.createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isBootstrapping, setIsBootstrapping] = React.useState(true);
  const [requiresStudioSelection, setRequiresStudioSelection] = React.useState(false);
  const [selectionToken, setSelectionToken] = React.useState<string | null>(null);
  const [user, setUser] = React.useState<AuthenticatedUserSummary | null>(null);
  const [currentStudio, setCurrentStudio] = React.useState<StudioMembershipOption | null>(null);
  const [availableStudios, setAvailableStudios] = React.useState<StudioMembershipOption[]>([]);

  const applySession = React.useCallback((session: AuthSessionResponse) => {
    setUser(session.user);
    setAvailableStudios(session.available_studios || []);
    if (session.requires_studio_selection) {
      setAccessToken(null);
      setRequiresStudioSelection(true);
      setSelectionToken(session.selection_token);
      setCurrentStudio(null);
    } else {
      if (session.access_token) {
        setAccessToken(session.access_token);
      }
      setRequiresStudioSelection(false);
      setSelectionToken(null);
      setCurrentStudio(session.current_studio);
    }
  }, []);

  const clearState = React.useCallback(() => {
    setAccessToken(null);
    setRequiresStudioSelection(false);
    setSelectionToken(null);
    setUser(null);
    setCurrentStudio(null);
    setAvailableStudios([]);
  }, []);

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      const refreshed = await silentRefreshSession();
      if (mounted && refreshed) {
        applySession(refreshed);
      }
      if (mounted) {
        setIsBootstrapping(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [applySession]);

  const login = React.useCallback(
    async (email: string, password: string) => {
      const data = await apiFetch<AuthSessionResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
        skipAuthRefresh: true,
      });
      applySession(data);
      return data;
    },
    [applySession]
  );

  const selectStudio = React.useCallback(
    async (studioId: string) => {
      if (!selectionToken) {
        throw new Error("Sessão de seleção expirada. Faça login novamente.");
      }
      const data = await apiFetch<AuthSessionResponse>("/auth/select-studio", {
        method: "POST",
        body: JSON.stringify({
          selection_token: selectionToken,
          studio_id: studioId,
        }),
        skipAuthRefresh: true,
      });
      applySession(data);
      return data;
    },
    [selectionToken, applySession]
  );

  const switchStudio = React.useCallback(
    async (studioId: string) => {
      const data = await apiFetch<AuthSessionResponse>("/auth/switch-studio", {
        method: "POST",
        body: JSON.stringify({ studio_id: studioId }),
      });
      applySession(data);
      return data;
    },
    [applySession]
  );

  const reloadSession = React.useCallback(async () => {
    const info = await apiFetch<AuthSessionResponse>("/auth/me");
    setUser(info.user);
    setCurrentStudio(info.current_studio);
    setAvailableStudios(info.available_studios || []);
  }, []);

  const logout = React.useCallback(async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST", skipAuthRefresh: true });
    } finally {
      clearState();
    }
  }, [clearState]);

  const cancelStudioSelection = React.useCallback(() => {
    clearState();
  }, [clearState]);

  const value = React.useMemo<AuthContextValue>(
    () => ({
      isBootstrapping,
      isAuthenticated: Boolean(user && !requiresStudioSelection),
      requiresStudioSelection,
      selectionToken,
      user,
      currentStudio,
      availableStudios,
      login,
      selectStudio,
      switchStudio,
      reloadSession,
      logout,
      cancelStudioSelection,
    }),
    [
      isBootstrapping,
      user,
      requiresStudioSelection,
      selectionToken,
      currentStudio,
      availableStudios,
      login,
      selectStudio,
      switchStudio,
      reloadSession,
      logout,
      cancelStudioSelection,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth deve ser utilizado dentro de AuthProvider.");
  }
  return ctx;
}
