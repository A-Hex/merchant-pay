import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { ApiError } from "@/api/client";
import { ErrorState, Spinner } from "@/components/ui";
import { useMe } from "@/features/auth/api";

export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return <Spinner />;
  if (me.error instanceof ApiError && (me.error.status === 401 || me.error.status === 403))
    return <Navigate to="/login" replace />;
  if (me.isError) return <ErrorState onRetry={() => me.refetch()} />;
  return <>{children}</>;
}
