import { useQuery } from "@tanstack/react-query";
import { DownloadIcon, FileTextIcon, LoaderCircleIcon, MessageCircleIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "@/api/client";
import type { CollectionsReport } from "@/api/types";
import { useFilters } from "@/app/filters";
import { AnimatePresence, motion } from "@/components/motion";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge, Card, ErrorState, Spinner } from "@/components/ui";
import { Button } from "@/components/ui/button";
import { formatDate, formatDateTime, formatMoney, formatNumber, formatPct } from "@/lib/format";

type Format = "pdf" | "csv";
type ShareState = "idle" | "working" | "sheet" | "cancelled" | "fallback" | "downloaded" | "error";

/** Fetch the server-generated file (cookie auth, merchant scope decided by the server). */
async function fetchReport(format: Format, from: string, to: string, filename: string): Promise<File> {
  const url = `/api/v1/reports/collections-summary.${format}?date_from=${from}&date_to=${to}`;
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) throw new Error(`report ${res.status}`);
  const blob = await res.blob();
  return new File([blob], filename, { type: format === "pdf" ? "application/pdf" : "text/csv" });
}

function download(file: File) {
  const href = URL.createObjectURL(file);
  const a = Object.assign(document.createElement("a"), { href, download: file.name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

/**
 * Settings → Reports & sharing. Aggregated Collections Summary only. Sharing hands the file to the
 * device (Web Share) or to the merchant (download + WhatsApp with a generic text): the merchant picks
 * the recipient and confirms the send inside WhatsApp. Nothing here claims delivery.
 */
export function ReportsCard() {
  const { t } = useTranslation();
  const { dateFrom, dateTo } = useFilters();
  const [format, setFormat] = useState<Format>("pdf");
  const [state, setState] = useState<ShareState>("idle");
  const preview = useQuery({
    queryKey: ["reports", "collections", dateFrom, dateTo],
    queryFn: () => api<CollectionsReport>("/reports/collections-summary", { query: { date_from: dateFrom, date_to: dateTo } }),
  });
  const filename = preview.data ? (format === "pdf" ? preview.data.pdf_filename : preview.data.csv_filename) : "";

  const onDownload = async () => {
    setState("working");
    try {
      download(await fetchReport(format, dateFrom, dateTo, filename));
      setState("downloaded");
    } catch {
      setState("error");
    }
  };

  const onShare = async () => {
    setState("working");
    let file: File;
    try {
      file = await fetchReport(format, dateFrom, dateTo, filename);
    } catch {
      setState("error");
      return;
    }
    const data = { files: [file], title: t("reports.shareTitle"), text: t("reports.shareText") };
    if (typeof navigator.canShare === "function" && navigator.canShare(data)) {
      try {
        await navigator.share(data);
        setState("sheet");  // the share sheet completed; WhatsApp itself confirms the actual send
      } catch (e) {
        setState(e instanceof DOMException && e.name === "AbortError" ? "cancelled" : "error");
      }
      return;
    }
    // Fallback: download the file, open WhatsApp with a GENERIC text (no figures, no links to data)
    download(file);
    window.open(`https://wa.me/?text=${encodeURIComponent(t("reports.shareText"))}`, "_blank", "noopener,noreferrer");
    setState("fallback");
  };

  return (
    <Card title={t("reports.title")}>
      <p className="mb-4 text-sm text-muted-foreground">{t("reports.intro")}</p>
      {preview.isPending ? <Spinner /> : preview.isError ? <ErrorState onRetry={() => preview.refetch()} /> : (
        <div className="space-y-4">
          <div className="rounded-xl border bg-muted/40 p-4" aria-label={t("reports.preview")}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <FileTextIcon className="size-4 text-muted-foreground" />
                <span className="text-sm font-medium">{t("reports.collectionsSummary")}</span>
              </div>
              {preview.data.synthetic
                ? <Badge tone="warning">{t("reports.synthetic")}</Badge>
                : <Badge tone="neutral">{t("reports.source")}</Badge>}
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
              <Meta label={t("reports.merchant")} value={preview.data.merchant_name} />
              <Meta label={t("reports.period")}
                value={`${formatDate(preview.data.period.date_from)} – ${formatDate(preview.data.period.date_to)}`} />
              <Meta label={t("reports.generated")} value={formatDateTime(preview.data.generated_at)} />
              <Meta label={t("reports.currency")} value={preview.data.currency} />
            </dl>
            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
              <Meta label={t("kpi.collected")} value={formatMoney(preview.data.gross_collected)} strong />
              <Meta label={t("kpi.acceptanceRate")} value={`${formatPct(preview.data.acceptance_rate.value)} (${preview.data.acceptance_rate.numerator}/${preview.data.acceptance_rate.denominator})`} strong />
              <Meta label={t("kpi.avgTicket")} value={formatMoney(preview.data.average_ticket)} strong />
            </dl>
            <ul className="mt-3 flex flex-wrap gap-3 text-xs">
              {preview.data.statuses.map((s) => (
                <li key={s.status} className="flex items-center gap-1.5">
                  <StatusBadge status={s.status} />{formatNumber(s.count)} · {formatMoney(s.amount)}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted-foreground">{t("reports.aggregatedNote")}</p>
          </div>

          <fieldset className="flex flex-wrap items-center gap-3 text-sm">
            <legend className="sr-only">{t("reports.format")}</legend>
            <span className="text-muted-foreground">{t("reports.format")}</span>
            {(["pdf", "csv"] as const).map((f) => (
              <label key={f} className="flex items-center gap-1.5">
                <input type="radio" name="report-format" value={f} checked={format === f} onChange={() => setFormat(f)} />
                {t(`reports.fmt.${f}`)}
              </label>
            ))}
          </fieldset>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={onDownload} disabled={state === "working"}>
              {state === "working" ? <LoaderCircleIcon className="animate-spin" /> : <DownloadIcon />}{t("reports.download")}
            </Button>
            <Button onClick={onShare} disabled={state === "working"}>
              <MessageCircleIcon />{t("reports.shareWhatsApp")}
            </Button>
          </div>
          <AnimatePresence mode="wait">
            {state !== "idle" && state !== "working" && (
              <motion.p key={state} role={state === "error" ? "alert" : "status"} initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
                className={state === "error" ? "text-sm text-destructive" : "text-sm text-muted-foreground"}>
                {t(`reports.state.${state}`, { file: filename })}
              </motion.p>
            )}
          </AnimatePresence>
          <p className="text-xs text-muted-foreground">{t("reports.privacy")}</p>
        </div>
      )}
    </Card>
  );
}

function Meta({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={strong ? "font-semibold tabular-nums" : "tabular-nums"}>{value}</dd>
    </div>
  );
}
