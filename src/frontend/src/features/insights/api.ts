import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { DeclineInsight } from "@/api/types";
import type { Filters } from "@/app/filters";

export const useDeclineInsight = (f: Pick<Filters, "dateFrom" | "dateTo">) =>
  useQuery({
    queryKey: ["insights", "decline", f.dateFrom, f.dateTo],
    queryFn: () =>
      api<DeclineInsight>("/insights/decline", {
        query: { date_from: f.dateFrom, date_to: f.dateTo },
      }),
    placeholderData: keepPreviousData,
  });
