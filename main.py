import os
from src.engine import InventoryEngine

def init_application():
    print("[INIT] Starting Hyper-Local Inventory System...")
    
    # Initialize the engine data layers
    engine = InventoryEngine()
    
    # Run structural validation check
    try:
        print("[DATA] Validating local cache registers...")
        engine.update_stock("SKU-TEST-SYSTEM", "System Initialization Test", 0, 0.00, tx_type="ADJUSTMENT")
        print("[SUCCESS] Core engine operational and local database synced.")
    except Exception as e:
        print(f"[ERROR] Engine initialization failed: {e}")
    finally:
        engine.close()

if __name__ == "__main__":
    init_application()
