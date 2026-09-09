import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";


export function ProviderStatus() {
  const query = useQuery({
    queryKey: ["provider-settings"],
    queryFn: api.getProviderSettings,
    staleTime: 0,
    refetchOnMount: "always",
  });
  const configured = query.data?.configured;
  return (
    <Link className={configured ? "provider-pill connected" : "provider-pill"} to="/settings">
      <span className="status-dot" aria-hidden="true" />
      {query.isLoading ? "检查模型…" : configured ? "模型已连接" : "配置模型"}
    </Link>
  );
}
