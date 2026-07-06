import sqlite3
from datetime import datetime

class InventoryEngine:
    def __init__(self, db_name="data/inventory.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

    def update_stock(self, sku, name, quantity, price, tx_type="STOCK_IN"):
        timestamp = datetime.now().isoformat()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT, quantity INTEGER, price REAL, updated_at TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS transactions (sku TEXT, type TEXT, quantity INTEGER, timestamp TEXT)")
        self.cursor.execute("INSERT INTO products VALUES (?,?,?,?,?) ON CONFLICT(sku) DO UPDATE SET quantity=quantity+excluded.quantity", (sku, name, quantity, price, timestamp))
        self.cursor.execute("INSERT INTO transactions VALUES (?,?,?,?)", (sku, tx_type, quantity, timestamp))
        self.conn.commit()

    def close(self):
        self.conn.close()
