import logging
from flask import Flask, request, jsonify, current_app
from email_processor import process_email_notification
from recipient_list_loader import compile_and_store_master_list
from supabase_client import supabase

app = Flask(__name__)
logger = logging.getLogger(__name__)

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
            logger.warning("Received notification for unknown subscription ID: %s", sub_id)
            continue

        message_id = item.get("resourceData", {}).get("id")
        if not message_id:
            logger.warning("Missing message ID in resourceData")
            continue

        resource = f"users/{user_email}/mailFolders('Inbox')/messages/{message_id}"
        logger.info("New email for %s", user_email)

        process_email_notification(resource, user_email)

    return jsonify({"status": "received"}), 202


@app.route("/user_toggle", methods=["POST"])
def user_toggle():
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
        sub = graph.subscribe_to_mail(f"{current_app.config['PUBLIC_URL']}/notification", user_email)
        if sub and "id" in sub:
            subscription_map[sub["id"]] = user_email
            logger.info("Enabled inbox monitoring for %s with subscription %s", user_email, sub["id"])
        else:
            logger.error("Failed to subscribe %s", user_email)
    else:
        sub_ids_to_remove = [sid for sid, email in subscription_map.items() if email == user_email]
        for sid in sub_ids_to_remove:
            graph.unsubscribe(sid)
            del subscription_map[sid]
            logger.info("Disabled inbox monitoring for %s by removing subscription %s", user_email, sid)

    return jsonify({"status": "updated"}), 200


@app.route("/company_list_update", methods=["POST"])
def company_list_update():
    data = request.get_json(silent=True)
    logger.info("Received webhook payload: %s", data)

    if not data:
        return jsonify({"error": "No JSON payload"}), 400

    record = data.get("record") or data.get("old_record")
    if not record:
        return jsonify({"error": "No record or old_record in payload"}), 400

    user_id = record.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

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
            logger.info("Updated master list for %s", user_email)
        except Exception as e:
            logger.error("Error compiling list for %s: %s", user_email, e)
    else:
        logger.warning("No email found for user ID: %s", user_id)

    return jsonify({"status": "success"}), 200
