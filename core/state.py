# Shared global states across modules
import threading
from collections import deque

BOT_RUNNING = False
BOT_PAUSED = False
CURRENT_STATUS = "Idle"
LOG_QUEUE = deque(maxlen=500)
METRICS = {"applied": 0, "skipped": 0, "suggested": 0}
DOUBT_QUEUE = []
DOUBT_LOCK = threading.Lock()
SESSION_STATS = {"evaluated_today": 0, "matches_today": 0, "applied_today": 0, "session_start": None}
ACTIVE_BROWSER_CONTEXT = None
ACTIVE_EVENT_LOOP = None
