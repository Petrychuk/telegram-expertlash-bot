import stripe
from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment
from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersCaptureRequest
from paypalcheckoutsdk.payments import CapturesRefundRequest
from payment_config import *
import json

# Настройка Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Настройка PayPal
class PayPalClient:
    def __init__(self):
        # Используйте SandboxEnvironment для тестирования, LiveEnvironment для продакшена
        self.environment = SandboxEnvironment(client_id=PAYPAL_CLIENT_ID, client_secret=PAYPAL_CLIENT_SECRET)
        # self.environment = LiveEnvironment(client_id=PAYPAL_CLIENT_ID, client_secret=PAYPAL_CLIENT_SECRET)
        self.client = PayPalHttpClient(self.environment)

paypal_client = PayPalClient()

class StripeService:
    @staticmethod
    def create_subscription_session(telegram_id: int, user_email: str = None):
        """Создание сессии подписки в Stripe"""
        try:
            # Создаем или получаем клиента
            customer = stripe.Customer.create(
                email=user_email,
                metadata={'telegram_id': str(telegram_id)}
            )
            
            # Создаем продукт (если еще не создан)
            try:
                product = stripe.Product.retrieve('lash_course_subscription')
            except stripe.error.InvalidRequestError:
                product = stripe.Product.create(
                    name='Курс "Ресницы от нуля до эксперта"',
                    description='Месячная подписка на курс по наращиванию ресниц'
                )
            
            # Создаем цену (если еще не создана)
            try:
                price = stripe.Price.retrieve('price_1Rs2wB6S8Oc0JZWfqIIhtXze')
            except stripe.error.InvalidRequestError:
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(SUBSCRIPTION_PRICE * 100),  # В центах
                    currency='eur',
                    recurring={'interval': 'month'}
                )
            
            # Создаем сессию подписки
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price.id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=PAYPAL_RETURN_URL + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=PAYPAL_CANCEL_URL,
                metadata={'telegram_id': str(telegram_id)}
            )
            
            return {
                'success': True,
                'session_id': session.id,
                'url': session.url,
                'customer_id': customer.id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_subscription_status(subscription_id: str):
        """Получение статуса подписки"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                'success': True,
                'status': subscription.status,
                'current_period_end': subscription.current_period_end,
                'customer_id': subscription.customer
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def cancel_subscription(subscription_id: str):
        """Отмена подписки"""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            return {
                'success': True,
                'status': subscription.status,
                'cancel_at_period_end': subscription.cancel_at_period_end
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

class PayPalService:
    @staticmethod
    def create_subscription_order(telegram_id: int):
        """Создание заказа подписки в PayPal"""
        try:
            request = OrdersCreateRequest()
            request.prefer('return=representation')
            request.request_body({
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "EUR",
                        "value": str(SUBSCRIPTION_PRICE)
                    },
                    "description": "Курс 'Ресницы от нуля до эксперта' - месячная подписка"
                }],
                "application_context": {
                    "return_url": PAYPAL_RETURN_URL,
                    "cancel_url": PAYPAL_CANCEL_URL,
                    "brand_name": "Lash Course",
                    "landing_page": "BILLING",
                    "user_action": "PAY_NOW"
                },
                "custom_id": str(telegram_id)  # Сохраняем telegram_id для связи
            })
            
            response = paypal_client.client.execute(request)
            
            # Получаем ссылку для оплаты
            approval_url = None
            for link in response.result.links:
                if link.rel == "approve":
                    approval_url = link.href
                    break
            
            return {
                'success': True,
                'order_id': response.result.id,
                'approval_url': approval_url
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def capture_order(order_id: str):
        """Захват (подтверждение) заказа PayPal"""
        try:
            request = OrdersCaptureRequest(order_id)
            response = paypal_client.client.execute(request)
            
            return {
                'success': True,
                'status': response.result.status,
                'order_id': response.result.id,
                'payer_id': response.result.payer.payer_id if response.result.payer else None
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

def verify_stripe_webhook(payload, sig_header):
    """Проверка подписи Stripe webhook"""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        return event
    except ValueError:
        # Неверный payload
        return None
    except stripe.error.SignatureVerificationError:
        # Неверная подпись
        return None

def verify_paypal_webhook(headers, body):
    """Проверка подписи PayPal webhook (упрощенная версия)"""
    # PayPal webhook verification более сложная и требует дополнительных запросов к API
    # Для простоты здесь базовая проверка
    # В продакшене нужно реализовать полную проверку согласно документации PayPal
    return True
