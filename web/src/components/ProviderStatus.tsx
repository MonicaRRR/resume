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
  const label = query.data?.kind === "rules"
    ? "规则分析（非生成式 AI）"
    : configured
      ? "生成式 AI 已连接"
      : "配置分析方式";
  return (
    <Link className={configured ? "provider-pill connected" : "provider-pill"} to="/settings">
      <span className="status-dot" aria-hidden="true" />
      {query.isLoading ? "检查分析方式…" : label}
    </Link>
  );
}
