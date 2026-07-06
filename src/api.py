import sqlite3
from datetime import datetime
from src.engine import InventoryEngine

class InventoryAPI:
    def __init__(self, db_name="data/inventory.db"):
        self.db_name = db_name

    def get_db(self):
        return sqlite3.connect(self.db_name)

    def create_pickup_order(self, order_id, sku, quantity_requested):
        """Processes a customer order atomically. Checks stock before confirming."""
        conn = self.get_db()
        cursor = conn.cursor()
        try:
            # 1. Check current inventory levels
            cursor.execute("SELECT quantity, name FROM products WHERE sku = ?", (sku,))
            row = cursor.fetchone()
            
            if not row:
                return {"status": "ERROR", "message": f"SKU {sku} not found."}
            
            current_qty, prod_name = row
            if current_qty < quantity_requested:
                return {
                    "status": "DENIED", 
                    "message": f"Insufficient stock for {prod_name}. Requested: {quantity_requested}, Available: {current_qty}"
                }
            
            # 2. Deduct stock atomically
            timestamp = datetime.now().isoformat()
            cursor.execute("""
                UPDATE products 
                SET quantity = quantity - ?, updated_at = ? 
                WHERE sku = ?
            """, (quantity_requested, timestamp, sku))
            
            # 3. Log the outbound transaction
            cursor.execute("""
                INSERT INTO transactions (sku, type, quantity, timestamp)
                VALUES (?, 'ORDER_OUT', ?, ?)
            """, (sku, -quantity_requested, timestamp))
            
            conn.commit()
            return {"status": "CONFIRMED", "message": f"Order {order_id} locked for {quantity_requested}x {prod_name}."}
            
        except Exception as e:
            conn.rollback()
            return {"status": "SYSTEM_FAIL", "message": str(e)}
        finally:
            conn.close()

    def get_manifest(self):
        """Returns the current inventory state for small business reporting."""
        conn = self.db_name
        engine = InventoryEngine(conn)
        engine.cursor.execute("SELECT sku, name, quantity, price FROM products")
        items = engine.cursor.fetchall()
        engine.close()
        return [{"sku": i[0], "name": i[1], "quantity": i[2], "price": i[3]} for i in items]
