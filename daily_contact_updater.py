import csv
import io
import logging
from supabase_client import supabase, decode_file_data_hex, update_file_data
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

def find_email_key(headers: list[str]) -> str | None:
    for h in headers:
        if h.lower() == 'email' or h.lower()=='email id':
            return h
    return None

def find_name_key(headers: list[str], target: str) -> str | None:
    for h in headers:
        if h.lower() == 'name' or h.lower()=='contact name':
            return h
    return None

def process_unsubscribes():
    try:
        response = supabase.table("unsubscribe_emails").select("*").execute()
        unsubscribes = response.data
        admin = supabase.table("users").select("id").eq("name", "Admin").execute().data[0]
        list_files = supabase.table("list_files").select("*").eq("created_by", admin["id"]).execute().data

        for entry in unsubscribes:
            email = entry["email"]
            for file in list_files:
                file_data = decode_file_data_hex(file["file_data"]).decode("utf-8")
                reader = csv.DictReader(io.StringIO(file_data))
                email_key = find_email_key(reader.fieldnames)
                if not email_key:
                    logger.warning(f"No 'email' column found in file {file['id']}, skipping.")
                    continue
                updated_rows = [row for row in reader if row.get(email_key) != email]

                if len(updated_rows) < sum(1 for _ in csv.DictReader(io.StringIO(file_data))):
                    update_file_data(file["id"], updated_rows, reader.fieldnames)

                    # Propagate to renamed files
                    renames = supabase.table("renamed_files").select("new_file_id").eq("original_file_id", file["id"]).execute().data
                    for rename in renames:
                        renamed_file = supabase.table("list_files").select("*").eq("id", rename["new_file_id"]).single().execute().data
                        renamed_data = decode_file_data_hex(renamed_file["file_data"]).decode("utf-8")
                        renamed_reader = csv.DictReader(io.StringIO(renamed_data))
                        renamed_email_key = find_email_key(renamed_reader.fieldnames)
                        if not renamed_email_key:
                            logger.warning(f"No 'email' column found in renamed file {renamed_file['id']}, skipping.")
                            continue
                        renamed_rows = [row for row in renamed_reader if row.get(renamed_email_key) != email]
                        update_file_data(renamed_file["id"], renamed_rows, renamed_reader.fieldnames)

            supabase.table("unsubscribe_emails").delete().eq("id", entry["id"]).execute()
    except Exception as e:
        logger.error(f"Error processing unsubscribes: {e}")


def process_contact_changes():
    try:
        response = supabase.table("contact_changes").select("*").execute()
        changes = response.data
        admin = supabase.table("users").select("id").eq("name", "Admin").execute().data[0]
        list_files = supabase.table("list_files").select("*").eq("created_by", admin["id"]).execute().data

        for change in changes:
            old_email = change["old_email"]
            new_email = change["new_email"]
            new_name = change["new_name"]

            for file in list_files:
                file_data = decode_file_data_hex(file["file_data"]).decode("utf-8")
                reader = csv.DictReader(io.StringIO(file_data))
                email_key = find_email_key(reader.fieldnames)
                name_key = find_name_key(reader.fieldnames)
                if not email_key or not name_key:
                    logger.warning(f"Missing 'email' or 'name' columns in file {file['id']}, skipping.")
                    continue
                updated_rows = []
                modified = False

                for row in reader:
                    if row.get(email_key) == old_email:
                        row[email_key] = new_email
                        row[name_key] = new_name
                        modified=True
                    updated_rows.append(row)

                if modified:
                    update_file_data(file["id"], updated_rows, reader.fieldnames)

                    # Propagate to renamed files
                    renames = supabase.table("renamed_files").select("new_file_id").eq("original_file_id", file["id"]).execute().data
                    for rename in renames:
                        renamed_file = supabase.table("list_files").select("*").eq("id", rename["new_file_id"]).single().execute().data
                        renamed_data = decode_file_data_hex(renamed_file["file_data"]).decode("utf-8")
                        renamed_reader = csv.DictReader(io.StringIO(renamed_data))
                        renamed_email_key = find_email_key(renamed_reader.fieldnames)
                        renamed_name_key = find_name_key(renamed_reader.fieldnames)
                        if not renamed_email_key or not renamed_name_key:
                            logger.warning(f"Missing columns in renamed file {renamed_file['id']}, skipping.")
                            continue
                        renamed_rows = []
                        renamed_modified = False

                        for row in renamed_reader:
                            if row.get(renamed_email_key) == old_email:
                                row[renamed_email_key] = new_email
                                row[renamed_name_key] = new_name
                                renamed_modified = True

                        if renamed_modified:
                            update_file_data(renamed_file["id"], renamed_rows, renamed_reader.fieldnames)

            supabase.table("contact_changes").delete().eq("id", change["id"]).execute()
    except Exception as e:
        logger.error(f"Error processing contact changes: {e}")


def run_daily_updates():
    logger.info("Starting daily contact updates...")
    process_unsubscribes()
    process_contact_changes()
    logger.info("Completed daily contact updates.")
    
# run_daily_updates()