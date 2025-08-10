# scripts/create_paypal_plan.py
import os
import sys
import requests
from payment_config import PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_API_BASE

API_BASE = PAYPAL_API_BASE.rstrip('/') if PAYPAL_API_BASE else "https://api-m.sandbox.paypal.com"

def get_access_token():
    url = f"{API_BASE}/v1/oauth2/token"
    resp = requests.post(url,
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        data={'grant_type': 'client_credentials'}
    )
    resp.raise_for_status()
    return resp.json()['access_token']

def create_product(token, name="Подписка на бот", description="Доступ к VIP контенту"):
    url = f"{API_BASE}/v1/catalogs/products"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "name": name,
        "description": description,
        "type": "SERVICE",
        "category": "SOFTWARE"
    }
    r = requests.post(url, headers=headers, json=body)
    r.raise_for_status()
    return r.json()['id']

def create_plan(token, product_id, currency="EUR", amount="5.00", interval_unit="MONTH", interval_count=1, trial_days=0):
    url = f"{API_BASE}/v1/billing/plans"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    billing_cycles = []
    seq = 1
    if trial_days and int(trial_days) > 0:
        billing_cycles.append({
            "frequency": {"interval_unit": "DAY", "interval_count": int(trial_days)},
            "tenure_type": "TRIAL",
            "sequence": seq,
            "total_cycles": 1,
            "pricing_scheme": {"fixed_price": {"value": "0", "currency_code": currency}}
        })
        seq += 1

    billing_cycles.append({
        "frequency": {"interval_unit": interval_unit, "interval_count": int(interval_count)},
        "tenure_type": "REGULAR",
        "sequence": seq,
        "total_cycles": 0,   # 0 = infinite
        "pricing_scheme": {"fixed_price": {"value": str(amount), "currency_code": currency}}
    })

    body = {
        "product_id": product_id,
        "name": f"{amount} {currency} / {interval_count} {interval_unit.lower()}",
        "description": "Месячная подписка на курс",
        "billing_cycles": billing_cycles,
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee": {"value": "0", "currency_code": currency},
            "setup_fee_failure_action": "CONTINUE",
            "payment_failure_threshold": 3
        },
        "taxes": {"percentage": "0", "inclusive": False}
    }

    r = requests.post(url, headers=headers, json=body)
    r.raise_for_status()
    return r.json()['id']

def main():
    token = get_access_token()
    print("Access token OK")
    product_id = create_product(token)
    print("Created product:", product_id)
    plan_id = create_plan(token, product_id, currency="EUR", amount="10.00", interval_unit="MONTH", interval_count=1, trial_days=0)
    print("Created plan_id:", plan_id)
    print("Теперь добавь этот plan_id в payment_config.PAYPAL_PLAN_ID")

if __name__ == "__main__":
    main()
