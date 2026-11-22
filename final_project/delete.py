
"""Delete the Final Weather Advisor AWS application stack."""

from stack.clients import AWSClients
from stack.config import Settings
from stack.runner import delete_stack


def main():
    settings = Settings.from_file(".env")
    clients = AWSClients(settings.region)

    print("Deleting Final Weather Advisor AWS stack...")

    delete_stack(clients, settings)

    print("Application stack cleanup finished.")
    print("Check AWS to confirm all resources are deleted.")
    print("Note: Gemini SSM parameter is preserved.")


if __name__ == "__main__":
    main()
