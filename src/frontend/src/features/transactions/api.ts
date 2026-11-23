import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Channel, Transaction, TransactionPage, TransactionStatus } from "@/api/types";

export type LedgerQuery = {
  dateFrom: string; dateTo: string; status: TransactionStatus[]; channel: Channel[]; q: string; page: number;
};
export const PAGE_SIZE = 25;

export const useTransactions = (p: LedgerQuery) =>
  useQuery({
    queryKey: ["transactions", p],
    queryFn: () => api<TransactionPage>("/transactions", {
      query: { date_from: p.dateFrom, date_to: p.dateTo, status: p.status, channel: p.channel,
               q: p.q, page: p.page, size: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  });

export const useTransaction = (id: string | null) =>
  useQuery({
    queryKey: ["transaction", id],
    queryFn: () => api<Transaction>(`/transactions/${encodeURIComponent(id!)}`),
    enabled: !!id,
  });
