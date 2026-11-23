/** Friendly aliases over the generated OpenAPI types. Regenerate with `make gen-api`. */
import type { components } from "./schema";

type S = components["schemas"];
export type Me = S["MeOut"];
export type Dashboard = S["DashboardOut"];
export type Kpis = S["KpiOut"];
export type Change = S["ChangeOut"];
export type Transaction = S["TransactionOut"];
export type TransactionPage = S["TransactionPageOut"];
export type Money = S["MoneyOut"];
export type Rate = S["RateOut"];
export type Channel = S["Channel"];
export type TransactionStatus = S["TransactionStatus"];
export type Granularity = S["Granularity"];

export const CHANNELS: Channel[] = ["pos", "ecommerce", "mobile_app", "contactless", "bank_transfer"];
export const STATUSES: TransactionStatus[] = ["accepted", "declined", "cancelled", "refunded"];
