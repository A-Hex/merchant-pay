import { useTranslation } from "react-i18next";
import { useFilters } from "@/app/filters";
import { Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatNumber, formatPct } from "@/lib/format";
import { useDeclineInsight } from "./api";

function Stat({ label, value, footnote }: { label: string; value: string; footnote?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {footnote && <p className="mt-1 text-xs text-slate-500">{footnote}</p>}
    </div>
  );
}

export function InsightsPage() {
  const { t } = useTranslation();
  const filters = useFilters();
  const query = useDeclineInsight(filters);

  if (query.isPending) return <Spinner />;
  if (query.isError) return <ErrorState onRetry={() => query.refetch()} />;

  const { period, signal } = query.data;
  const lower = signal.credible_interval.lower;
  const upper = signal.credible_interval.upper;
  const mean = signal.posterior_mean;
  const hasBand = lower !== null && upper !== null && mean !== null;

  return (
    <div className="space-y-4">
      <Card title={t("insights.title")}>
        <p className="text-sm text-slate-600">{t("insights.intro")}</p>
        <p className="mt-1 text-xs text-slate-500">
          {t("insights.period", {
            from: formatDate(period.date_from),
            to: formatDate(period.date_to),
          })}
        </p>
      </Card>

      {signal.attempts === 0 ? (
        <EmptyState>{t("insights.empty")}</EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label={t("insights.posterior")} value={formatPct(mean)}
              footnote={t("insights.posterior_hint")} />
            <Stat label={t("insights.observed")} value={formatPct(signal.observed_rate.value)}
              footnote={t("insights.observed_hint", {
                declined: formatNumber(signal.declined),
                accepted: formatNumber(signal.accepted),
              })} />
            <Stat label={t("insights.attempts")} value={formatNumber(signal.attempts)}
              footnote={t("insights.attempts_hint")} />
            <Stat label={t("insights.interval")}
              value={
                hasBand
                  ? t("insights.interval_value", { lower: formatPct(lower), upper: formatPct(upper) })
                  : "—"
              }
              footnote={t("insights.interval_hint", {
                level: Math.round(signal.credible_interval.level * 100),
              })} />
          </div>

          {hasBand && (
            <Card>
              <div className="relative h-3 rounded-full bg-slate-100" aria-hidden="true">
                <div className="absolute inset-y-0 rounded-full bg-brand-100"
                  style={{ insetInlineStart: `${lower * 100}%`, width: `${(upper - lower) * 100}%` }} />
                <div className="absolute -top-1 h-5 w-0.5 bg-brand-700"
                  style={{ insetInlineStart: `calc(${mean * 100}% - 1px)` }} />
              </div>
              <p className="mt-2 text-xs text-slate-500">{t("insights.band_legend")}</p>
            </Card>
          )}

          {!signal.sample_gate_met && (
            <p role="status"
              className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800 ring-1 ring-amber-200">
              {t("insights.insufficient_data", {
                attempts: formatNumber(signal.attempts),
                min: formatNumber(signal.min_attempts),
              })}
            </p>
          )}

          <Card title={t("insights.method")}>
            <p className="text-sm text-slate-600">{t("insights.method_body")}</p>
            <p className="mt-2 text-sm text-slate-600">{t("insights.limitations_body")}</p>
            <details className="mt-3 rounded-lg bg-slate-50 p-2 text-xs text-slate-600">
              <summary className="cursor-pointer font-medium">{t("insights.technical")}</summary>
              <p className="mt-1">
                {t("insights.technical_body", {
                  alpha: signal.prior.alpha,
                  beta: signal.prior.beta,
                  family: signal.prior.family,
                })}
              </p>
              <p className="mt-1 font-mono text-[11px] text-slate-500">{signal.method}</p>
            </details>
          </Card>
        </>
      )}
    </div>
  );
}
