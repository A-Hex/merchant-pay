import { PlaceholderPage } from "@/components/PlaceholderPage";

export const ProfilePage = () => (
  <PlaceholderPage titleKey="nav.profile" todo={[
    "Afficher les infos de GET /merchant/me",
    "Modifier nom, catégorie, jours d'ouverture, objectif mensuel (PATCH /merchant/me)",
  ]} />
);
