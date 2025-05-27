import time
from datetime import datetime, timezone
from supabase_client import supabase
from recipient_list_loader import compile_and_store_master_list

# Keep track of the last time we polled
last_checked_at = datetime.now(timezone.utc)

def poll_audit_log(interval_seconds=30):
    global last_checked_at

    print("Starting polling loop...")

    while True:
        print(f"Polling for changes since {last_checked_at.isoformat()}...")

        # Query audit log for any changes since last poll
        res = (
            supabase
            .table("company_recipient_lists_audit")
            .select("*")
            .gte("changed_at", last_checked_at.isoformat())
            .execute()
        )

        if res.data:
            seen_users = set()
            for row in res.data:
                user_id = row["user_id"]
                seen_users.add(user_id)

            print(f"Detected changes for users: {seen_users}")

            for user_id in seen_users:
                # Fetch user email for this ID
                user_res = (
                    supabase
                    .table("users")
                    .select("email")
                    .eq("id", user_id)
                    .single()
                    .execute()
                )
                if user_res.data:
                    user_email = user_res.data["email"]
                    try:
                        compile_and_store_master_list(user_email)
                        print(f"Updated master list for {user_email}")
                    except Exception as e:
                        print(f"Error compiling list for {user_email}: {e}")
                else:
                    print(f"No email found for user ID: {user_id}")

        else:
            print("No changes detected.")

        # Update the time window and wait
        last_checked_at = datetime.now(timezone.utc)
        time.sleep(interval_seconds)
