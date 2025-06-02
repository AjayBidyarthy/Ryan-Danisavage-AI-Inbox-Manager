import logging
from config import OPENAI_API_KEY
from openai import OpenAI

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

prompt_template = """
You are an email classification assistant.

Classify the email content into ONE of the following four categories:

1. Not Interested  
→ The sender is expressing disinterest in your offering, without explicitly using words like “unsubscribe”.

2. Contact Changed  
→ The sender has left the company or is no longer in the relevant role, and has provided a new contact to follow up with.

3. Unsubscribe  
→ The sender is asking to stop receiving emails or expresses a desire to be removed from the mailing list. This includes phrases like "please remove me", "unsubscribe", or "do not include me in this campaign".

4. Primary  
→ All other cases. These include general replies, interested leads, or emails that do not clearly fit in the first three categories.

---

Respond with ONLY the category name: Not Interested, Contact Changed, Unsubscribe, or Primary.

Here is the email:

\"\"\"{email}\"\"\"
"""

def classify_email(email_text: str) -> str:
    try:
        messages = [{"role": "user", "content": prompt_template.format(email=email_text)}]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=20,
            temperature=0.3
        )
        classification = response.choices[0].message.content.strip()
        logger.info(f"Email classified as: {classification}")
        return classification
    except Exception as e:
        logger.error(f"Error during email classification: {e}")
        return "Primary"  # default fallback