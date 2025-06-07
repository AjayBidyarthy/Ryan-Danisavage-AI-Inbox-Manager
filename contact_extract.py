import json
import logging
from openai import OpenAI
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

def extract_new_contact_info(email_body: str) -> dict:
    prompt = f"""
You are an assistant that extracts contact information from emails.

Given the following email content, extract the new contact's name and email address provided by the sender.

Email:
\"\"\"
{email_body}
\"\"\"

Respond in the following JSON format:
{{
  "new_contact_name": "Full Name",
  "new_contact_email": "email@example.com"
}}
leave empty for any entry that is not found and move to next line
Only respond with the JSON object and nothing else.
"""
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=100,
        temperature=0.3
    )
    content = response.choices[0].message.content.strip()
    content = content.strip("`").strip()
    try:
        # Use json.loads instead of eval for security
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error parsing contact info: {e}\nResponse was: {content}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error parsing contact info: {e}")
        return {}
