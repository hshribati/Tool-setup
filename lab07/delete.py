
"""Delete the Lab 06 Weather and Advisor application stack."""

from stack.clients import AWSClients
from stack.config import Settings
from stack.runner import delete_stack


def main():
    settings = Settings.from_file(".env")
    clients = AWSClients(settings.region)

    print("Deleting Lab 06 application stack...")

    delete_stack(clients, settings)

    print("Application stack cleanup finished.")
    print("Check AWS to confirm all resources are deleted.")


if __name__ == "__main__":
    main()

