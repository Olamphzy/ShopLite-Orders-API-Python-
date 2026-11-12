# IMPORTANT ! DO NOT MODIFY THIS FILE
# Simulates a third-party email SDK. Like many SDKs, it only offers a blocking API.
import time


class EmailClient:
    def __init__(self, latency_seconds: float = 1.5):
        self.latency_seconds = latency_seconds
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> None:
        """Sends an email. Blocks the calling thread until the provider responds."""
        time.sleep(self.latency_seconds)
        self.sent.append({"to": to, "subject": subject, "body": body})
