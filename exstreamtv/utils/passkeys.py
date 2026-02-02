"""Apple Passkey (WebAuthn) support for authentication"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from webauthn import (
        generate_authentication_options,
        generate_registration_options,
        options_to_json,
        verify_authentication_response,
        verify_registration_response,
    )
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
    from webauthn.helpers.cose import COSEAlgorithmIdentifier
    from webauthn.helpers.structs import (
        AttestationConveyancePreference,
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        PublicKeyCredentialType,
        UserVerificationRequirement,
    )

    WEBAUTHN_AVAILABLE = True
except ImportError:
    WEBAUTHN_AVAILABLE = False
    logger.warning("webauthn library not installed. Install with: pip install webauthn")


class PasskeyManager:
    """Manages Passkey (WebAuthn) authentication"""

    def __init__(
        self,
        rp_id: str = "localhost",
        rp_name: str = "StreamTV",
        credentials_file: Path | None = None,
    ):
        """
        Initialize Passkey Manager

        Args:
            rp_id: Relying Party ID (domain name, e.g., "localhost" or "streamtv.example.com")
            rp_name: Relying Party name (display name)
            credentials_file: Path to file for persistent credential storage
        """
        if not WEBAUTHN_AVAILABLE:
            raise ImportError("webauthn library is required. Install with: pip install webauthn")

        self.rp_id = rp_id
        self.rp_name = rp_name
        self._challenges: dict[str, dict] = {}  # Store challenges temporarily
        self._credentials: dict[str, dict] = {}  # Store registered credentials
        self.credentials_file = credentials_file or Path("data/passkeys.json")

        # Load existing credentials
        self._load_credentials()

    def generate_registration_challenge(
        self, username: str, user_id: bytes | None = None
    ) -> dict[str, Any]:
        """
        Generate registration challenge for Passkey creation.
        Returns challenge data to send to client.
        """
        if not WEBAUTHN_AVAILABLE:
            raise ImportError("webauthn library not available")

        # Generate user ID if not provided
        if user_id is None:
            user_id = hashlib.sha256(username.encode()).digest()

        # Generate registration options
        registration_options = generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=user_id,
            user_name=username,
            user_display_name=username,
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.PREFERRED,
                authenticator_attachment=None,  # Allow any authenticator (including platform authenticators for Passkeys)
            ),
            attestation=AttestationConveyancePreference.NONE,
            supported_pub_key_algs=[
                COSEAlgorithmIdentifier.ECDSA_WITH_SHA256,
                COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_WITH_SHA256,
            ],
        )

        # Extract challenge for storage
        challenge_b64 = bytes_to_base64url(registration_options.challenge)

        # Store challenge
        self._challenges[challenge_b64] = {
            "type": "registration",
            "username": username,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "rp_id": self.rp_id,
        }

        # Convert to JSON-serializable format
        options_dict = json.loads(options_to_json(registration_options))

        return options_dict

    def verify_registration(
        self, challenge: str, credential: dict[str, Any], expected_origin: str
    ) -> dict[str, Any]:
        """
        Verify Passkey registration response.
        Returns credential data to store.
        """
        if not WEBAUTHN_AVAILABLE:
            raise ImportError("webauthn library not available")

        if challenge not in self._challenges:
            raise ValueError("Invalid or expired challenge")

        challenge_data = self._challenges[challenge]
        if challenge_data["type"] != "registration":
            raise ValueError("Challenge type mismatch")

        # Check challenge expiration (5 minutes)
        if (datetime.utcnow() - challenge_data["timestamp"]).total_seconds() > 300:
            del self._challenges[challenge]
            raise ValueError("Challenge expired")

        try:
            # Convert credential dict to proper format for verification
            from webauthn.helpers.structs import RegistrationCredential

            # Reconstruct the credential from the JSON
            # Credential data comes as base64url encoded strings
            credential_id_bytes = base64url_to_bytes(credential["id"])
            client_data_json = base64url_to_bytes(credential["response"]["clientDataJSON"])
            attestation_object = base64url_to_bytes(credential["response"]["attestationObject"])

            registration_credential = RegistrationCredential(
                id=credential_id_bytes,
                raw_id=credential_id_bytes,
                response=RegistrationCredential.Response(
                    client_data_json=client_data_json, attestation_object=attestation_object
                ),
                type=PublicKeyCredentialType.PUBLIC_KEY,
            )

            # Get the original challenge from stored challenge data
            # The challenge parameter is the base64url encoded challenge
            expected_challenge_bytes = base64url_to_bytes(challenge)

            # Verify registration
            verification = verify_registration_response(
                credential=registration_credential,
                expected_challenge=expected_challenge_bytes,
                expected_rp_id=self.rp_id,
                expected_origin=expected_origin,
            )

            # Store credential
            username = challenge_data["username"]
            credential_id_b64 = bytes_to_base64url(verification.credential_id)

            self._credentials[username] = {
                "id": credential_id_b64,
                "public_key": bytes_to_base64url(verification.credential_public_key),
                "sign_count": verification.sign_count,
                "created_at": datetime.utcnow().isoformat(),
            }

            # Save credentials to file
            self._save_credentials()

            # Clean up challenge
            del self._challenges[challenge]

            return {"username": username, "credential_id": credential_id_b64, "status": "verified"}

        except Exception as e:
            logger.exception(f"Passkey registration verification failed: {e}")
            raise ValueError(f"Registration verification failed: {e!s}")

    def generate_authentication_challenge(self, username: str | None = None) -> dict[str, Any]:
        """
        Generate authentication challenge for Passkey verification.
        Returns challenge data to send to client.
        """
        if not WEBAUTHN_AVAILABLE:
            raise ImportError("webauthn library not available")

        # Get credentials for user (if username provided) or allow any
        allowed_credentials = []
        if username and username in self._credentials:
            cred = self._credentials[username]
            try:
                cred_id_bytes = base64url_to_bytes(cred["id"])
                allowed_credentials.append(
                    PublicKeyCredentialDescriptor(
                        id=cred_id_bytes, type=PublicKeyCredentialType.PUBLIC_KEY
                    )
                )
            except Exception as e:
                logger.warning(f"Error processing credential for {username}: {e}")
        else:
            # Allow any registered credential
            for cred in self._credentials.values():
                try:
                    cred_id_bytes = base64url_to_bytes(cred["id"])
                    allowed_credentials.append(
                        PublicKeyCredentialDescriptor(
                            id=cred_id_bytes, type=PublicKeyCredentialType.PUBLIC_KEY
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error processing credential: {e}")
                    continue

        # Generate authentication options
        authentication_options = generate_authentication_options(
            rp_id=self.rp_id,
            allow_credentials=allowed_credentials if allowed_credentials else None,
            user_verification=UserVerificationRequirement.PREFERRED,
        )

        # Extract challenge for storage
        challenge_b64 = bytes_to_base64url(authentication_options.challenge)

        # Store challenge
        self._challenges[challenge_b64] = {
            "type": "authentication",
            "username": username,
            "timestamp": datetime.utcnow(),
            "rp_id": self.rp_id,
        }

        # Convert to JSON-serializable format
        options_dict = json.loads(options_to_json(authentication_options))

        return options_dict

    def verify_authentication(
        self, challenge: str, credential: dict[str, Any], expected_origin: str
    ) -> dict[str, Any]:
        """
        Verify Passkey authentication response.
        Returns authentication result.
        """
        if not WEBAUTHN_AVAILABLE:
            raise ImportError("webauthn library not available")

        if challenge not in self._challenges:
            raise ValueError("Invalid or expired challenge")

        challenge_data = self._challenges[challenge]
        if challenge_data["type"] != "authentication":
            raise ValueError("Challenge type mismatch")

        # Check challenge expiration (5 minutes)
        if (datetime.utcnow() - challenge_data["timestamp"]).total_seconds() > 300:
            del self._challenges[challenge]
            raise ValueError("Challenge expired")

        credential_id = credential.get("id")
        if not credential_id:
            raise ValueError("Missing credential ID")

        # Find matching credential
        username = None
        stored_credential = None
        for uname, cred in self._credentials.items():
            if cred["id"] == credential_id:
                username = uname
                stored_credential = cred
                break

        if not username or not stored_credential:
            raise ValueError("Credential not found")

        try:
            # Convert credential dict to proper format for verification
            from webauthn.helpers.structs import AuthenticationCredential

            # Reconstruct the credential from the JSON
            # Credential data comes as base64url encoded strings
            credential_id_bytes = base64url_to_bytes(credential["id"])
            client_data_json = base64url_to_bytes(credential["response"]["clientDataJSON"])
            authenticator_data = base64url_to_bytes(credential["response"]["authenticatorData"])
            signature = base64url_to_bytes(credential["response"]["signature"])
            user_handle = (
                base64url_to_bytes(credential["response"]["userHandle"])
                if credential["response"].get("userHandle")
                else None
            )

            authentication_credential = AuthenticationCredential(
                id=credential_id_bytes,
                raw_id=credential_id_bytes,
                response=AuthenticationCredential.Response(
                    client_data_json=client_data_json,
                    authenticator_data=authenticator_data,
                    signature=signature,
                    user_handle=user_handle,
                ),
                type=PublicKeyCredentialType.PUBLIC_KEY,
            )

            # Get the original challenge from stored challenge data
            # The challenge parameter is the base64url encoded challenge
            expected_challenge_bytes = base64url_to_bytes(challenge)

            # Verify authentication
            verification = verify_authentication_response(
                credential=authentication_credential,
                expected_challenge=expected_challenge_bytes,
                expected_rp_id=self.rp_id,
                expected_origin=expected_origin,
                credential_public_key=base64url_to_bytes(stored_credential["public_key"]),
                credential_current_sign_count=stored_credential.get("sign_count", 0),
            )

            # Update sign count
            stored_credential["sign_count"] = verification.new_sign_count

            # Save updated credentials
            self._save_credentials()

            # Clean up challenge
            del self._challenges[challenge]

            return {
                "username": username,
                "credential_id": credential_id,
                "status": "verified",
                "authenticated": True,
            }

        except Exception as e:
            logger.exception(f"Passkey authentication verification failed: {e}")
            raise ValueError(f"Authentication verification failed: {e!s}")

    def has_passkey(self, username: str) -> bool:
        """Check if user has a registered Passkey"""
        return username in self._credentials

    def delete_passkey(self, username: str) -> bool:
        """Delete a registered Passkey"""
        if username in self._credentials:
            del self._credentials[username]
            self._save_credentials()
            return True
        return False

    def _load_credentials(self):
        """Load credentials from file"""
        if self.credentials_file.exists():
            try:
                with open(self.credentials_file) as f:
                    self._credentials = json.load(f)
                logger.info(f"Loaded {len(self._credentials)} Passkey credentials")
            except Exception as e:
                logger.warning(f"Failed to load Passkey credentials: {e}")
                self._credentials = {}
        else:
            # Create directory if needed
            self.credentials_file.parent.mkdir(parents=True, exist_ok=True)

    def _save_credentials(self):
        """Save credentials to file"""
        try:
            with open(self.credentials_file, "w") as f:
                json.dump(self._credentials, f, indent=2)
        except Exception as e:
            logger.exception(f"Failed to save Passkey credentials: {e}")
