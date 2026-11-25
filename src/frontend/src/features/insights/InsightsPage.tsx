import { useState, useEffect } from "react";
import { api } from "@/api/client";
import { useTranslation } from "react-i18next";

export const InsightsPage = () => {
  const { t } = useTranslation();
  const [data, setData] = useState<{ declineRate: number; confidence: number; sampleSize: number } | null>(null);
  const [_loading, _setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    api("/insights/decline", { method: "GET" }).then((res: unknown) => {
        if (!cancelled) {
          setData({
            declineRate: (res as { value: number }).value ?? 0,
            confidence: 0.95,
            sampleSize: (res as { denominator: number }).denominator ?? 0,
          });
        }
      })
.catch((_e: unknown) => {
        if (!cancelled) {
          setError(t("insights.error"));
        }
      })
;
    return () => { cancelled = true; };
  }, []);

  if (_loading) {
    return <p>{t("common.loading")}</p>;
  }

  if (error) {
    return <p className="text-destructive">{error}</p>;
  }

  if (!data) {
    return <p>{t("insights.empty")}</p>;
  }

  const { declineRate, sampleSize } = data;
  const denominator = sampleSize;
  const confidenceLevel = 0.95;
  const z = 1.96;
  const p = declineRate / (denominator > 0 ? denominator : 1);
  const se = Math.sqrt((p * (1 - p)) / denominator);
  const margin = z * se;
  const lower = Math.max(0, p - margin);
  const upper = Math.min(1, p + margin);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">{t("insights.title")}</h2>
      <p className="text-muted-foreground">{t("insights.intro")}</p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="p-4 rounded border">{t("insights.confidence", { value: (confidenceLevel * 100).toFixed(0) })}</div>
        <div className="p-4 rounded border">{t("insights.sample_size", { value: sampleSize })}</div>
      </div>
      <div className="mt-4">
        <p>{t("insights.decline_rate", { value: (declineRate * 100).toFixed(1) })}</p>
        <p>{t("insights.confidence_interval", { value: (lower * 100).toFixed(1), value2: (upper * 100).toFixed(1) })}</p>
        {sampleSize < 30 && (
          <p className="text-sm text-destructive">{t("insights.insufficient_data")}</p>
        )}
      </div>
    </div>
  );
};
