import threading
import time
import logging
from webhook_listener import app
from graph_client import GraphClient
from daily_contact_updater import run_regular_updates
from apscheduler.schedulers.background import BackgroundScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Initial user emails to subscribe on startup (optional)
USER_EMAILS = [
    "conference@danisavage.com",
    "tdanisavage@danisavage.com",
    "rdanisavage@danisavage.com",
    "kdanisavage@danisavage.com"
]

def run_flask():
    app.run(host="0.0.0.0", port=80)

def main():

    # 1. Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)  # Give Flask time to start

    # 2. Ngrok tunnel for public URLs
    public_url = r"https://flexible-creative-boxer.ngrok-free.app"
    notification_url = f"{public_url}/notification"
    user_toggle_url = f"{public_url}/user_toggle"
    company_list_update_url = f"{public_url}/company_list_update"
    
    logging.info(f"Ngrok Notification URL: {notification_url}")
    logging.info(f"Ngrok User Toggle URL: {user_toggle_url}")
    logging.info(f"Ngrok Company List Update URL: {company_list_update_url}")
    
    # 3. Initialize Graph client and subscribe initial emails
    graph = GraphClient()
    subscription_map = {}
    for email in USER_EMAILS:
        sub = graph.subscribe_to_mail(notification_url, email)
        if sub and "id" in sub:
            subscription_map[sub["id"]] = email
            logging.info(f"Subscribed {email} -> {sub['id']}")
        else:
            logging.warning(f"Failed to subscribe {email}")

    # 4. Save objects in Flask app config for access in endpoints
    app.config["SUBSCRIPTION_MAP"] = subscription_map
    app.config["GRAPH_CLIENT"] = graph
    app.config["PUBLIC_URL"] = public_url

    # 5. (Optional) Start polling thread for audit logs
    # polling_thread = threading.Thread(target=run_polling, daemon=True)
    # polling_thread.start()

    # 6. Schedule any daily jobs if needed
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_regular_updates, 'interval', minutes = 1)
    scheduler.start()

    logging.info("Listening for notifications and webhooks...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down…")

if __name__ == "__main__":
    main()