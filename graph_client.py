import msal
import requests
import datetime
import logging
from config import CLIENT_ID, CLIENT_SECRET, TENANT_ID, GRAPH_SCOPE

logger = logging.getLogger(__name__)

class GraphClient:
    def __init__(self):
        self.token = None
        self.get_token()

    def get_token(self):
        authority = f"https://login.microsoftonline.com/{TENANT_ID}"
        app = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=authority, client_credential=CLIENT_SECRET
        )
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        if "access_token" in result:
            self.token = result["access_token"]
        else:
            raise Exception("Could not obtain access token: " + str(result))

    def subscribe_to_mail(self, notification_url, user_email):
        # 1) Compute expiration 2 days from now in UTC, no microseconds:
        expiration = (datetime.datetime.now() + datetime.timedelta(days=2)).replace(microsecond=0).isoformat() + "Z"

        resource = f"users/{user_email}/mailFolders('Inbox')/messages"
        payload = {
            "changeType": "created",
            "notificationUrl": notification_url,
            "resource": resource,
            "expirationDateTime": expiration,
            "clientState": "secretClientValue"
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        resp = requests.post(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers=headers,
            json=payload
        )

        if resp.status_code in (200, 201):
            logger.info("Webhook subscription created!")
            return resp.json()
        else:
            logger.error("Failed to create subscription: %s %s", resp.status_code, resp.text)
            return None

    def get_inbox_folder_id(self, user_email):
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/Inbox"
        response = requests.get(url, headers={"Authorization": f"Bearer {self.token}"})
        return response.json().get("id")

    def get_or_create_subfolder(self, user_email, folder_name):
        inbox_id = self.get_inbox_folder_id(user_email)

        # Get existing folders
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/{inbox_id}/childFolders"
        response = requests.get(url, headers={"Authorization": f"Bearer {self.token}"})
        if response.status_code != 200:
            logger.error("Error listing folders: %s", response.text)
            return None

        folders = response.json().get("value", [])
        for f in folders:
            if f["displayName"].lower() == folder_name.lower():
                return f["id"]

        # Create folder if not exists
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/{inbox_id}/childFolders"
        response = requests.post(url, json={"displayName": folder_name}, headers={"Authorization": f"Bearer {self.token}"})
        if response.status_code == 201:
            return response.json().get("id")
        else:
            logger.error("Failed to create folder: %s", response.text)
            return None

    def move_email_to_folder(self, user_email, message_id, destination_folder_id):
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/move"
        response = requests.post(url, json={"destinationId": destination_folder_id}, headers={"Authorization": f"Bearer {self.token}"})
        if response.status_code not in [200, 201]:
            logger.error("Error moving email %s: %s", message_id, response.text)

    def unsubscribe(self, subscription_id):
        """
        Deletes a subscription by its ID.
        Returns True if successful, False otherwise.
        """
        if not self.token:
            self.get_token()

        url = f"https://graph.microsoft.com/v1.0/subscriptions/{subscription_id}"
        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        resp = requests.delete(url, headers=headers)
        if resp.status_code == 204:
            logger.info("Subscription %s successfully deleted", subscription_id)
            return True
        else:
            logger.error("Failed to delete subscription %s: %s %s", subscription_id, resp.status_code, resp.text)
            # In case the token expired, try refreshing once
            if resp.status_code == 401:
                self.get_token()
                resp = requests.delete(url, headers={"Authorization": f"Bearer {self.token}"})
                if resp.status_code == 204:
                    logger.info("Subscription %s successfully deleted after token refresh.", subscription_id)
                    return True
            return False