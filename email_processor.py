import requests
from graph_client import GraphClient
from supabase_client import is_email_in_master_list, store_contact_change, store_unsubscribe_email
from bs4 import BeautifulSoup # type: ignore
from email_classify import classify_email
from contact_extract import extract_new_contact_info

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


def process_email_notification(resource_url, user_email):
    print(f"Fetching email details for: {resource_url}")
    
    graph = GraphClient()
    headers = {"Authorization": f"Bearer {graph.token}"}

    response = requests.get(f"https://graph.microsoft.com/v1.0/{resource_url}", headers=headers)
    if response.status_code != 200:
        print("Failed to fetch message details:", response.text)
        return

    data = response.json()

    # Extract message ID
    message_id = data.get("id")
    if not message_id:
        print("No message ID found, skipping.")
        return

    if message_id in processed_message_ids:
        print(f"Duplicate message {message_id}, skipping.")
        return

    # Mark as processed
    processed_message_ids.add(message_id)

    sender_email = data.get("from", {}).get("emailAddress", {}).get("address", "")
    subject = data.get("subject", "")
    body = data.get("body", {}).get("content", "")
    clean_body = extract_actual_body(body)

    print(f"From: {sender_email}\nSubject: {subject}\nBody: {clean_body}")

    
    classification = classify_email(clean_body)
    print(f"Email classified as: {classification}")

    destination_folder = None
    # should_update_contacts = False

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
            print(f"Moved email to '{destination_folder}'")
        else:
            print(f"Failed to determine folder ID for: {destination_folder}")
    else:
        print("Keeping email in Inbox")
