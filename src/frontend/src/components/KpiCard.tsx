import clsx from "clsx";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { Change } from "@/api/types";
import { formatPct } from "@/lib/format";

export function KpiCard({ label, value, change, footnote, help }: {
  label: string; value: ReactNode; change?: Change; footnote?: ReactNode; help?: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" title={help}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {change && (
        <p className="mt-1 text-xs text-slate-500">
          {change.kind === "comparable" ? (
            <span className={clsx("font-medium", (change.pct ?? 0) < 0 ? "text-rose-600" : "text-emerald-600")}>
              {formatPct(change.pct, true)}
            </span>
          ) : (
            <span className="font-medium">{t(change.kind === "new_activity" ? "kpi.newActivity" : "kpi.noActivity")}</span>
          )}{" "}
          {t("kpi.vsPrevious")}
        </p>
      )}
      {footnote && <p className="mt-1 text-xs text-slate-500">{footnote}</p>}
    </div>
  );
}
