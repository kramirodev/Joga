import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { LoadingBlock } from "./components/Feedback";
import { AuthProvider } from "./lib/auth";
import { useAuth } from "./lib/auth-context";
import { queryClient } from "./lib/query";
import { LoginPage } from "./pages/LoginPage";
import { OrganizationPage } from "./pages/OrganizationPage";
import { OrganizationsPage } from "./pages/OrganizationsPage";
import { VenuePage } from "./pages/VenuePage";

function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="app-shell">
        <main className="page">
          <LoadingBlock label="Verificando sessão..." />
        </main>
      </div>
    );
  }

  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<OrganizationsPage />} />
              <Route path="/organizations/:organizationId" element={<OrganizationPage />} />
              <Route
                path="/organizations/:organizationId/venues/:venueId"
                element={<VenuePage />}
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
