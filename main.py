import json
import sqlite3
import os
import queue
import threading
import time
from datetime import datetime

# ==========================================
# 1. CORE FITNESS DATA ENGINE LAYER
# ==========================================
class FitnessInventoryEngine:
    def __init__(self, db_name="data/fitness_hub.db"):
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.setup_tables()

    def setup_tables(self):
        # Track core items like gym equipment, bars, plates, and supplements
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fitness_inventory (
                sku TEXT PRIMARY KEY,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                unit_cost REAL NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)
        # Audit log for stock changes, allocations to trainers, or customer pickups
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL,
                action_type TEXT CHECK(action_type IN ('RESTOCK', 'PICKUP_ORDER', 'ADJUSTMENT')),
                quantity_changed INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(sku) REFERENCES fitness_inventory(sku)
            )
        """)
        self.conn.commit()

    def update_item_stock(self, sku, name, category, quantity, unit_cost, action_type="RESTOCK"):
        timestamp = datetime.now().isoformat()
        self.cursor.execute("""
            INSERT INTO fitness_inventory (sku, item_name, category, quantity, unit_cost, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                quantity = quantity + excluded.quantity,
                unit_cost = excluded.unit_cost,
                last_updated = excluded.last_updated
        """, (sku, name, category, quantity, unit_cost, timestamp))
        
        self.cursor.execute("""
            INSERT INTO inventory_ledger (sku, action_type, quantity_changed, timestamp)
            VALUES (?, ?, ?, ?)
        """, (sku, action_type, quantity, timestamp))
        self.conn.commit()

    def close(self):
        self.conn.close()


# ==========================================
# 2. TRANSACTIONAL FITNESS API CONTROLLER
# ==========================================
class FitnessAPI:
    def __init__(self, db_name="data/fitness_hub.db"):
        self.db_name = db_name

    def process_pickup_checkout(self, order_id, sku, qty_requested):
        """Processes a gym client or retail order atomically."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT quantity, item_name FROM fitness_inventory WHERE sku = ?", (sku,))
            row = cursor.fetchone()
            if not row:
                return {"status": "ERROR", "message": f"Fitness item SKU {sku} not found."}
            
            current_qty, item_name = row
            if current_qty < qty_requested:
                return {"status": "DENIED", "message": f"Insufficient stock for {item_name}. Available: {current_qty}"}
            
            timestamp = datetime.now().isoformat()
            # Deduct inventory atomically
            cursor.execute("""
                UPDATE fitness_inventory 
                SET quantity = quantity - ?, last_updated = ? 
                WHERE sku = ?
            """, (qty_requested, timestamp, sku))
            
            # Log the outbound change
            cursor.execute("""
                INSERT INTO inventory_ledger (sku, action_type, quantity_changed, timestamp)
                VALUES (?, 'PICKUP_ORDER', ?, ?)
            """, (sku, -qty_requested, timestamp))
            
            conn.commit()
            return {"status": "CONFIRMED", "message": f"Order {order_id} successfully allocated {qty_requested}x {item_name}."}
        except Exception as e:
            conn.rollback()
            return {"status": "SYSTEM_FAIL", "message": str(e)}
        finally:
            conn.close()

    def get_fitness_manifest(self):
        """Returns the full active state of the fitness facility inventory."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT sku, item_name, category, quantity, unit_cost FROM fitness_inventory")
        items = cursor.fetchall()
        conn.close()
        return [{"sku": i[0], "name": i[1], "category": i[2], "quantity": i[3], "price": i[4]} for i in items]


# ==========================================
# 3. BACKGROUND BULK JOB WORKER
# ==========================================
class FitnessJobWorker:
    def __init__(self, engine_instance):
        self.engine = engine_instance
        self.job_queue = queue.Queue()
        self.is_running = False
        self._thread = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=1)

    def queue_bulk_restock(self, items_list):
        self.job_queue.put(items_list)

    def _run_loop(self):
        while self.is_running:
            try:
                batch = self.job_queue.get(timeout=0.2)
                for item in batch:
                    self.engine.update_item_stock(
                        sku=item.get("sku"),
                        name=item.get("name"),
                        category=item.get("category"),
                        quantity=item.get("quantity"),
                        unit_cost=item.get("price")
                    )
                self.job_queue.task_done()
            except queue.Empty:
                continue


# ==========================================
# 4. WEB GATEWAY API ROUTER
# ==========================================
class FitnessWebGateway:
    def __init__(self):
        self.api = FitnessAPI()

    def handle_request(self, endpoint, payload_json):
        try:
            payload = json.loads(payload_json)
        except Exception:
            return {"status_code": 400, "body": {"error": "Invalid JSON"}}

        if endpoint == "/api/fitness/checkout":
            order_id = payload.get("order_id")
            summaries = []
            for item in payload.get("items", []):
                res = self.api.process_pickup_checkout(order_id, item.get("sku"), item.get("quantity"))
                summaries.append({"sku": item.get("sku"), "status": res["status"], "detail": res["message"]})
            return {"status_code": 200, "body": {"order_id": order_id, "results": summaries}}
        
        elif endpoint == "/api/fitness/view":
            return {"status_code": 200, "body": {"fitness_hub_stock": self.api.get_fitness_manifest()}}
        
        return {"status_code": 404, "body": {"error": "Not Found"}}


# ==========================================
# 5. EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("[INIT] Starting Clean Fitness App Core Subsystem...")
    
    engine = FitnessInventoryEngine()
    worker = FitnessJobWorker(engine)
    gateway = FitnessWebGateway()
    
    worker.start()

    # Bulk feed initial gym catalog into the database asynchronously
    gym_gear_batch = [
        {"sku": "FIT-BAR-OLY", "name": "Olympic Barbell 20KG", "category": "Equipment", "quantity": 10, "price": 249.99},
        {"sku": "FIT-PLT-45LB", "name": "Bumper Plate 45LB", "category": "Weights", "quantity": 80, "price": 79.50},
        {"sku": "FIT-SUP-WHEY", "name": "Isolate Protein powder 5LB", "category": "Supplements", "quantity": 30, "price": 59.99}
    ]
    
    print("[SYSTEM] Loading gym equipment inventory into worker threads...")
    worker.queue_bulk_restock(gym_gear_batch)
    time.sleep(0.5)  # Let background thread commit changes

    # Simulate an incoming order from a commercial fitness user checkout
    order_payload = json.dumps({
        "order_id": "ORDER-FIT-9001",
        "items": [
            {"sku": "FIT-BAR-OLY", "quantity": 2},
            {"sku": "FIT-PLT-45LB", "quantity": 8},
            {"sku": "BAD-SKU-TEST", "quantity": 1}
        ]
    })

    print("\n[GATEWAY] Routing inbound client order payload...")
    checkout_response = gateway.handle_request("/api/fitness/checkout", order_payload)
    print(f"Response Status: {checkout_response['status_code']}")
    print(json.dumps(checkout_response['body'], indent=4))

    print("\n[GATEWAY] Fetching clean active fitness manifest report...")
    view_response = gateway.handle_request("/api/fitness/view", json.dumps({}))
    print(json.dumps(view_response['body'], indent=4))

    worker.stop()
    engine.close()
    print("\n[SUCCESS] Pipeline clean. No overlapping dependencies.")
