import requests
import logging
from graph_client import GraphClient
from supabase_client import is_email_in_master_list, store_contact_change, store_unsubscribe_email
from bs4 import BeautifulSoup  # type: ignore
from email_classify import classify_email
from contact_extract import extract_new_contact_info
import re

logger = logging.getLogger(__name__)

# Keep track of already processed emails in this run
processed_message_ids = set()

def extract_actual_body(html_body: str) -> str:
    soup = BeautifulSoup(html_body, "html.parser")
    text = soup.get_text(separator="\n")

    banned_phrases = [
        "You don't often get email from",
        "Learn why this is important",
    ]
    cleaned_lines = [
        line.strip()
        for line in text.splitlines()
        if not any(banner in line for banner in banned_phrases)
    ]
    return "\n".join(filter(None, cleaned_lines)).strip()

def extract_original_sender(forwarded_body: str) -> str:
    # Look for patterns like "From: John Smith <john@example.com>"
    match = re.search(r"From:\s+.*?<([^@\s]+@[^>\s]+)>", forwarded_body, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def process_email_notification(resource_url, user_email):
    logger.info(f"Fetching email details for: {resource_url}")

    graph = GraphClient()
    headers = {"Authorization": f"Bearer {graph.token}"}

    response = requests.get(f"https://graph.microsoft.com/v1.0/{resource_url}", headers=headers)
    if response.status_code != 200:
        logger.error("Failed to fetch message details: %s", response.text)
        return

    data = response.json()

    message_id = data.get("id")
    if not message_id:
        logger.warning("No message ID found, skipping.")
        return

    if message_id in processed_message_ids:
        logger.info(f"Duplicate message {message_id}, skipping.")
        return

    processed_message_ids.add(message_id)

    sender_email = data.get("from", {}).get("emailAddress", {}).get("address", "")
    subject = data.get("subject", "")
    body = data.get("body", {}).get("content", "")
    clean_body = extract_actual_body(body)

    logger.debug(f"Initial From: {sender_email}\nSubject: {subject}\nBody: {clean_body}")

    # If email is from replies alias, try to extract original sender
    if sender_email.endswith("@danisavagereplies.com"):
        original_sender = extract_original_sender(clean_body)
        if original_sender:
            logger.info(f"Detected forwarded email. Original sender: {original_sender}")
            sender_email = original_sender
        else:
            logger.warning("Could not detect original sender in forwarded message.")

    classification = classify_email(clean_body)
    logger.info(f"Email classified as: {classification}")

    destination_folder = None

    if classification == "Not Interested":
        if is_email_in_master_list(user_email, sender_email):
            destination_folder = "Not Interested - Companies"
        else:
            destination_folder = "Not Interested - Investors"

    elif classification == "Contact Changed":
        destination_folder = "Contact Changed"
        contact_info = extract_new_contact_info(clean_body)
        store_contact_change(sender_email, contact_info.get("new_contact_email"), contact_info.get("new_contact_name"))

    elif classification == "Unsubscribe":
        destination_folder = "Unsubscribe"
        store_unsubscribe_email(sender_email)

    if destination_folder:
        folder_id = graph.get_or_create_subfolder(user_email, destination_folder)
        if folder_id:
            graph.move_email_to_folder(user_email, message_id, folder_id)
            logger.info(f"Moved email to '{destination_folder}'")
        else:
            logger.error(f"Failed to determine folder ID for: {destination_folder}")
    else:
        logger.info("Keeping email in Inbox")