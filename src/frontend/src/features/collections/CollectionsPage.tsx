import { PlaceholderPage } from "@/components/PlaceholderPage";

export const CollectionsPage = () => (
  <PlaceholderPage titleKey="nav.collections" todo={[
    "GET /collections/summary : totaux par statut, période A vs B",
    "Accepté / refusé / annulé / remboursé toujours séparés",
    "Export CSV (protégé contre l'injection de formules)",
  ]} />
);
