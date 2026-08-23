import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { ProviderStatus } from "./components/ProviderStatus";
import { HomePage } from "./pages/HomePage";
import { PracticePage } from "./pages/PracticePage";
import { SettingsPage } from "./pages/SettingsPage";
import { WorkspacePage } from "./pages/WorkspacePage";


const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 15_000 } } });

function AppFrame() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="简历证据工作台首页">
          <span className="brand-mark" aria-hidden="true">证</span>
          <span>简历证据工作台</span>
        </Link>
        <ProviderStatus />
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/projects/:id" element={<WorkspacePage />} />
        <Route path="/projects/:id/practice" element={<PracticePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </div>
  );
}

export function App() {
  return <QueryClientProvider client={queryClient}><BrowserRouter><AppFrame /></BrowserRouter></QueryClientProvider>;
}
