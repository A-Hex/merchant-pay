import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ar from "./ar.json";
import fr from "./fr.json";

export type Lang = "fr" | "ar";
const STORAGE_KEY = "mp.lang";

function applyDirection(lng: string) {
  document.documentElement.lang = lng;
  document.documentElement.dir = lng === "ar" ? "rtl" : "ltr";
}

const initial = (localStorage.getItem(STORAGE_KEY) as Lang | null) ?? "fr";

i18n.use(initReactI18next).init({
  resources: { fr: { translation: fr }, ar: { translation: ar } },
  lng: initial,
  fallbackLng: "fr",
  interpolation: { escapeValue: false },
});
applyDirection(initial);
i18n.on("languageChanged", (lng) => {
  localStorage.setItem(STORAGE_KEY, lng);
  applyDirection(lng);
});

export const isRtl = () => i18n.language === "ar";
export default i18n;
