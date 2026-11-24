import { useState, useRef } from "react";
import { api } from "@/api/client";
import { useTranslation } from "react-i18next";

export const ProfilePage = () => {
  const { t } = useTranslation();
  const [name, setName] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [operatingDays, setOperatingDays] = useState<string>("sun,mon,tue,wed,thu,sat");
  const [monthlyGoal, setMonthlyGoal] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const submitRef = useRef<HTMLFormElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api("/merchant/me", {
        method: "PATCH",
        body: JSON.stringify({
          display_name: name,
          category,
          operating_days: operatingDays.split(",").filter(Boolean),
          monthly_goal_centimes: monthlyGoal ? Math.round(monthlyGoal * 100) : null,
        }),
      } as RequestInit);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form ref={submitRef} onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-1">{t("nav.profile")}</label>
        <input
          type="text"
          value={name || ""}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("profile.display_name")}
          className="w-full rounded border px-3 py-2 focus:outline-none focus:border-primary"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">{t("profile.category")}</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full rounded border px-3 py-2 focus:outline-none focus:border-primary"
          >
            <option value="ecommerce">{t("profile.category.ecommerce")}</option>
            <option value="mobile_app">{t("profile.category.mobile_app")}</option>
            <option value="pos">{t("profile.category.pos")}</option>
            <option value="bank_transfer">{t("profile.category.bank_transfer")}</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">{t("profile.operating_days")}</label>
          <select
            value={operatingDays}
            onChange={(e) => setOperatingDays(e.target.value)}
            className="w-full rounded border px-3 py-2 focus:outline-none focus:border-primary"
          >
            <option value="sun,mon,tue,wed,thu,sat">{t("profile.operating_days.all")}</option>
            <option value="mon-fri">{t("profile.operating_days.weekdays")}</option>
            <option value="tue,thu,sat">{t("profile.operating_days.partial")}</option>
          </select>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">{t("profile.monthly_goal")}</label>
        <input
          type="number"
          value={monthlyGoal ?? ""}
          onChange={(e) => setMonthlyGoal(parseFloat(e.target.value) || null)}
          placeholder={t("profile.monthly_goal_placeholder")}
          className="w-full rounded border px-3 py-2 focus:outline-none focus:border-primary"
        />
      </div>
      <button
        type="submit"
        disabled={saving}
        className="w-full rounded border px-3 py-2 focus:outline-none focus:border-primary bg-primary text-primary-foreground disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {saving ? "Enregistrement…" : t("profile.save")}
      </button>
    </form>
  );
};