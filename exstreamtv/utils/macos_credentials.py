"""macOS-specific credential input using AppleScript dialogs"""

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def is_macos() -> bool:
    """Check if running on macOS"""
    return platform.system() == "Darwin"


def show_credentials_dialog(title: str, message: str) -> tuple[str, str] | None:
    """
    Show AppleScript dialog to get username and password.
    Returns (username, password) tuple or None if cancelled.
    """
    if not is_macos():
        logger.warning("AppleScript dialogs are only available on macOS")
        return None

    # AppleScript to show username/password dialog

    try:
        # First, get username
        username_script = f'''
        tell application "System Events"
            activate
            set theResponse to display dialog "Enter your {title} username:" ¬
                with title "{title} - Username" ¬
                with icon note ¬
                default answer "" ¬
                buttons {{"Cancel", "OK"}} ¬
                default button "OK"
            set theUsername to text returned of theResponse
        end tell
        return theUsername
        '''

        result = subprocess.run(
            ["osascript", "-e", username_script],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.info("User cancelled username dialog")
            return None

        username = result.stdout.strip()
        if not username:
            logger.warning("Empty username provided")
            return None

        # Then, get password
        password_script = f'''
        tell application "System Events"
            activate
            set theResponse to display dialog "Enter your {title} password:" ¬
                with title "{title} - Password" ¬
                with icon note ¬
                default answer "" ¬
                buttons {{"Cancel", "OK"}} ¬
                default button "OK" ¬
                with hidden answer
            set thePassword to text returned of theResponse
        end tell
        return thePassword
        '''

        result = subprocess.run(
            ["osascript", "-e", password_script],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.info("User cancelled password dialog")
            return None

        password = result.stdout.strip()
        if not password:
            logger.warning("Empty password provided")
            return None

        return (username, password)

    except subprocess.TimeoutExpired:
        logger.exception("Dialog timeout - user took too long to respond")
        return None
    except Exception as e:
        logger.exception(f"Error showing credentials dialog: {e}")
        return None


def get_archive_org_credentials() -> tuple[str, str] | None:
    """
    Prompt user for Archive.org credentials using AppleScript dialog.
    Returns (username, password) tuple or None if cancelled/not macOS.
    """
    if not is_macos():
        logger.debug("Not running on macOS, skipping AppleScript dialog")
        return None

    message = (
        "Some Archive.org media requires authentication to view.\n\n"
        "Please enter your Archive.org credentials.\n\n"
        "These will be used to access restricted content."
    )

    credentials = show_credentials_dialog(title="Archive.org Authentication", message=message)

    if credentials:
        logger.info("Archive.org credentials obtained via AppleScript dialog")
        return credentials
    else:
        logger.info("Archive.org credentials not provided or dialog cancelled")
        return None


def store_credentials_in_keychain(service: str, username: str, password: str) -> bool:
    """
    Store credentials in macOS Keychain using security command.
    Returns True if successful, False otherwise.
    """
    if not is_macos():
        return False

    try:
        # Use security command to add to keychain
        # This will update if it already exists
        subprocess.run(
            [
                "security",
                "add-internet-password",
                "-a",
                username,
                "-s",
                service,
                "-w",
                password,
                "-U",  # Update if exists
            ],
            capture_output=True,
            check=True,
            timeout=10,
        )
        logger.info(f"Stored credentials in Keychain for {service}")
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to store credentials in Keychain: {e}")
        return False
    except Exception as e:
        logger.exception(f"Error storing credentials in Keychain: {e}")
        return False


def get_credentials_from_keychain(service: str) -> tuple[str, str] | None:
    """
    Retrieve credentials from macOS Keychain.
    Returns (username, password) tuple or None if not found.
    """
    if not is_macos():
        return None

    try:
        # Get password from keychain
        result = subprocess.run(
            [
                "security",
                "find-internet-password",
                "-s",
                service,
                "-w",  # Print password only
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return None

        password = result.stdout.strip()
        if not password:
            return None

        # Get account (username) from keychain
        account_result = subprocess.run(
            [
                "security",
                "find-internet-password",
                "-s",
                service,
                "-g",  # Show keychain item
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Parse account from output (format: "keychain: "acct"<blob>="username"")
        username = None
        for line in account_result.stdout.split("\n"):
            if "acct" in line and "=" in line:
                parts = line.split("=")
                if len(parts) > 1:
                    username = parts[1].strip().strip('"')
                    break

        if username and password:
            return (username, password)

        return None

    except subprocess.CalledProcessError:
        # Not found in keychain
        return None
    except Exception as e:
        logger.exception(f"Error retrieving credentials from Keychain: {e}")
        return None
