"""Delete the Lab 05 AWS stack."""

from stack.clients import AWSClients
from stack.config import Settings
from stack.runner import delete_stack


def main():
    settings = Settings.from_file(".env")
    clients = AWSClients(settings.region)

    delete_stack(clients, settings)

    print("Stack deletion requested successfully!")


if __name__ == "__main__":
    main()
