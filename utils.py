from datetime import datetime


def fmt_price(value) -> str:
    """730.00 -> '730', 389.50 -> '389.5' — no scientific notation, ever."""
    value = float(value)
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


PAYMENT_METHOD_LABELS = {"cash": "💵 Наличные", "terminal": "💳 Терминал", "transfer": "📲 Перевод"}
PAYMENT_STATUS_LABELS = {
    "pending": "⏳ ждём оплату",
    "confirmed": "✅ оплачено",
    "declined": "❌ отклонено",
}
