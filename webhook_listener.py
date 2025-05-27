# webhook_listener.py

from flask import Flask, request, jsonify, current_app
from email_processor import process_email_notification

app = Flask(__name__)

@app.route("/notification", methods=["POST", "GET"])
def notification():
    # 1) Validation handshake
    validation_token = request.args.get("validationToken")
    if validation_token:
        return validation_token, 200, {"Content-Type": "text/plain"}

    # 2) Actual notification: don’t print the entire payload
    data = request.get_json(silent=True)
    for item in data.get("value", []):
        sub_id = item.get("subscriptionId")
        user_email = current_app.config["SUBSCRIPTION_MAP"].get(sub_id)
        if not user_email:
            # unknown subscription — skip
            continue

        # resourceData.id is the message ID
        message_id = item.get("resourceData", {}).get("id")
        if not message_id:
            continue

        # Build the resource path for fetching
        resource = f"users/{user_email}/mailFolders('Inbox')/messages/{message_id}"
        print(f"→ New email for {user_email}")

        process_email_notification(resource, user_email)

    return jsonify({"status": "received"}), 202
