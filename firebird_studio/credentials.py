from __future__ import annotations

SERVICE_NAME = "firebird-maintenance-studio"


class CredentialStore:
    """Small adapter around Windows Credential Manager via keyring."""

    def __init__(self, service_name: str = SERVICE_NAME):
        self.service_name = service_name

    def get(self, profile_name: str) -> str | None:
        import keyring

        return keyring.get_password(self.service_name, profile_name)

    def set(self, profile_name: str, password: str) -> None:
        import keyring

        keyring.set_password(self.service_name, profile_name, password)

    def delete(self, profile_name: str) -> None:
        import keyring

        try:
            keyring.delete_password(self.service_name, profile_name)
        except keyring.errors.PasswordDeleteError:
            pass
