"""
Simple checker for required environment/config values used by the app.
Run from the project folder with the venv active:

    python check_config.py

It will print the values (masked where appropriate) and list any missing/empty.
"""
from config import settings

REQUIRED = [
    "NOCODB_URL",
    "NOCO_XC_TOKEN",
    "NOCO_PROJECT_ID",
    "NOCO_PARAMETROS_TABLE",
    "NOCO_INSUMO_TABLE",
    "NOCO_BASE_TRABAJO_TABLE",
    "RUNT_URL",
    "RUNT_USERNAME",
    "RUNT_PASSWORD",
]

OPTIONAL_EMAIL = [
    "CLIENT_ID",
    "CLIENT_SECRET",
    "TENANT_ID",
    "AUTHORITY",
    "SCOPE",
    "USER_EMAIL",
    "RECEIVER_EMAIL",
]


def mask(s: str | None) -> str:
    if not s:
        return "<EMPTY>"
    if len(s) <= 8:
        return "*" * len(s)
    return s[:4] + "..." + s[-4:]


def main():
    print("Checking required settings from `config.Settings` (loaded from .env)")
    missing = []
    for k in REQUIRED:
        v = getattr(settings, k, None)
        print(f"{k}: {mask(v)}")
        if not v:
            missing.append(k)

    if missing:
        print("\nMissing required settings:")
        for m in missing:
            print(" - ", m)
        print("\nPlease set them in your .env or environment and restart the app.")
    else:
        print("\nAll required settings present.")

    print('\nEmail-related (optional):')
    for k in OPTIONAL_EMAIL:
        v = getattr(settings, k, None)
        print(f"{k}: {mask(v)}")


if __name__ == '__main__':
    main()
