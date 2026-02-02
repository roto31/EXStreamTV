"""Authentication status checker and re-prompting"""

import logging

logger = logging.getLogger(__name__)


async def check_and_renew_archive_org_auth(
    stream_manager,
    config,
    is_macos_func,
    check_swiftdialog_func,
    show_login_func,
    store_keychain_func,
) -> bool:
    """
    Check Archive.org authentication and re-prompt if needed.
    Returns True if authenticated, False otherwise.
    """
    if not config.archive_org.use_authentication or not config.archive_org.username:
        return False

    try:
        auth_valid = await stream_manager.archive_org_adapter.check_authentication()

        if not auth_valid:
            logger.warning("Archive.org authentication failed or expired")

            # Re-prompt for credentials on macOS
            if is_macos_func() and check_swiftdialog_func():
                logger.info("Re-prompting for Archive.org credentials...")
                credentials = show_login_func()

                if credentials:
                    username, password = credentials
                    config.archive_org.username = username
                    config.archive_org.password = password
                    stream_manager.update_archive_org_credentials(username, password)

                    # Store in keychain
                    if store_keychain_func("archive.org", username, password):
                        logger.info("Updated Archive.org credentials in Keychain")

                    # Verify new credentials
                    auth_valid = await stream_manager.archive_org_adapter.check_authentication()
                    if auth_valid:
                        logger.info("Successfully re-authenticated with Archive.org")
                        return True
                    else:
                        logger.error("Re-authentication failed with new credentials")
                        return False
                else:
                    logger.warning("User cancelled Archive.org re-authentication")
                    return False
            else:
                logger.warning(
                    "Cannot re-prompt for credentials (not macOS or SwiftDialog not available)"
                )
                return False

        return auth_valid

    except Exception as e:
        logger.exception(f"Error checking Archive.org authentication: {e}")
        return False
