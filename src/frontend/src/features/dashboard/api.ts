import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Dashboard } from "@/api/types";
import type { Filters } from "@/app/filters";

export const useDashboard = (f: Filters) =>
  useQuery({
    queryKey: ["dashboard", f],
    queryFn: () => api<Dashboard>("/analytics/dashboard", {
      query: { date_from: f.dateFrom, date_to: f.dateTo, granularity: f.granularity },
    }),
    placeholderData: keepPreviousData,
  });
