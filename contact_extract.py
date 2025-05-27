from openai import OpenAI
from config import OPENAI_API_KEY

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
"""
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=100,
        temperature=0.3
    )
    try:
        return eval(response.choices[0].message.content.strip())
    except Exception as e:
        print(f"Error parsing contact info: {e}")
        return {}
