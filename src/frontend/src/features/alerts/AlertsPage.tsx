import { PlaceholderPage } from "@/components/PlaceholderPage";

export const AlertsPage = () => (
  <PlaceholderPage titleKey="nav.alerts" todo={[
    "GET /alerts : liste ouvertes / acquittées / résolues",
    "Détail : métrique, fenêtres, seuil, valeur observée, référence, lien vers le registre",
    "Actions : acquitter, résoudre (POST /alerts/{id}/acknowledge|resolve)",
  ]} />
);
