import { useTranslation } from "react-i18next";
import type { Severity } from "@/api/types";
import { Badge } from "@/components/ui";

// Strong colour is reserved for alerts (blueprint §11 UX rules); statuses stay calm.
const TONE = { critical: "danger", warning: "warning", info: "info" } as const;

export function SeverityBadge({ severity }: { severity: Severity }) {
  const { t } = useTranslation();
  return <Badge tone={TONE[severity]}>{t(`alerts.severity.${severity}`)}</Badge>;
}
