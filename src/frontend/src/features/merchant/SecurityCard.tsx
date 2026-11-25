import { useQuery } from "@tanstack/react-query";
import { CircleCheckIcon, CircleXIcon, LockIcon, LogOutIcon, ShieldAlertIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { api } from "@/api/client";
import type { LoginHistory } from "@/api/types";
import { motion, rowVariants, Stagger } from "@/components/motion";
import { Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

const ICON: Record<LoginHistory["events"][number]["outcome"], ReactNode> = {
  success: <CircleCheckIcon className="size-4 text-emerald-600 dark:text-emerald-400" />,
  failure: <CircleXIcon className="size-4 text-destructive" />,
  throttled: <LockIcon className="size-4 text-amber-600 dark:text-amber-400" />,
  logout: <LogOutIcon className="size-4 text-muted-foreground" />,
};

/** Settings → account security: the signed-in user's own sign-in history (server-recorded). */
export function SecurityCard() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["auth", "history"], queryFn: () => api<LoginHistory>("/auth/history", { query: { limit: 15 } }) });
  return (
    <Card title={t("security.title")}>
      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> : (
        <div className="space-y-3">
          {q.data.failures_last_30_days > 0 && (
            <p role="status" className="flex items-start gap-2 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-400">
              <ShieldAlertIcon className="mt-0.5 size-4 shrink-0" />
              {t("security.failures", { n: q.data.failures_last_30_days })}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            {q.data.previous_success
              ? t("security.previous", { date: formatDateTime(q.data.previous_success) })
              : t("security.noPrevious")}
          </p>
          {q.data.events.length === 0 ? <EmptyState>{t("security.empty")}</EmptyState> : (
            <Stagger className="divide-y rounded-lg border">
              {q.data.events.map((e, i) => (
                <motion.div key={`${e.occurred_at}-${i}`} variants={rowVariants}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
                  {ICON[e.outcome]}
                  <span className="font-medium">{t(`security.outcome.${e.outcome}`)}</span>
                  <span className="text-muted-foreground">{formatDateTime(e.occurred_at)}</span>
                  <span className="ms-auto text-xs text-muted-foreground">
                    {e.device === "unknown" ? t("security.unknownDevice") : e.device} · <span className="font-mono">{e.ip}</span>
                  </span>
                </motion.div>
              ))}
            </Stagger>
          )}
          <p className="text-xs text-muted-foreground">{t("security.note", { days: q.data.retention_days })}</p>
        </div>
      )}
    </Card>
  );
}
