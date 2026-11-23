import { useTranslation } from "react-i18next";
import type { TransactionStatus } from "@/api/types";
import { Badge } from "./ui";

// Strong colour is reserved for actionable alerts; statuses stay calm (blueprint §11 UX rules).
const TONE = { accepted: "success", declined: "neutral", cancelled: "neutral", refunded: "info" } as const;

export function StatusBadge({ status }: { status: TransactionStatus }) {
  const { t } = useTranslation();
  return <Badge tone={TONE[status]}>{t(`status.${status}`)}</Badge>;
}
