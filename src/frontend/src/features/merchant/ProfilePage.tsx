import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { WEEKDAYS, type Merchant, type Weekday } from "@/api/types";
import { Button, Card, ErrorState, Spinner } from "@/components/ui";
import { useMe } from "@/features/auth/api";
import { useUpdateProfile } from "./api";

const inputClass =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 " +
  "disabled:bg-slate-50 disabled:text-slate-500";

function toGoalInput(centimes: number | null | undefined): string {
  return centimes === null || centimes === undefined ? "" : (centimes / 100).toFixed(2);
}

function ProfileForm({ merchant, canEdit }: { merchant: Merchant; canEdit: boolean }) {
  const { t } = useTranslation();
  const update = useUpdateProfile();
  const [displayName, setDisplayName] = useState(merchant.display_name);
  const [category, setCategory] = useState(merchant.category);
  const [days, setDays] = useState<Weekday[]>(
    WEEKDAYS.filter((d) => merchant.operating_days.includes(d)),
  );
  const [goal, setGoal] = useState(toGoalInput(merchant.monthly_goal?.centimes));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const toggleDay = (day: Weekday) =>
    setDays((current) =>
      current.includes(day) ? current.filter((d) => d !== day) : [...current, day],
    );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!displayName.trim()) errors.displayName = t("profile.required");
    if (!category.trim()) errors.category = t("profile.required");
    if (days.length === 0) errors.days = t("profile.at_least_one_day");

    const goalValue = goal.trim() === "" ? null : Math.round(Number(goal) * 100);
    if (goalValue !== null && (!Number.isFinite(goalValue) || goalValue < 0)) {
      errors.goal = t("profile.goal_invalid");
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    update.mutate({
      display_name: displayName.trim(),
      category: category.trim(),
      operating_days: days,
      monthly_goal_centimes: goalValue,
    });
  };

  const forbidden = update.error instanceof ApiError && update.error.status === 403;

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      {!canEdit && (
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800 ring-1 ring-amber-200">
          {t("profile.read_only")}
        </p>
      )}

      <div>
        <label htmlFor="profile-name" className="mb-1 block text-sm font-medium text-slate-700">
          {t("profile.display_name")}
        </label>
        <input
          id="profile-name" className={inputClass} value={displayName} maxLength={200}
          disabled={!canEdit} autoComplete="organization"
          aria-invalid={Boolean(fieldErrors.displayName)}
          aria-describedby="profile-name-error"
          onChange={(e) => setDisplayName(e.target.value)}
        />
        <p id="profile-name-error" role={fieldErrors.displayName ? "alert" : undefined}
          className="mt-1 text-xs text-rose-700">
          {fieldErrors.displayName ?? t("profile.display_name_hint")}
        </p>
      </div>

      <div>
        <label htmlFor="profile-category" className="mb-1 block text-sm font-medium text-slate-700">
          {t("profile.category")}
        </label>
        <input
          id="profile-category" className={inputClass} value={category} maxLength={100}
          disabled={!canEdit}
          aria-invalid={Boolean(fieldErrors.category)}
          aria-describedby="profile-category-error"
          onChange={(e) => setCategory(e.target.value)}
        />
        <p id="profile-category-error" role={fieldErrors.category ? "alert" : undefined}
          className="mt-1 text-xs text-slate-500">
          {fieldErrors.category ?? t("profile.category_hint")}
        </p>
      </div>

      <fieldset disabled={!canEdit}>
        <legend className="mb-1 block text-sm font-medium text-slate-700">
          {t("profile.operating_days")}
        </legend>
        <div className="flex flex-wrap gap-2">
          {WEEKDAYS.map((day) => (
            <label key={day}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm has-checked:border-brand-600 has-checked:bg-brand-50">
              <input type="checkbox" className="accent-brand-700" checked={days.includes(day)}
                onChange={() => toggleDay(day)} />
              {t(`profile.days.${day}`)}
            </label>
          ))}
        </div>
        <p role={fieldErrors.days ? "alert" : undefined} className="mt-1 text-xs text-rose-700">
          {fieldErrors.days ?? t("profile.operating_days_hint")}
        </p>
      </fieldset>

      <div>
        <label htmlFor="profile-goal" className="mb-1 block text-sm font-medium text-slate-700">
          {t("profile.monthly_goal")}
        </label>
        <div className="flex items-center gap-2">
          <input
            id="profile-goal" type="number" inputMode="decimal" min="0" step="0.01"
            className={inputClass} value={goal} disabled={!canEdit}
            placeholder={t("profile.monthly_goal_placeholder")}
            aria-invalid={Boolean(fieldErrors.goal)}
            aria-describedby="profile-goal-error"
            onChange={(e) => setGoal(e.target.value)}
          />
          <span className="text-sm text-slate-500">DZD</span>
        </div>
        <p id="profile-goal-error" role={fieldErrors.goal ? "alert" : undefined}
          className="mt-1 text-xs text-slate-500">
          {fieldErrors.goal ?? t("profile.monthly_goal_hint")}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={!canEdit || update.isPending}>
          {update.isPending ? t("profile.saving") : t("profile.save")}
        </Button>
        <span role="status" aria-live="polite" className="text-sm">
          {update.isSuccess && <span className="text-emerald-700">{t("profile.saved")}</span>}
          {update.isError && (
            <span className="text-rose-700">
              {forbidden ? t("profile.read_only") : t("profile.save_error")}
            </span>
          )}
        </span>
      </div>
    </form>
  );
}

export function ProfilePage() {
  const { t } = useTranslation();
  const me = useMe();

  return (
    <Card title={t("profile.title")}>
      <p className="mb-4 text-sm text-slate-600">{t("profile.intro")}</p>
      {me.isPending ? (
        <Spinner />
      ) : me.isError ? (
        <ErrorState onRetry={() => me.refetch()} />
      ) : (
        <ProfileForm key={me.data.merchant.merchant_id} merchant={me.data.merchant}
          canEdit={me.data.role === "owner"} />
      )}
    </Card>
  );
}
