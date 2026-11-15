import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

const OverviewPage = lazy(() => import("@/pages/OverviewPage").then((m) => ({ default: m.OverviewPage })));
const ExceptionsPage = lazy(() => import("@/pages/ExceptionsPage").then((m) => ({ default: m.ExceptionsPage })));
const LedgerPage = lazy(() => import("@/pages/LedgerPage").then((m) => ({ default: m.LedgerPage })));
const TaxPage = lazy(() => import("@/pages/TaxPage").then((m) => ({ default: m.TaxPage })));
const ImportPage = lazy(() => import("@/pages/ImportPage").then((m) => ({ default: m.ImportPage })));
const AuditPage = lazy(() => import("@/pages/AuditPage").then((m) => ({ default: m.AuditPage })));
const SettingsPage = lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));

export function App() {
  return (
    <Suspense fallback={<p className="p-6">Loading the desk…</p>}>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/exceptions" element={<ExceptionsPage />} />
        <Route path="/ledger" element={<LedgerPage />} />
        <Route path="/tax" element={<TaxPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/404" element={<NotFoundPage />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Routes>
    </Suspense>
  );
}
