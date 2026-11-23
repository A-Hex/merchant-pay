import { useTranslation } from "react-i18next";
import { Card } from "./ui";

/** Temporary page for modules still on the team plan. Replace, don't ship to the jury. */
export function PlaceholderPage({ titleKey, todo }: { titleKey: string; todo: string[] }) {
  const { t } = useTranslation();
  return (
    <Card title={t(titleKey)}>
      <p className="mb-2 text-sm font-medium text-amber-700">{t("common.todo")}</p>
      <p className="mb-3 text-sm text-slate-500">{t("common.todoBody")}</p>
      <ul className="list-disc space-y-1 ps-5 text-sm text-slate-600">{todo.map((x) => <li key={x}>{x}</li>)}</ul>
    </Card>
  );
}
