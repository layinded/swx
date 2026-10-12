from swx_core.models.currency import TAX_RATES


def calculate_tax(amount_nano: int, jurisdiction: str) -> dict[str, int | float]:
    rate = TAX_RATES.get(jurisdiction.upper(), 0.0)
    tax_amount = int(round(amount_nano * (rate / 100)))
    return {"amount": amount_nano, "tax_rate": rate, "tax_amount": tax_amount, "total": amount_nano + tax_amount}


def get_supported_jurisdictions() -> dict[str, float]:
    return dict(TAX_RATES)
