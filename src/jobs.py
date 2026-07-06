import queue
import threading
import time
from src.security import SecurityManager

class AsyncJobWorker:
    def __init__(self, engine_instance):
        self.engine = engine_instance
        self.job_queue = queue.Queue()
        self.is_running = False
        self._worker_thread = None

    def start(self):
        """Spins up the isolated backend background worker."""
        if not self.is_running:
            self.is_running = True
            self._worker_thread = threading.Thread(target=self._process_loop, daemon=True)
            self._worker_thread.start()

    def stop(self):
        """Gracefully drains and kills the queue processor."""
        self.is_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2)

    def submit_bulk_restock(self, restock_list: list):
        """Accepts an array of items and appends it to the async engine pool."""
        self.job_queue.put(restock_list)

    def _process_loop(self):
        while self.is_running:
            try:
                # Polling interval matching high-efficiency local configurations
                batch = self.job_queue.get(timeout=0.5)
                print(f"[BACKGROUND JOB] Working thread processing {len(batch)} tasks...")
                
                for item in batch:
                    clean_sku = SecurityManager.sanitize_sku(item.get("sku"))
                    clean_price = SecurityManager.validate_price(item.get("price", 0.0))
                    
                    self.engine.update_stock(
                        sku=clean_sku,
                        name=item.get("name", "Async Product"),
                        quantity=int(item.get("quantity", 0)),
                        price=clean_price,
                        tx_type="STOCK_IN"
                    )
                self.job_queue.task_done()
                print("[BACKGROUND JOB] Batch completed execution track successfully.")
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[BACKGROUND JOB CRITICAL ERROR] Pipeline failed: {e}")
