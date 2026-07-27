import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set (check your .env / Render env vars)")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set (check your .env / Render env vars)")

_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip()}
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS is empty — set at least one Telegram user id")

# --- Webhook config -----------------------------------------------------
# Path is kept secret-ish so random bots scanning /webhook don't hit it.
_webhook_secret_path = os.getenv("WEBHOOK_SECRET", BOT_TOKEN.split(":")[0])
WEBHOOK_PATH = f"/webhook/{_webhook_secret_path}"

# Render sets RENDER_EXTERNAL_URL automatically for Web Services.
# WEBHOOK_URL can be set manually as a fallback (e.g. for other hosts).
_external_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("WEBHOOK_URL", "")
EXTERNAL_URL = _external_url.rstrip("/")
WEBHOOK_URL = f"{EXTERNAL_URL}{WEBHOOK_PATH}" if EXTERNAL_URL else ""

# Telegram sends this header back on every webhook request; we verify it
# to make sure requests actually come from Telegram and not a random POST.
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "mix-pizza-webhook-secret")

PORT = int(os.getenv("PORT", "10000"))

PIZZERIA_NAME = "МИКС"
