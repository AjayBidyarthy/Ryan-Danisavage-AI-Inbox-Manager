import threading
import time
import logging
from webhook_listener import app
from graph_client import GraphClient
from daily_contact_updater import run_regular_updates
from apscheduler.schedulers.background import BackgroundScheduler
from supabase_client import supabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Initial user emails
USER_EMAILS = [
    "conference@danisavage.com",
    "tdanisavage@danisavage.com",
    "rdanisavage@danisavage.com",
    "kdanisavage@danisavage.com"
]

def run_flask():
    app.run(host="0.0.0.0", port=5000)

def main():

    # 1. Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)  # Give Flask time to start

    # 2. public URLs
    public_url = r"https://webhooks.danisavage.com"
    notification_url = f"{public_url}/notification"
    user_toggle_url = f"{public_url}/user_toggle"
    company_list_update_url = f"{public_url}/company_list_update"
    
    logging.info(f"Notification URL: {notification_url}")
    logging.info(f"User Toggle URL: {user_toggle_url}")
    logging.info(f"Company List Update URL: {company_list_update_url}")
    
    # 3. Initialize Graph client and subscribe initial emails
    graph = GraphClient()
    subscription_map = {}
    for email in USER_EMAILS:
        try:
            result = (
                supabase
                .table("inbox_manager_switch")
                .select("status")
                .eq("email", email)
                .single()
                .execute()
            )
            if result.data and result.data.get("status"):
                sub = graph.subscribe_to_mail(notification_url, email)
                if sub and "id" in sub:
                    subscription_map[sub["id"]] = email
                    logging.info(f"Subscribed {email} -> {sub['id']}")
                else:
                    logging.warning(f"Failed to subscribe {email}")
            else:
                logging.info(f"Skipping subscription for {email} (status = false)")
        except Exception as e:
            logging.error(f"Error checking switch for {email}: {e}")

    # 4. Save objects in Flask app config for access in endpoints
    app.config["SUBSCRIPTION_MAP"] = subscription_map
    app.config["GRAPH_CLIENT"] = graph
    app.config["PUBLIC_URL"] = public_url

    # 6. Schedule any daily jobs if needed
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_regular_updates, 'interval', hours = 24)
    scheduler.start()

    logging.info("Listening for notifications and webhooks...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down…")

if __name__ == "__main__":
    main()