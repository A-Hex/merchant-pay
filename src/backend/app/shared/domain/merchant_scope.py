"""Authorized tenant context.

Built ONLY by identity.ResolveScope at the API boundary from the server-side access mapping.
Every repository read takes a MerchantScope as first argument, so a query that forgets
tenant isolation does not type-check. A client-supplied merchant_id is never authorization.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MerchantScope:
    user_id: int
    merchant_id: str
    role: str
