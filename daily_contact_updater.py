import csv
import io
from supabase_client import supabase, decode_file_data_hex, update_file_data  # Use the shared client and decoding
from supabase_client import fetch_file_record  # Optional if needed
from config import SUPABASE_URL, SUPABASE_KEY

def find_field_key(headers: list[str], target: str) -> str | None:
    for h in headers:
        if h.lower() == target.lower():
            return h
    return None

def process_unsubscribes():
    response = supabase.table("unsubscribe_emails").select("*").execute()
    unsubscribes = response.data
    admin = supabase.table("users").select("id").eq("name", "Admin").execute().data[0]
    list_files = supabase.table("list_files").select("*").eq("created_by", admin["id"]).execute().data

    for entry in unsubscribes:
        email = entry["email"]
        for file in list_files:
            file_data = decode_file_data_hex(file["file_data"]).decode("utf-8")
            reader = csv.DictReader(io.StringIO(file_data))
            email_key = find_field_key(reader.fieldnames, "email")
            if not email_key:
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
                    renamed_email_key = find_field_key(renamed_reader.fieldnames, "email")
                    if not renamed_email_key:
                        continue
                    renamed_rows = [row for row in renamed_reader if row.get(renamed_email_key) != email]
                    update_file_data(renamed_file["id"], renamed_rows, renamed_reader.fieldnames)

        supabase.table("unsubscribe_emails").delete().eq("id", entry["id"]).execute()


def process_contact_changes():
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
            email_key = find_field_key(reader.fieldnames, "email")
            name_key = find_field_key(reader.fieldnames, "name")
            if not email_key or not name_key:
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
                    renamed_email_key = find_field_key(renamed_reader.fieldnames, "email")
                    renamed_name_key = find_field_key(renamed_reader.fieldnames, "name")
                    if not renamed_email_key or not renamed_name_key:
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


def run_daily_updates():
    process_unsubscribes()
    process_contact_changes()


# if __name__ == "__main__":
#     run_daily_updates()
