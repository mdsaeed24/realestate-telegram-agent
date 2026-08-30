"""Shared helpers for the seeding and inspection scripts."""
import os
import pathlib

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

PROPERTY_HEADERS = [
    "property_id", "name", "property_type", "price_inr", "locality", "city",
    "status", "key_details", "maps_url", "media_folder", "hero_file",
    "gallery_files", "video_file",
]
LEAD_HEADERS = [
    "lead_id", "name", "phone", "source", "enquired_about", "status", "deep_link",
]
BOOKING_HEADERS = [
    "booking_id", "lead_id", "lead_name", "property_id", "property_name",
    "slot_date", "slot_time", "maps_url", "created_at",
]
TABS = {
    "Properties": PROPERTY_HEADERS,
    "Leads": LEAD_HEADERS,
    "Bookings": BOOKING_HEADERS,
}


def env():
    load_dotenv(ROOT / ".env")
    missing = [k for k in ("GOOGLE_SHEET_ID", "GOOGLE_CREDENTIALS_PATH") if not os.getenv(k)]
    if missing:
        raise SystemExit(f"missing env vars: {', '.join(missing)}")
    return os.environ


def sheets_service(e):
    creds = Credentials.from_service_account_file(
        str(ROOT / e["GOOGLE_CREDENTIALS_PATH"]), scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)
