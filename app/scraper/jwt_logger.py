"""Log stream dedicated to the desktop jwt_api engine — deliberately separate from
app.scraper.logger (shared by api/playwright/selenium/emulator) so a jwt_api job's
log never interleaves with an unrelated ADB job's log."""
import datetime
import sys


class ScraperLogger:
    def __init__(self):
        self.logs = []

    def log(self, msg: str, ok: bool = True):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {"time": timestamp, "msg": msg, "ok": ok}
        self.logs.append(entry)
        if len(self.logs) > 2000:
            self.logs = self.logs[-1000:]
        try:
            print(f"[jwt][{timestamp}] {msg}")
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or 'utf-8'
            print(f"[jwt][{timestamp}] {msg.encode(encoding, errors='replace').decode(encoding)}")

    def get_logs(self, start_idx: int = 0):
        new_logs = self.logs[start_idx:]
        return new_logs, len(self.logs)

    def clear(self):
        self.logs = []


scraper_logger = ScraperLogger()


def log(msg: str, ok: bool = True):
    scraper_logger.log(msg, ok)
