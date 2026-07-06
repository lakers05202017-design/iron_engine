import re
import hashlib
from datetime import datetime

class SecurityManager:
    @staticmethod
    def sanitize_sku(sku: str) -> str:
        """Removes illegal characters from SKUs to prevent query exploits."""
        if not sku:
            return ""
        return re.sub(r'[^a-zA-Z0-9\-_]', '', str(sku)).upper().strip()

    @staticmethod
    def generate_audit_hash(order_id: str, sku: str, quantity: int) -> str:
        """Generates a cryptographic signature to verify transaction history integrity."""
        payload = f"{order_id}:{sku}:{quantity}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    @staticmethod
    def validate_price(price: float) -> float:
        """Ensures commercial values cannot be set below zero."""
        try:
            val = float(price)
            return max(0.0, val)
        except (ValueError, TypeError):
            return 0.0
