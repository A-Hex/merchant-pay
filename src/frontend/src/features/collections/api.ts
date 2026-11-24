import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { CollectionsSummary } from "@/api/types";

export type CollectionsQuery = { aFrom: string; aTo: string; bFrom: string; bTo: string };

export const useCollections = (p: CollectionsQuery) =>
  useQuery({
    queryKey: ["collections", p],
    queryFn: () => api<CollectionsSummary>("/collections/summary", {
      query: { a_from: p.aFrom, a_to: p.aTo, b_from: p.bFrom, b_to: p.bTo },
    }),
    placeholderData: keepPreviousData,
  });
