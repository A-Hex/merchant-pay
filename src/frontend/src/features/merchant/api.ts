import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Merchant, MerchantUpdate } from "@/api/types";

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MerchantUpdate) =>
      api<Merchant>("/merchant/me", { method: "PATCH", body: JSON.stringify(body) }),
    // The server response is the refreshed merchant: write it straight into the cache,
    // then invalidate so `MeOut` (role, accessible merchants) is refetched too.
    onSuccess: (merchant) => {
      qc.setQueryData(["me"], (old: { merchant: Merchant } | undefined) =>
        old ? { ...old, merchant } : old,
      );
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}
