"""Shared enumerations with tolerant parsing of source values (EN/FR aliases)."""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


def normalize_token(raw: str) -> str:
    """'Contactless / NFC' -> 'contactlessnfc', 'Accepté' -> 'accepte'."""
    ascii_text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


class TransactionStatus(StrEnum):
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

    @property
    def is_collected(self) -> bool:
        """Only Accepted (approved & settled) counts as collected money."""
        return self is TransactionStatus.ACCEPTED

    @property
    def is_authorization_decision(self) -> bool:
        """Denominator population for acceptance / decline rates."""
        return self in (TransactionStatus.ACCEPTED, TransactionStatus.DECLINED)

    @classmethod
    def parse(cls, raw: str) -> TransactionStatus:
        key = normalize_token(raw)
        if key in _STATUS_ALIASES:
            return _STATUS_ALIASES[key]
        raise ValueError(f"Unknown status '{raw}'")


_STATUS_ALIASES = {
    "accepted": TransactionStatus.ACCEPTED, "accepte": TransactionStatus.ACCEPTED,
    "approved": TransactionStatus.ACCEPTED, "success": TransactionStatus.ACCEPTED,
    "declined": TransactionStatus.DECLINED, "refuse": TransactionStatus.DECLINED,
    "rejected": TransactionStatus.DECLINED, "rejete": TransactionStatus.DECLINED,
    "cancelled": TransactionStatus.CANCELLED, "canceled": TransactionStatus.CANCELLED,
    "annule": TransactionStatus.CANCELLED,
    "refunded": TransactionStatus.REFUNDED, "rembourse": TransactionStatus.REFUNDED,
}


class Channel(StrEnum):
    POS = "pos"
    ECOMMERCE = "ecommerce"
    MOBILE_APP = "mobile_app"
    CONTACTLESS = "contactless"
    BANK_TRANSFER = "bank_transfer"

    @classmethod
    def parse(cls, raw: str) -> Channel:
        key = normalize_token(raw)
        if key in _CHANNEL_ALIASES:
            return _CHANNEL_ALIASES[key]
        raise ValueError(f"Unknown channel '{raw}'")


_CHANNEL_ALIASES = {
    "pos": Channel.POS, "tpe": Channel.POS, "tpepos": Channel.POS, "postpe": Channel.POS,
    "ecommerce": Channel.ECOMMERCE, "online": Channel.ECOMMERCE, "web": Channel.ECOMMERCE,
    "mobileapp": Channel.MOBILE_APP, "mobile": Channel.MOBILE_APP, "app": Channel.MOBILE_APP,
    "contactless": Channel.CONTACTLESS, "nfc": Channel.CONTACTLESS,
    "contactlessnfc": Channel.CONTACTLESS, "sanscontact": Channel.CONTACTLESS,
    "banktransfer": Channel.BANK_TRANSFER, "transfer": Channel.BANK_TRANSFER,
    "virement": Channel.BANK_TRANSFER, "virementbancaire": Channel.BANK_TRANSFER,
}


class DataOrigin(StrEnum):
    CHALLENGE_SOURCE = "challenge_source"
    SYNTHETIC_DEMO = "synthetic_demo"
