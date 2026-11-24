/** Friendly aliases over the generated OpenAPI types. Regenerate with `make gen-api`. */
import type { components } from "./schema";

type S = components["schemas"];
export type Me = S["MeOut"];
export type Merchant = S["MerchantOut"];
export type MerchantUpdate = S["MerchantUpdateIn"];
export type DeclineInsight = S["DeclineInsightOut"];
export type DeclineSignal = S["DeclineSignalOut"];
export type Period = S["PeriodOut"];
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
export type Alert = S["AlertOut"];
export type AlertList = S["AlertPageOut"];
export type AlertEvaluation = S["EvaluationOut"];
export type AlertState = S["AlertState"];
export type Severity = S["Severity"];
export type Simulation = S["SimulationOut"];
export type CollectionsSummary = S["CollectionsSummaryOut"];

export const CHANNELS: Channel[] = ["pos", "ecommerce", "mobile_app", "contactless", "bank_transfer"];
export const STATUSES: TransactionStatus[] = ["accepted", "declined", "cancelled", "refunded"];
export const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type Weekday = (typeof WEEKDAYS)[number];
