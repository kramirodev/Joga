import { lazy, Suspense } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { AdminRoute } from "./components/AdminRoute";
import { AppShell } from "./components/AppShell";
import { ModerationRoute } from "./components/ModerationRoute";
import { LoadingBlock } from "./components/Feedback";
import { ToastProvider } from "./components/ui/Toast";
import { AuthProvider } from "./lib/auth";
import { useAuth } from "./lib/auth-context";
import { queryClient } from "./lib/query";
import { LoginPage } from "./pages/LoginPage";
import { OrganizationsPage } from "./pages/OrganizationsPage";

const ModerationPage = lazy(() =>
  import("./pages/ModerationPage").then((module) => ({ default: module.ModerationPage })),
);
const OrganizationPage = lazy(() =>
  import("./pages/OrganizationPage").then((module) => ({ default: module.OrganizationPage })),
);
const VenuePage = lazy(() =>
  import("./pages/VenuePage").then((module) => ({ default: module.VenuePage })),
);
const AdminUsersPage = lazy(() =>
  import("./pages/admin/AdminUsersPage").then((module) => ({ default: module.AdminUsersPage })),
);
const AdminSportsPage = lazy(() =>
  import("./pages/admin/AdminSportsPage").then((module) => ({ default: module.AdminSportsPage })),
);
const AdminVenuesPage = lazy(() =>
  import("./pages/admin/AdminVenuesPage").then((module) => ({
    default: module.AdminVenuesPage,
  })),
);
const AdminVenueDetailPage = lazy(() =>
  import("./pages/admin/AdminVenueDetailPage").then((module) => ({
    default: module.AdminVenueDetailPage,
  })),
);
const AdminObservabilityPage = lazy(() =>
  import("./pages/admin/AdminObservabilityPage").then((module) => ({
    default: module.AdminObservabilityPage,
  })),
);
const AdminObservabilityEventsPage = lazy(() =>
  import("./pages/admin/AdminObservabilityEventsPage").then((module) => ({
    default: module.AdminObservabilityEventsPage,
  })),
);
const AdminObservabilityEventPage = lazy(() =>
  import("./pages/admin/AdminObservabilityEventPage").then((module) => ({
    default: module.AdminObservabilityEventPage,
  })),
);
const AdminObservabilityUserPage = lazy(() =>
  import("./pages/admin/AdminObservabilityUserPage").then((module) => ({
    default: module.AdminObservabilityUserPage,
  })),
);
const AdminObservabilityIpPage = lazy(() =>
  import("./pages/admin/AdminObservabilityIpPage").then((module) => ({
    default: module.AdminObservabilityIpPage,
  })),
);

function ProtectedRoute() {
  const { user, loading, sessionExpired } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="app-shell">
        <main className="page">
          <LoadingBlock label="Verificando sessão..." />
        </main>
      </div>
    );
  }

  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: `${location.pathname}${location.search}${location.hash}`,
          expired: sessionExpired,
        }}
      />
    );
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <ToastProvider>
            <Suspense
              fallback={
                <div className="app-shell">
                  <main className="page">
                    <LoadingBlock label="Carregando painel..." />
                  </main>
                </div>
              }
            >
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route element={<ProtectedRoute />}>
                  <Route path="/" element={<OrganizationsPage />} />
                  <Route element={<ModerationRoute />}>
                    <Route path="/moderation" element={<ModerationPage />} />
                  </Route>
                  <Route path="/organizations/:organizationId" element={<OrganizationPage />} />
                  <Route
                    path="/organizations/:organizationId/venues/:venueId"
                    element={<VenuePage />}
                  />
                  <Route element={<AdminRoute />}>
                    <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
                    <Route path="/admin/users" element={<AdminUsersPage />} />
                    <Route path="/admin/sports" element={<AdminSportsPage />} />
                    <Route path="/admin/venues" element={<AdminVenuesPage />} />
                    <Route path="/admin/venues/:venueId" element={<AdminVenueDetailPage />} />
                    <Route path="/admin/observability" element={<AdminObservabilityPage />} />
                    <Route
                      path="/admin/observability/events"
                      element={<AdminObservabilityEventsPage />}
                    />
                    <Route
                      path="/admin/observability/events/:eventId"
                      element={<AdminObservabilityEventPage />}
                    />
                    <Route
                      path="/admin/observability/users/:userId"
                      element={<AdminObservabilityUserPage />}
                    />
                    <Route
                      path="/admin/observability/ips/:ip"
                      element={<AdminObservabilityIpPage />}
                    />
                  </Route>
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
