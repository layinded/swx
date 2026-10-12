from swx_core.config.settings import settings
from swx_core.services.billing.providers import LocalPaymentProvider
from swx_core.services.billing.providers.flutterwave_provider import FlutterwaveProvider
from swx_core.services.billing.providers.mpesa_provider import MpesaProvider
from swx_core.services.billing.providers.paystack_provider import PaystackProvider
from swx_core.services.llm.config_resolver import resolve_config


def _provider_config(name: str) -> dict[str, str]:
    configs = {
        "paystack": {"secret_key": settings.PAYSTACK_SECRET_KEY, "public_key": settings.PAYSTACK_PUBLIC_KEY},
        "flutterwave": {"secret_key": settings.FLUTTERWAVE_SECRET_KEY, "public_key": settings.FLUTTERWAVE_PUBLIC_KEY, "encryption_key": settings.FLUTTERWAVE_ENCRYPTION_KEY},
        "mpesa": {"consumer_key": settings.MPESA_CONSUMER_KEY, "consumer_secret": settings.MPESA_CONSUMER_SECRET, "passkey": settings.MPESA_PASSKEY, "shortcode": settings.MPESA_SHORTCODE, "env": settings.MPESA_ENV},
    }
    if name not in configs:
        raise ValueError(f"Unsupported billing provider: {name}")
    return resolve_config(configs[name])


def get_local_payment_provider(name: str) -> LocalPaymentProvider:
    provider_name = name.lower()
    config = _provider_config(provider_name)
    providers = {
        "paystack": lambda: PaystackProvider(secret_key=str(config["secret_key"]), public_key=str(config["public_key"])),
        "flutterwave": lambda: FlutterwaveProvider(secret_key=str(config["secret_key"]), public_key=str(config["public_key"]), encryption_key=str(config["encryption_key"])),
        "mpesa": lambda: MpesaProvider(consumer_key=str(config["consumer_key"]), consumer_secret=str(config["consumer_secret"]), passkey=str(config["passkey"]), shortcode=str(config["shortcode"]), env=str(config["env"])),
    }
    return providers[provider_name]()
