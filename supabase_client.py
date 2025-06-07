import binascii
import csv
import logging
from io import BytesIO, StringIO
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
from storage3.exceptions import StorageApiError

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_id_by_email(email: str) -> str | None:
    res = (
        supabase
        .table("users")
        .select("id")
        .eq("email", email)
        .single()
        .execute()
    )
    return res.data["id"] if res.data else None

def get_user_company_file_ids(user_id: str) -> list[str]:
    res = (
        supabase
        .table("company_recipient_lists")
        .select("file_id")
        .eq("user_id", user_id)
        .execute()
    )
    return [row["file_id"] for row in (res.data or [])]

def fetch_file_record(file_id: str) -> dict | None:
    res = (
        supabase
        .table("list_files")
        .select("*")
        .eq("id", file_id)
        .single()
        .execute()
    )
    return res.data if res.data else None

def decode_file_data_hex(hex_data: str) -> bytes:
    if hex_data.startswith("\\x") or hex_data.startswith("0x"):
        hex_str = hex_data[2:]
    else:
        hex_str = hex_data
    return binascii.unhexlify(hex_str)

def upload_master_list(user_email: str, csv_bytes: bytes) -> bool:
    bucket = "master-lists"
    path = f"{user_email}/master_list.csv"
    file_options = {"upsert": "true"}

    try:
        supabase.storage.from_(bucket).upload(path, csv_bytes, file_options)
        return True
    except StorageApiError as e:
        logger.error("Failed to upload master list for %s: %s", user_email, e)
        return False

def download_master_list(user_email: str) -> bytes | None:
    bucket = "master-lists"
    path = f"{user_email}/master_list.csv"
    return supabase.storage.from_(bucket).download(path)

def is_email_in_master_list(user_email: str, sender_email: str) -> bool:
    """
    Check if the sender_email exists in the user's master_list.
    """
    file_bytes = download_master_list(user_email)
    if not file_bytes:
        return False

    csv_text = file_bytes.decode("utf-8")
    csv_reader = csv.DictReader(StringIO(csv_text))

    for row in csv_reader:
        email = row.get("email") or row.get("Email") or row.get("EMAIL") or row.get('Email ID') or row.get('email id')
        if email and email.strip().lower() == sender_email.lower():
            return True

    return False

def store_contact_change(old_email: str, new_email: str, new_name: str):
    supabase.table("contact_changes").insert({
        "old_email": old_email,
        "new_email": new_email,
        "new_name": new_name
    }).execute()

def store_unsubscribe_email(email: str):
    supabase.table("unsubscribe_emails").insert({"email": email}).execute()

def update_file_data(file_id: str, rows: list[dict], fieldnames: list[str]):
    """
    Updates the list_files table with new CSV data encoded in hex, prefixed with \\x.
    """
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    csv_string = output.getvalue()
    hex_string = "\\x" + csv_string.encode("utf-8").hex()

    supabase.table("list_files").update({"file_data": hex_string}).eq("id", file_id).execute()

def delete_master_list(user_email: str) -> bool:
    """
    Deletes the master list CSV from Supabase Storage if it exists.
    Returns True if successful or not found, False on error.
    """
    try:
        path = f"{user_email}/master_list.csv"
        deleted_files = supabase.storage.from_("master-lists").remove([path])
        if not deleted_files:
            logger.info("Master list file not found or already deleted for %s", user_email)
        else:
            logger.info("Master list deleted for %s", user_email)
        return True
    except Exception as e:
        logger.error("Error deleting master list for %s: %s", user_email, e)
        return False