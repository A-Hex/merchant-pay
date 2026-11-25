import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Alert, AlertEvaluation, AlertList, AlertState } from "@/api/types";

const ALERTS_KEY = ["alerts"] as const;

export const useAlerts = (state: AlertState) =>
  useQuery({
    queryKey: [...ALERTS_KEY, state],
    queryFn: () => api<AlertList>("/alerts", { query: { state } }),
  });

export const useEvaluateAlerts = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<AlertEvaluation>("/alerts/evaluate", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ALERTS_KEY }),
  });
};

/** One state transition (acknowledge / resolve): the aggregate is the guard, the API returns 409. */
export const useAlertTransition = (action: "acknowledge" | "resolve") => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<Alert>(`/alerts/${id}/${action}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ALERTS_KEY }),
  });
};
