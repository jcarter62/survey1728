import os
import logging
from dotenv import load_dotenv
import yagmail

load_dotenv()

# router = APIRouter()
logger = logging.getLogger(__name__)

class EMailSender:

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.default_from = os.getenv("SMTP_FROM", self.smtp_user)

    def __del__(self):
        self.smtp_host = None
        self.smtp_port = None
        self.smtp_user = None
        self.smtp_pass = None
        self.default_from = None

    def send_email(self,to_address: str, subject: str = '', body: str = '', html: bool = False):
        try:
            user = self.smtp_user
            password = self.smtp_pass

            yag = yagmail.SMTP(user=user, password=password)
            contents = body if not html else yagmail.inline(body)
            yag.send(to=to_address, subject=subject, contents=contents)
            yag.close()
            logger.exception("send to: %s", to_address)

        except Exception as exc:
            logger.exception("async send failed: %s", exc)
            raise

