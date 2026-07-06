"""
RefineFlow — Real-Time Logging System
Color-coded, timestamped terminal output + optional file logging.
"""
import sys, io
# Force UTF-8 on Windows console
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import logging
import sys
from datetime import datetime
from typing import Optional

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    _COLORAMA = True
except ImportError:
    _COLORAMA = False


class RefineLogger:
    """
    Unified logger for RefineFlow.
    Supports SUCCESS / INFO / WARNING / ERROR levels with color output.

    Usage:
        log = RefineLogger()
        log.success("Dataset scanned successfully")
        log.warning("Duplicate risk is HIGH")
        log.error("File not found")
    """

    # ASCII-safe prefixes (Windows compatible)
    _PREFIX = {
        "success": "[OK]",
        "info":    "[>>]",
        "warning": "[!!]",
        "error":   "[XX]",
        "skip":    "[--]",
        "resume":  "[<<]",
    }

    _COLOR = {
        "success": Fore.GREEN   if _COLORAMA else "",
        "info":    Fore.CYAN    if _COLORAMA else "",
        "warning": Fore.YELLOW  if _COLORAMA else "",
        "error":   Fore.RED     if _COLORAMA else "",
        "skip":    Fore.MAGENTA if _COLORAMA else "",
        "resume":  Fore.BLUE    if _COLORAMA else "",
    }

    _RESET = Style.RESET_ALL if _COLORAMA else ""

    def __init__(self, name: str = "RefineFlow", log_file: Optional[str] = None,
                 verbose: bool = True):
        self.name = name
        self.verbose = verbose
        self._entries: list[dict] = []   # in-memory log for report

        # File handler (optional)
        self._file_logger: Optional[logging.Logger] = None
        if log_file:
            self._file_logger = logging.getLogger(name)
            self._file_logger.setLevel(logging.DEBUG)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            self._file_logger.addHandler(fh)

    def _log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = self._PREFIX.get(level, "[?]")
        color  = self._COLOR.get(level, "")
        reset  = self._RESET

        if self.verbose:
            print(f"{color}{prefix} {message}{reset}", flush=True)

        entry = {"time": ts, "level": level, "message": message}
        self._entries.append(entry)

        if self._file_logger:
            getattr(self._file_logger,
                    "info" if level in ("success", "info", "skip", "resume")
                    else level)(message)

    def success(self, message: str) -> None:
        self._log("success", message)

    def info(self, message: str) -> None:
        self._log("info", message)

    def warning(self, message: str) -> None:
        self._log("warning", message)

    def error(self, message: str) -> None:
        self._log("error", message)

    def skip(self, message: str) -> None:
        self._log("skip", message)

    def resume(self, message: str) -> None:
        self._log("resume", message)

    def section(self, title: str) -> None:
        """Print a section divider."""
        bar = "─" * 50
        if _COLORAMA:
            print(f"\n{Fore.CYAN}{bar}\n  {title}\n{bar}{Style.RESET_ALL}")
        else:
            print(f"\n{bar}\n  {title}\n{bar}")

    def get_entries(self) -> list[dict]:
        """Return all log entries (used by report generator)."""
        return self._entries.copy()

    def clear(self) -> None:
        self._entries.clear()


# Module-level default logger (can be replaced)
_default_logger = RefineLogger()


def get_logger(name: str = "RefineFlow", log_file: Optional[str] = None) -> RefineLogger:
    """Get a new named logger instance."""
    return RefineLogger(name=name, log_file=log_file)
