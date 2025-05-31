import threading
import time
# from pyngrok import ngrok
from webhook_listener import app
from graph_client import GraphClient
from poll_audit_changes import poll_audit_log
from daily_contact_updater import run_daily_updates
from apscheduler.schedulers.background import BackgroundScheduler

# Initial user emails to subscribe on startup (optional)
USER_EMAILS = [
    "conference@danisavage.com"
]

def run_flask():
    app.run(host="0.0.0.0", port=80)

def run_polling():
    poll_audit_log()

def main():
    # 1. Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)  # Give Flask time to start

    # 2. Ngrok tunnel for public URLs
    public_url = r"https://aware-fluent-falcon.ngrok-free.app"
    notification_url = f"{public_url}/notification"
    user_toggle_url = f"{public_url}/user_toggle"
    print(f"Ngrok Notification URL: {notification_url}")
    print(f"Ngrok User Toggle URL: {user_toggle_url}")

    # 3. Initialize Graph client and subscribe initial emails
    graph = GraphClient()
    subscription_map = {}
    for email in USER_EMAILS:
        sub = graph.subscribe_to_mail(notification_url, email)
        if sub and "id" in sub:
            subscription_map[sub["id"]] = email
            print(f"Subscribed {email} -> {sub['id']}")
        else:
            print(f"Failed to subscribe {email}")

    # 4. Save objects in Flask app config for access in endpoints
    app.config["SUBSCRIPTION_MAP"] = subscription_map
    app.config["GRAPH_CLIENT"] = graph
    app.config["PUBLIC_URL"] = public_url

    # 5. Start polling thread for audit logs (optional if you still want to poll)
    polling_thread = threading.Thread(target=run_polling, daemon=True)
    polling_thread.start()

    # 6. Schedule any daily jobs if needed
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_updates, 'interval', minutes=2)
    scheduler.start()

    print("Listening for notifications and user toggle webhooks...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down…")

if __name__ == "__main__":
    main()