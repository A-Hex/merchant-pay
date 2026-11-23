from sqlalchemy.orm import Session

from app.contexts.identity.application.ports import PasswordHasher
from app.db.models import MerchantRow, UserMerchantAccessRow, UserRow


def ensure_merchant(s: Session, merchant_id: str, display_name: str, category: str,
                    monthly_goal_centimes: int | None = None) -> None:
    row = s.get(MerchantRow, merchant_id)
    if row is None:
        s.add(MerchantRow(merchant_id=merchant_id, display_name=display_name, category=category,
                          monthly_goal_centimes=monthly_goal_centimes))
    else:
        row.display_name, row.category = display_name, category
        row.monthly_goal_centimes = monthly_goal_centimes
    s.flush()


def ensure_user(s: Session, hasher: PasswordHasher, email: str, password: str,
                merchant_id: str, role: str = "owner") -> None:
    user = s.query(UserRow).filter_by(email=email).one_or_none()
    if user is None:
        user = UserRow(email=email, password_hash=hasher.hash(password), status="active")
        s.add(user)
        s.flush()
    if s.get(UserMerchantAccessRow, (user.id, merchant_id)) is None:
        s.add(UserMerchantAccessRow(user_id=user.id, merchant_id=merchant_id, role=role))
    s.flush()
