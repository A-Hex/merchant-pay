import { PlaceholderPage } from "@/components/PlaceholderPage";

export const SimulatorPage = () => (
  <PlaceholderPage titleKey="nav.simulator" todo={[
    "Curseur de croissance du volume (défaut +15 %), options taux d'acceptation / panier",
    "POST /simulations/growth : nombre projeté, encaissement projeté, écart vs référence",
    "Panneau d'hypothèses visible + bouton réinitialiser",
  ]} />
);
