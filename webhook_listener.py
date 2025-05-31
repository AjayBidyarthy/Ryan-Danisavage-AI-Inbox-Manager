from flask import Flask, request, jsonify, current_app
from email_processor import process_email_notification

app = Flask(__name__)

@app.route("/notification", methods=["POST", "GET"])
def notification():
    # 1) Validation handshake for Microsoft Graph subscription validation
    validation_token = request.args.get("validationToken")
    if validation_token:
        return validation_token, 200, {"Content-Type": "text/plain"}

    # 2) Actual notification from Microsoft Graph: email events
    data = request.get_json(silent=True)
    if not data or "value" not in data:
        return jsonify({"error": "Invalid payload"}), 400

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


@app.route("/user_toggle", methods=["POST"])
def user_toggle():
    """
    Endpoint to handle Supabase webhook for inbox_manager_switch table updates.
    Expected JSON payload from Supabase webhook includes:
    {
        "event": "UPDATE",
        "table": "inbox_manager_switch",
        "schema": "public",
        "record": {
            "user_id": "...",
            "email": "...",
            "status": true/false,
            "updated_at": "..."
        },
        ...
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON payload"}), 400

    record = data.get("record")
    if not record:
        return jsonify({"error": "No record in payload"}), 400

    user_email = record.get("email")
    new_status = record.get("status")

    if user_email is None or new_status is None:
        return jsonify({"error": "Missing email or status"}), 400

    graph = current_app.config.get("GRAPH_CLIENT")
    subscription_map = current_app.config.get("SUBSCRIPTION_MAP", {})

    if new_status:
        # Enable inbox monitoring for user
        sub = graph.subscribe_to_mail(f"{current_app.config['PUBLIC_URL']}/notification", user_email)
        if sub and "id" in sub:
            subscription_map[sub["id"]] = user_email
            print(f"Enabled inbox monitoring for {user_email} with subscription {sub['id']}")
        else:
            print(f"Failed to subscribe {user_email}")
    else:
        # Disable inbox monitoring for user
        # Find subscription ID(s) for this user
        sub_ids_to_remove = [sid for sid, email in subscription_map.items() if email == user_email]
        for sid in sub_ids_to_remove:
            # You need to implement unsubscribe method in your GraphClient
            graph.unsubscribe(sid)
            del subscription_map[sid]
            print(f"Disabled inbox monitoring for {user_email} by removing subscription {sid}")

    return jsonify({"status": "updated"}), 200
