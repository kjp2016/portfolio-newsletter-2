#gmail_auth_test.py
import smtplib
import logging

# ---------- Configuration ----------
smtp_server = "smtp.gmail.com"
smtp_port = 587
sender_email = "keanejpalmer@gmail.com"  # Your Gmail address
sender_password = st.secrets["GMAIL_APP_PASSWORD"]

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S"
)

def test_gmail_auth():
    """Test Gmail authentication."""
    try:
        logging.info("Connecting to Gmail SMTP server...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Secure the connection
            logging.info("Starting TLS encryption...")
            # Try to log in
            server.login(sender_email, sender_password)
            logging.info("Successfully authenticated with Gmail!")
    except smtplib.SMTPAuthenticationError as e:
        # Print detailed error message
        logging.error(f"SMTP Authentication failed: {e.smtp_error.decode()}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_gmail_auth()
