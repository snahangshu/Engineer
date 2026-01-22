import httpx
import os

INTERAKT_API_KEY = os.getenv("INTERAKT_API_KEY")
INTERAKT_BASE_URL = os.getenv("INTERAKT_BASE_URL")


async def send_whatsapp_message(
    phone: str,
    template_name: str,
    params: list[str]
):
    """
    phone: '919876543210'
    template_name: approved template name
    params: template variables in order
    """

    payload = {
        "phoneNumber": phone,
        "countryCode": "91",
        "type": "Template",
        "template": {
            "name": template_name,
            "languageCode": "en",
            "bodyValues": params
        }
    }

    headers = {
        "Authorization": f"Basic {INTERAKT_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{INTERAKT_BASE_URL}/message/",
            json=payload,
            headers=headers
        )

    if response.status_code not in (200, 201):
        print("❌ WhatsApp Error:", response.text)
        return False

    return True
