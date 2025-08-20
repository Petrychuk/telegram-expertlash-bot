from datetime import datetime, timedelta
from database import SessionLocal, create_tables, create_user, get_user_by_telegram_id, Subscription

db = SessionLocal()
create_tables()

def ensure_user(tg_id, uname):
    u = get_user_by_telegram_id(db, tg_id)
    if not u:
        u = create_user(db, tg_id, uname, "Test", "User")
    return u

now = datetime.utcnow()

# 1) pending, создан 4 часа назад — должен получить “пинок”
u1 = ensure_user(111111001, "pending_user")
sub1 = Subscription(
    user_id=u1.id,
    telegram_id=u1.telegram_id,
    payment_system="stripe",
    subscription_id="test_pending_1",
    status="pending",
    amount=10.0,
    created_at=now - timedelta(hours=4),
)
db.add(sub1)

# 2) active, истекает через 1 день — должен получить предупреждение
u2 = ensure_user(111111002, "expiring_user")
sub2 = Subscription(
    user_id=u2.id,
    telegram_id=u2.telegram_id,
    payment_system="paypal",
    subscription_id="test_active_warn_1",
    status="active",
    amount=10.0,
    created_at=now - timedelta(days=25),
    activated_at=now - timedelta(days=25),
    expires_at=now + timedelta(days=1),
    has_group_access=True,
)
db.add(sub2)

# 3) active, истёк вчера — должен деактивироваться и получить “прощалку”
u3 = ensure_user(111111003, "expired_user")
sub3 = Subscription(
    user_id=u3.id,
    telegram_id=u3.telegram_id,
    payment_system="stripe",
    subscription_id="test_active_expired_1",
    status="active",
    amount=10.0,
    created_at=now - timedelta(days=40),
    activated_at=now - timedelta(days=40),
    expires_at=now - timedelta(days=1),
    has_group_access=True,
)
db.add(sub3)

db.commit()
db.close()
print("✅ Fixtures inserted")
