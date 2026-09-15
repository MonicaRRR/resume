import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { ProviderStatus } from "./components/ProviderStatus";
import { HomePage } from "./pages/HomePage";
import { PracticePage } from "./pages/PracticePage";
import { ProfilePage } from "./pages/ProfilePage";
import { SettingsPage } from "./pages/SettingsPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { api } from "./api/client";


function AppFrame() {
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const profileNeedsAttention = Boolean(
    profile.data && (!profile.data.ready || profile.data.resume.education.length === 0),
  );
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="简历证据工作台首页">
          <span className="brand-mark" aria-hidden="true">证</span>
          <span>简历证据工作台</span>
        </Link>
        <nav className="topbar-nav" aria-label="主导航">
          <Link className="profile-nav-link" to="/profile">
            经历库
            {profileNeedsAttention && (
              <span className="profile-nav-dot" role="status" aria-label="经历库有待完善内容" title="经历库有待完善内容" />
            )}
          </Link>
          <ProviderStatus />
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/projects/:id" element={<WorkspacePage />} />
        <Route path="/projects/:id/practice" element={<PracticePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </div>
  );
}

export function App() {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 15_000 } } }));
  return <QueryClientProvider client={queryClient}><BrowserRouter><AppFrame /></BrowserRouter></QueryClientProvider>;
}
