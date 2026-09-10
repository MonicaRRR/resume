import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import type { OptimizationMode, OptimizationRun, OptimizationStatus } from "../types";

const terminalStatuses = new Set<OptimizationStatus>([
  "ready_for_user",
  "failed",
  "cancelled",
  "waiting_for_user",
]);

export function useOptimizationRun(projectId: string) {
  const queryClient = useQueryClient();
  const [runId, setRunId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["optimization-run", projectId, runId],
    queryFn: () => api.getOptimizationRun(projectId, runId!),
    enabled: Boolean(projectId && runId),
    refetchInterval: (current) =>
      terminalStatuses.has((current.state.data?.status ?? "") as OptimizationStatus) ? false : 1000,
  });

  return {
    run: query.data as OptimizationRun | undefined,
    isLoading: query.isLoading || query.isFetching,
    error: query.error,
    start: async (mode: OptimizationMode, provider: string) => {
      const created = await api.createOptimizationRun(projectId, mode, provider);
      setRunId(created.id);
      queryClient.setQueryData(["optimization-run", projectId, created.id], created);
      return created;
    },
    cancel: async () => {
      if (!runId) {
        return undefined;
      }
      const updated = await api.cancelOptimizationRun(projectId, runId);
      queryClient.setQueryData(["optimization-run", projectId, runId], updated);
      return updated;
    },
    resume: async () => {
      if (!runId) {
        return undefined;
      }
      const updated = await api.resumeOptimizationRun(projectId, runId);
      queryClient.setQueryData(["optimization-run", projectId, runId], updated);
      return updated;
    },
  };
}
