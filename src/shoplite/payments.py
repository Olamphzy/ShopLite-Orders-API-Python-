# IMPORTANT ! DO NOT MODIFY THIS FILE
# Simulates an external payment provider. Treat it as a remote service: calls are slow and can be declined.
import asyncio
import secrets


class PaymentDeclinedError(Exception):
    code = "card_declined"


class PaymentGateway:
    def __init__(self, latency_seconds: float = 0.3, decline_above_cents: int = 100_000):
        self.latency_seconds = latency_seconds
        self.decline_above_cents = decline_above_cents

    async def charge(self, amount_cents: int, reference: str) -> dict:
        """Charges the customer. Raises PaymentDeclinedError when the card is declined."""
        if not isinstance(amount_cents, int) or isinstance(amount_cents, bool) or amount_cents <= 0:
            raise ValueError("amount_cents must be a positive integer")
        await asyncio.sleep(self.latency_seconds)
        if amount_cents > self.decline_above_cents:
            raise PaymentDeclinedError("Card declined: amount exceeds the card limit")
        return {"id": f"ch_{secrets.token_hex(8)}", "amount_cents": amount_cents, "reference": reference}
