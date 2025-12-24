from twilio.rest import Client
import os 

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_otp(identifier: str, channel: str):
    """
    identifier: +91XXXXXXXXXX or email
    channel: sms | email
    """
    client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID) \
        .verifications \
        .create(to=identifier, channel=channel)
def verify_otp(identifier: str, code: str) -> bool:
    check = client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID) \
        .verification_checks \
        .create(to=identifier, code=code)
    return check.status == "approved"

