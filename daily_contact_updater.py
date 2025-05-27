import csv
import io
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def update_file_data(file_id, rows, fieldnames):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    csv_string = output.getvalue()
    hex_string = csv_string.encode("utf-8").hex()

    supabase.table("list_files").update({"file_data": hex_string}).eq("id", file_id).execute()


def process_unsubscribes():
    response = supabase.table("unsubscribe_emails").select("*").execute()
    unsubscribes = response.data
    for entry in unsubscribes:
        email = entry["email"]
        admin = supabase.table("users").select("id").eq("name", "Admin").execute().data[0]
        list_files = supabase.table("list_files").select("*").eq("user_id", admin["id"]).execute().data

        for file in list_files:
            file_data = bytes.fromhex(file["file_data"]).decode("utf-8")
            reader = csv.DictReader(io.StringIO(file_data))
            updated_rows = [row for row in reader if row["email"] != email]

            if len(updated_rows) < sum(1 for _ in csv.DictReader(io.StringIO(file_data))):  # change detected
                update_file_data(file["id"], updated_rows, reader.fieldnames)

                # Update rename_files if any
                renames = supabase.table("rename_files").select("new_file_id").eq("original_file_id", file["id"]).execute().data
                for rename in renames:
                    renamed_file = supabase.table("list_files").select("*").eq("id", rename["new_file_id"]).execute().data[0]
                    renamed_data = bytes.fromhex(renamed_file["file_data"]).decode("utf-8")
                    renamed_reader = csv.DictReader(io.StringIO(renamed_data))
                    renamed_rows = [row for row in renamed_reader if row["email"] != email]
                    update_file_data(renamed_file["id"], renamed_rows, renamed_reader.fieldnames)

        supabase.table("unsubscribe_emails").delete().eq("id", entry["id"]).execute()


def process_contact_changes():
    response = supabase.table("contact_changes").select("*").execute()
    changes = response.data
    for change in changes:
        old_email = change["old_email"]
        new_email = change["new_email"]
        new_name = change["new_name"]
        admin = supabase.table("users").select("id").eq("name", "Admin").execute().data[0]
        list_files = supabase.table("list_files").select("*").eq("user_id", admin["id"]).execute().data

        for file in list_files:
            file_data = bytes.fromhex(file["file_data"]).decode("utf-8")
            reader = csv.DictReader(io.StringIO(file_data))
            updated_rows = []
            modified = False
            for row in reader:
                if row["email"] == old_email:
                    row["email"] = new_email
                    row["name"] = new_name
                    modified = True
                updated_rows.append(row)

            if modified:
                update_file_data(file["id"], updated_rows, reader.fieldnames)

                # Update rename_files if any
                renames = supabase.table("rename_files").select("new_file_id").eq("original_file_id", file["id"]).execute().data
                for rename in renames:
                    renamed_file = supabase.table("list_files").select("*").eq("id", rename["new_file_id"]).execute().data[0]
                    renamed_data = bytes.fromhex(renamed_file["file_data"]).decode("utf-8")
                    renamed_reader = csv.DictReader(io.StringIO(renamed_data))
                    renamed_rows = []
                    renamed_modified = False
                    for row in renamed_reader:
                        if row["email"] == old_email:
                            row["email"] = new_email
                            row["name"] = new_name
                            renamed_modified = True
                        renamed_rows.append(row)
                    if renamed_modified:
                        update_file_data(renamed_file["id"], renamed_rows, renamed_reader.fieldnames)

        supabase.table("contact_changes").delete().eq("id", change["id"]).execute()

def run_daily_updates():
    process_unsubscribes()
    process_contact_changes()
