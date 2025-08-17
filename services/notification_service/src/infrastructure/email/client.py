import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from src.config.config import config
from src.config.logger_config import log
from src.core.exceptions import ExternalServiceError


class EmailClient:
    """
    Client for sending emails via SMTP using Ethereal (or other SMTP providers).

    This class provides a simple interface to send emails through an SMTP server.
    It uses the configuration from the global config object for connection details.
    """

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """
        Send an email using the configured SMTP server.

        Args:
            to (str): Recipient email address
            subject (str): Email subject line
            body (str): Email body content

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self._validate_inputs(to, subject, body):
            return False

        msg = self._create_message(to, subject, body)
        if not msg:
            return False

        return self._send_message(to, subject, msg)

    def _validate_inputs(self, to: str, subject: str, body: str) -> bool:
        """Validate input parameters before sending email."""
        if not to or not isinstance(to, str) or "@" not in to:
            log.error("Invalid recipient email address", to=to)
            return False

        if not subject or not isinstance(subject, str):
            log.error("Email subject is required", subject=subject)
            return False

        if not body or not isinstance(body, str):
            log.error("Email body is required", body_length=len(body) if body else 0)
            return False

        return True

    def _create_message(
        self, to: str, subject: str, body: str
    ) -> Optional[MIMEMultipart]:
        """Create the email message object."""
        try:
            msg = MIMEMultipart()
            msg["From"] = config.EMAIL_USERNAME
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            return msg

        except Exception as e:
            log.critical(
                "Failed to create email message", to=to, subject=subject, error=str(e)
            )
            return None

    def _validate_config(self) -> None:
        """Validate that all required email configuration is present."""
        if not config.EMAIL_HOST:
            raise ExternalServiceError(
                "email-service", "EMAIL_HOST configuration is missing"
            )
        if not config.EMAIL_PORT:
            raise ExternalServiceError(
                "email-service", "EMAIL_PORT configuration is missing"
            )
        if not config.EMAIL_USERNAME:
            raise ExternalServiceError(
                "email-service", "EMAIL_USERNAME configuration is missing"
            )
        if not config.EMAIL_PASSWORD:
            raise ExternalServiceError(
                "email-service", "EMAIL_PASSWORD configuration is missing"
            )

    def _send_message(self, to: str, subject: str, msg: MIMEMultipart) -> bool:
        """Send the email message via SMTP."""
        server = None
        try:
            self._validate_config()
            server = self._connect_and_login()
            if not server:
                return False

            log.info("Sending email", to=to, subject=subject)
            server.send_message(msg)
            log.info("Email sent successfully", to=to, subject=subject)
            return True

        except (
            smtplib.SMTPException,
            ConnectionError,
            TimeoutError,
            ssl.SSLError,
        ) as e:
            return self._handle_smtp_error(e, to, subject)

        except ExternalServiceError:
            # Re-raise config errors
            raise

        except Exception as e:
            log.critical(
                "Unexpected error sending email",
                to=to,
                subject=subject,
                error=str(e),
                exc_info=True,
            )
            return False

        finally:
            self._close_connection(server)

    def _connect_and_login(self) -> Optional[smtplib.SMTP]:
        """Establish SMTP connection and authenticate."""
        try:
            log.debug(
                "Creating SMTP connection",
                host=config.EMAIL_HOST,
                port=config.EMAIL_PORT,
            )

            server = smtplib.SMTP(config.EMAIL_HOST, config.EMAIL_PORT, timeout=30)
            context = ssl.create_default_context()
            server.starttls(context=context)

            log.debug("Logging in to SMTP server", username=config.EMAIL_USERNAME)
            server.login(config.EMAIL_USERNAME, config.EMAIL_PASSWORD)

            return server

        except Exception as e:
            log.critical(
                "Failed to connect or login to SMTP server",
                host=config.EMAIL_HOST,
                port=config.EMAIL_PORT,
                error=str(e),
            )
            if "server" in locals():
                server.quit()
            return None

    def _handle_smtp_error(self, error: Exception, to: str, subject: str) -> bool:
        """Handle specific SMTP-related errors."""
        error_map = {
            smtplib.SMTPAuthenticationError: "SMTP authentication failed - check username and password",
            smtplib.SMTPConnectError: "Failed to connect to SMTP server",
            smtplib.SMTPServerDisconnected: "SMTP server disconnected unexpectedly",
            smtplib.SMTPRecipientsRefused: "SMTP server refused recipient",
            smtplib.SMTPSenderRefused: "SMTP server refused sender",
            smtplib.SMTPDataError: "SMTP server rejected email data",
            ssl.SSLError: "SSL/TLS connection error",
            TimeoutError: "Connection timeout to SMTP server",
            ConnectionRefusedError: "Connection refused by SMTP server",
        }

        error_type = type(error)
        log_fn = (
            log.critical
            if error_type
            in [
                smtplib.SMTPConnectError,
                smtplib.SMTPServerDisconnected,
                ConnectionRefusedError,
                TimeoutError,
            ]
            else log.warning
        )

        log_fn(
            error_map.get(error_type, "SMTP error occurred"),
            to=to,
            subject=subject,
            error=str(error),
        )
        return False

    def _close_connection(self, server: Optional[smtplib.SMTP]) -> None:
        """Safely close the SMTP connection."""
        if server:
            try:
                log.debug("Closing SMTP connection")
                server.quit()
            except Exception as e:
                log.warning("Error closing SMTP connection", error=str(e))
