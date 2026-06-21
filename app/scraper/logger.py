import datetime
import sys

class ScraperLogger:
    def __init__(self):
        self.logs = []
        
    def log(self, msg: str, ok: bool = True):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {"time": timestamp, "msg": msg, "ok": ok}
        self.logs.append(entry)
        # Keep it from growing infinitely in memory
        if len(self.logs) > 2000:
            self.logs = self.logs[-1000:]
            
        try:
            print(f"[{timestamp}] {msg}")
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or 'utf-8'
            safe_msg = msg.encode(encoding, errors='replace').decode(encoding)
            print(f"[{timestamp}] {safe_msg}")
            
    def get_logs(self, start_idx: int = 0):
        # Return new logs and the new next_idx
        new_logs = self.logs[start_idx:]
        return new_logs, len(self.logs)
        
    def clear(self):
        self.logs = []

# Global instance
scraper_logger = ScraperLogger()

def log(msg: str, ok: bool = True):
    scraper_logger.log(msg, ok)
