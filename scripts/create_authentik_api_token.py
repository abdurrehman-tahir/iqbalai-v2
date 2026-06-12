"""Create an Authentik API token for IqbalAI invite/user management.

Run once (idempotent — replaces prior token with the same description):

    docker compose exec -T authentik-server ak shell < scripts/create_authentik_api_token.py

Copy the printed token into `.env` as AUTHENTIK_API_TOKEN, then restart the API:

    docker compose up -d api
"""

from authentik.core.models import Token, TokenIntents, User

DESCRIPTION = "IqbalAI API"

# `is_superuser` is a computed property on Authentik's User (derived from group
# membership), NOT a queryable DB field — filtering on it raises FieldError. Look up
# the default admin by username, then fall back to any user whose group grants superuser.
user = User.objects.filter(username="akadmin").first()
if user is None:
    user = next((u for u in User.objects.all() if u.is_superuser), None)
if user is None:
    raise SystemExit("No Authentik superuser found — complete initial setup first.")

Token.objects.filter(description=DESCRIPTION, intent=TokenIntents.INTENT_API).delete()
token = Token.objects.create(
    user=user,
    intent=TokenIntents.INTENT_API,
    description=DESCRIPTION,
    expiring=False,  # long-lived service token; rotate via re-running this script
)

print("")
print("=== Authentik API token (Intent: API) ===")
print(token.key)
print("=== Add to .env as AUTHENTIK_API_TOKEN, then: docker compose up -d api ===")
print("")
