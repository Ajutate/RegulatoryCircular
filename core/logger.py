"""
Logger
======
Configures application-wide logging with a combined size + daily rotation strategy.

Rotation rules:
  - At midnight every day  →  new file  app_YYYY-MM-DD.log
  - When file reaches 5 MB →  new file  app_YYYY-MM-DD.<n>.log

File layout example after a busy day:
  logs/app_2026-09-09.log      ← current file
  logs/app_2026-09-09.1.log   ← first size-roll of that day
  logs/app_2026-09-08.log     ← previous day (kept for 30 days)
"""

import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler

# ------------------------------------------------------------------ #
#  Custom handler: rotate on EITHER midnight OR 5 MB                  #
# ------------------------------------------------------------------ #

class SizedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    Rotates log files daily at midnight *and* whenever the file
    exceeds ``max_bytes``.

    File naming convention:
        logs/app_YYYY-MM-DD.log        (current active file)
        logs/app_YYYY-MM-DD.1.log      (first intra-day size rollover)
        logs/app_YYYY-MM-DD.2.log      (second intra-day size rollover)
        ...
    """

    def __init__(self, base_path: str, max_bytes: int = 5 * 1024 * 1024,
                 backup_days: int = 30, encoding: str = "utf-8"):
        self.base_path = base_path          # e.g. logs/app
        self.max_bytes = max_bytes
        self._size_index = 0               # counter within the current day

        # Compute today's dated filename before calling super().__init__
        today_str = time.strftime("%Y-%m-%d")
        filename = f"{base_path}_{today_str}.log"

        super().__init__(
            filename=filename,
            when="midnight",
            interval=1,
            backupCount=backup_days,
            encoding=encoding,
            delay=False,
            utc=False,
        )

    # ------------------------------------------------------------------
    #  Override the base-class suffix/extMatch so that timed-rolled
    #  files keep the dated name pattern.
    # ------------------------------------------------------------------
    def _build_dated_filename(self) -> str:
        """Return the canonical filename for today (no size-index)."""
        today_str = time.strftime("%Y-%m-%d")
        return f"{self.base_path}_{today_str}.log"

    def _build_sized_filename(self, date_str: str, index: int) -> str:
        """Return a size-indexed filename for a given date."""
        return f"{self.base_path}_{date_str}.{index}.log"

    # ------------------------------------------------------------------
    #  Size check — called by every emit()
    # ------------------------------------------------------------------
    def shouldRollover(self, record) -> bool:  # type: ignore[override]
        # First check the time-based condition from the parent
        if super().shouldRollover(record):
            return True
        # Then check size
        if self.stream and self.max_bytes > 0:
            self.stream.seek(0, 2)          # seek to end
            if self.stream.tell() >= self.max_bytes:
                return True
        return False

    # ------------------------------------------------------------------
    #  Rotation logic
    # ------------------------------------------------------------------
    def doRollover(self) -> None:
        """
        Decide which kind of rollover is happening:
          * Midnight (new day) → reset size-index, open new dated file.
          * Size limit hit     → rename current file with size-index,
                                  open a fresh file for the same date.
        """
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore[assignment]

        now_str = time.strftime("%Y-%m-%d")
        current_date = os.path.basename(self.baseFilename).split("_", 1)[-1].replace(".log", "")

        if current_date != now_str:
            # ── Day boundary: standard timed rotation ──────────────────
            self._size_index = 0
            new_filename = self._build_dated_filename()
            # Archive the old file under the timed-rotation suffix so
            # the parent's backupCount pruning still works.
            if os.path.exists(self.baseFilename):
                # Parent keeps files under  <base>.<timestamp>  pattern.
                # We just leave the dated file as-is; it already has the
                # date in its name and will age-out via getFilesToDelete().
                pass
            self.baseFilename = os.path.abspath(new_filename)
            self.rolloverAt = self.computeRollover(int(time.time()))
        else:
            # ── Intra-day size rollover ─────────────────────────────────
            self._size_index += 1
            archived_name = self._build_sized_filename(now_str, self._size_index)
            if os.path.exists(self.baseFilename):
                os.rename(self.baseFilename, archived_name)
            # baseFilename stays the same (dated .log); a fresh file opens

        self.mode = "a"
        self.stream = self._open()

    # ------------------------------------------------------------------
    #  Prune old files (respect backup_days)
    # ------------------------------------------------------------------
    def getFilesToDelete(self):
        """
        Return a list of old log files to delete so we don't accumulate
        files beyond backup_days.  Scans the log directory for files
        matching  app_YYYY-MM-DD*.log  and keeps only the newest
        backupCount of them.
        """
        log_dir = os.path.dirname(self.baseFilename)
        base_name = os.path.basename(self.base_path)   # e.g. "app"
        try:
            all_files = [
                os.path.join(log_dir, f)
                for f in os.listdir(log_dir)
                if f.startswith(base_name + "_") and f.endswith(".log")
                   and f != os.path.basename(self.baseFilename)
            ]
        except OSError:
            return []

        all_files.sort()   # oldest first (date-stamped names sort correctly)
        if len(all_files) <= self.backupCount:
            return []
        return all_files[: len(all_files) - self.backupCount]


# ------------------------------------------------------------------ #
#  Public API                                                          #
# ------------------------------------------------------------------ #

def setup_logging() -> None:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    base_path = os.path.join(log_dir, "app")

    # Force UTF-8 console output on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    file_handler = SizedTimedRotatingFileHandler(
        base_path=base_path,
        max_bytes=5 * 1024 * 1024,   # 5 MB per file
        backup_days=30,               # keep 30 daily files
        encoding="utf-8",
    )

    console_handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Suppress noisy third-party loggers
    logging.getLogger("passlib").setLevel(logging.ERROR)
    logging.getLogger("openai").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)

    # Avoid duplicate handlers when uvicorn hot-reloads the module
    has_file_handler = any(
        isinstance(h, SizedTimedRotatingFileHandler) for h in root_logger.handlers
    )
    if not has_file_handler:
        root_logger.addHandler(file_handler)

    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root_logger.handlers
    )
    if not has_console:
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# Initialise on import
setup_logging()
