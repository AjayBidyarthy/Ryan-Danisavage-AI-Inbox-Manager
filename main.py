import threading, time
from pyngrok import ngrok
from webhook_listener import app
from graph_client import GraphClient
from poll_audit_changes import poll_audit_log
from daily_contact_updater import run_daily_updates
from apscheduler.schedulers.background import BackgroundScheduler

# List of mailboxes
USER_EMAILS = [
    "conference@danisavage.com"
]

def run_flask():
    app.run(host="0.0.0.0", port=5000)

def run_polling():
    poll_audit_log()

def main():
    # 1 Start Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)

    # 2 Ngrok tunnel
    public_url = ngrok.connect(5000).public_url
    notification_url = f"{public_url}/notification"
    print(f"Ngrok URL: {notification_url}")

    # 3 Subscribe & build map
    graph = GraphClient()
    subscription_map = {}
    for email in USER_EMAILS:
        sub = graph.subscribe_to_mail(notification_url, email)
        if sub and "id" in sub:
            subscription_map[sub["id"]] = email
            print(f"Subscribed {email} → {sub['id']}")
        else:
            print(f" Failed to subscribe {email}")

    # Make the map available to the Flask app
    app.config["SUBSCRIPTION_MAP"] = subscription_map

    # Start polling thread
    polling_thread = threading.Thread(target=run_polling, daemon=True)
    polling_thread.start()

    # Schedule daily updates
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_updates, 'interval', hours=24)
    scheduler.start()
    
    print("Listening for notifications and auditing changes...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down…")

if __name__ == "__main__":
    main()
