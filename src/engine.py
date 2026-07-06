import sqlite3
import os
from datetime import datetime

class InventoryEngine:
    def __init__(self, db_name="data/inventory.db"):
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.setup_tables()

    def setup_tables(self):
        """Initializes the core commercial inventory tables."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                price REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL,
                type TEXT CHECK(type IN ('STOCK_IN', 'ORDER_OUT', 'ADJUSTMENT')),
                quantity INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(sku) REFERENCES products(sku)
            )
        """)
        self.conn.commit()

    def update_stock(self, sku, name, quantity, price, tx_type="STOCK_IN"):
        """Handles atomic stock updates and records transactions for audit safety."""
        timestamp = datetime.now().isoformat()
        
        # Upsert product profile
        self.cursor.execute("""
            INSERT INTO products (sku, name, quantity, price, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                quantity = quantity + excluded.quantity,
                price = excluded.price,
                updated_at = excluded.updated_at
        """, (sku, name, quantity, price, timestamp))
        
        # Record history trace
        self.cursor.execute("""
            INSERT INTO transactions (sku, type, quantity, timestamp)
            VALUES (?, ?, ?, ?)
        """, (sku, tx_type, quantity, timestamp))
        
        self.conn.commit()
        print(f"[SUCCESS] Processed {tx_type} for SKU: {sku} | Qty Change: {quantity}")

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    # Quick operational verification check
    engine = InventoryEngine()
    engine.update_stock("SKU-CORE-001", "Base Engine Block", 10, 249.99)
    engine.close()

