"""Deploy the Lab 05 AWS stack."""

from stack.clients import AWSClients
from stack.config import Settings
from stack.runner import create_stack


def main():
    settings = Settings.from_file(".env")
    clients = AWSClients(settings.region)

    outputs = create_stack(clients, settings)

    print("Stack created successfully!")
    print("Uploader URL:", outputs["uploader_url"])
    print("Viewer URL:", outputs["viewer_url"])


if __name__ == "__main__":
    main()
