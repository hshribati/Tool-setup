
"""Configuration for the Lab 06 Weather Advisor AWS stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_KEYS = [
    "AWS_REGION",
    "AZ_A",
    "AZ_B",
    "AMI_ID",
    "INSTANCE_TYPE",
    "APP_SECURITY_GROUP_ID",
    "KEY_NAME",
    "WEATHER_ROLE_NAME",
    "WEATHER_PROFILE_NAME",
    "WEATHER_LT_NAME",
    "WEATHER_TG_NAME",
    "WEATHER_ASG_NAME",
    "WEATHER_LISTENER_PORT",
    "ADVISOR_ROLE_NAME",
    "ADVISOR_PROFILE_NAME",
    "ADVISOR_LT_NAME",
    "ADVISOR_TG_NAME",
    "ADVISOR_ASG_NAME",
    "ADVISOR_LISTENER_PORT",
    "ALB_NAME",
    "ALB_SG_NAME",
    "DB_INSTANCE_ID",
    "DB_NAME",
    "DB_USER",
    "DB_SG_NAME",
    "DB_SUBNET_GROUP_NAME",
    "DB_PASSWORD_PARAM",
    "CACHE_SECONDS",
    "GEMINI_PARAM_NAME",
    "GEMINI_MODEL",
    "KEY_CACHE_SECONDS",
    "CONTACT_EMAIL",
]


class ConfigError(Exception):
    """Raised when required settings are missing or invalid."""


def load_dotenv(path: str | Path = ".env") -> dict[str, str]:
    values = {}

    for raw in Path(path).read_text().splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


@dataclass(frozen=True)
class Tier:
    name: str
    role_name: str
    profile_name: str
    lt_name: str
    tg_name: str
    asg_name: str
    listener_port: int
    app_dir: Path

    @property
    def policy_name(self) -> str:
        return f"{self.role_name}-policy"

    @property
    def service_name(self) -> str:
        return self.name


@dataclass(frozen=True)
class Settings:
    region: str
    az_a: str
    az_b: str
    ami_id: str
    instance_type: str
    app_sg_id: str
    key_name: str

    alb_name: str
    alb_sg_name: str

    db_instance_id: str
    db_name: str
    db_user: str
    db_sg_name: str
    db_subnet_group_name: str
    db_password_param: str

    cache_seconds: int
    gemini_param_name: str
    gemini_model: str
    key_cache_seconds: int
    contact_email: str

    weather: Tier
    advisor: Tier

    app_port: int = 3000

    @property
    def tiers(self) -> tuple[Tier, Tier]:
        return (self.weather, self.advisor)

    def tier(self, name: str) -> Tier:
        return {
            "weather": self.weather,
            "advisor": self.advisor,
        }[name]

    @classmethod
    def from_values(
        cls,
        v: dict[str, str],
        base_dir: str | Path = ".",
    ) -> "Settings":

        missing = [key for key in REQUIRED_KEYS if not v.get(key)]

        if missing:
            raise ConfigError(
                "Missing keys in .env: " + ", ".join(missing)
            )

        base = Path(base_dir)

        def tier(prefix: str) -> Tier:
            return Tier(
                name=prefix.lower(),
                role_name=v[f"{prefix}_ROLE_NAME"],
                profile_name=v[f"{prefix}_PROFILE_NAME"],
                lt_name=v[f"{prefix}_LT_NAME"],
                tg_name=v[f"{prefix}_TG_NAME"],
                asg_name=v[f"{prefix}_ASG_NAME"],
                listener_port=int(v[f"{prefix}_LISTENER_PORT"]),
                app_dir=base / f"{prefix.lower()}-app",
            )

        return cls(
            region=v["AWS_REGION"],
            az_a=v["AZ_A"],
            az_b=v["AZ_B"],
            ami_id=v["AMI_ID"],
            instance_type=v["INSTANCE_TYPE"],
            app_sg_id=v["APP_SECURITY_GROUP_ID"],
            key_name=v["KEY_NAME"],

            alb_name=v["ALB_NAME"],
            alb_sg_name=v["ALB_SG_NAME"],

            db_instance_id=v["DB_INSTANCE_ID"],
            db_name=v["DB_NAME"],
            db_user=v["DB_USER"],
            db_sg_name=v["DB_SG_NAME"],
            db_subnet_group_name=v["DB_SUBNET_GROUP_NAME"],
            db_password_param=v["DB_PASSWORD_PARAM"],

            cache_seconds=int(v["CACHE_SECONDS"]),
            gemini_param_name=v["GEMINI_PARAM_NAME"],
            gemini_model=v["GEMINI_MODEL"],
            key_cache_seconds=int(v["KEY_CACHE_SECONDS"]),
            contact_email=v["CONTACT_EMAIL"],

            weather=tier("WEATHER"),
            advisor=tier("ADVISOR"),
        )

    @classmethod
    def from_file(
        cls,
        path: str | Path = ".env",
    ) -> "Settings":

        path = Path(path)

        return cls.from_values(
            load_dotenv(path),
            base_dir=path.resolve().parent,
        )

