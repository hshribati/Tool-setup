"""Estimate Final Weather Advisor project costs."""

import argparse
import os
from decimal import Decimal

from dotenv import dotenv_values

BUDGET_USD = Decimal("2.00")
ESTIMATED_STACK_HOURLY_USD = Decimal("0.07")


def calculate_budget(hours, gemini_calls, extra_cost):
    """Calculate estimated project costs."""
    if hours < 0 or gemini_calls < 0 or extra_cost < 0:
        raise ValueError("Usage values cannot be negative.")

    stack_cost = hours * ESTIMATED_STACK_HOURLY_USD
    total_cost = stack_cost + extra_cost

    return {
        "stack_cost": stack_cost,
        "extra_cost": extra_cost,
        "total_cost": total_cost,
        "remaining": BUDGET_USD - total_cost,
        "gemini_calls": gemini_calls,
    }


def main():
    """Display the project budget report."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hours",
        type=Decimal,
        required=True,
        help="Total hours the AWS stack was running",
    )
    parser.add_argument(
        "--gemini-calls",
        type=int,
        required=True,
        help="Total Gemini API calls",
    )
    parser.add_argument(
        "--extra-cost",
        type=Decimal,
        default=Decimal("0"),
        help="Other AWS or API costs in USD",
    )

    args = parser.parse_args()
    settings = dotenv_values(".env")

    result = calculate_budget(
        args.hours,
        args.gemini_calls,
        args.extra_cost,
    )

    print("\nFINAL WEATHER ADVISOR - BUDGET REPORT")
    print("-------------------------------------")
    print("AWS Region:", settings.get("AWS_REGION", "unknown"))
    print("EC2 Type:", settings.get("INSTANCE_TYPE", "unknown"))
    print("Gemini Model:", settings.get("GEMINI_MODEL", "unknown"))
    print("Stack Hours:", args.hours)
    print("Gemini Calls:", result["gemini_calls"])
    print("Estimated Stack Cost: ${:.2f}".format(result["stack_cost"]))
    print("Other Costs: ${:.2f}".format(result["extra_cost"]))
    print("Estimated Total: ${:.2f}".format(result["total_cost"]))
    print("Project Budget: ${:.2f}".format(BUDGET_USD))
    print("Remaining Budget: ${:.2f}".format(result["remaining"]))

    if result["total_cost"] <= BUDGET_USD:
        print("Budget Status: WITHIN ESTIMATE")
    else:
        print("Budget Status: OVER ESTIMATE")

    print("\nNote: Uses an estimated $0.07/hour stack rate.")
    print("Check AWS billing for actual charges.")


if __name__ == "__main__":
    main()
