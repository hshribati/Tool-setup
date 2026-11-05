
"""Create the Lab 06 Weather and Advisor application stack."""

from stack.clients import AWSClients
from stack.config import Settings
from stack.runner import create_stack


def main():
    settings = Settings.from_file(".env")
    clients = AWSClients(settings.region)

    print("Creating Lab 06 application stack...")

    outputs = create_stack(clients, settings)

    print("Application stack created.")
    print("Weather URL:", outputs["weather_url"])
    print("Advisor URL:", outputs["advisor_url"])


if __name__ == "__main__":
    main()

