"""Dev-only Authentik seed: one login-able user per role, password 'devpassword'.

Run inside the Authentik container (idempotent — safe to re-run):

    docker compose exec -T authentik-server ak shell < \
        infrastructure/authentik/seed_dev_accounts.py

Also installs a scope mapping on the 'profile' scope (already requested by the
frontend) so the JWT carries `role` + `tenant_type` from each user's attributes —
without it every login defaults to school/no-role. See core/tenant.py + core/
dependencies.py for the claim contract.

NOT for production: fixed weak password, self-set roles, bypasses the app's
independent_signup provisioning / ToS.
"""

from authentik.core.models import User
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

PASSWORD = "devpassword"
PROVIDER_NAME = "IqbalAI Frontend"

# (email, display name, role claim, tenant_type)
ACCOUNTS = [
    ("platform.admin@iqbalai.dev", "Platform Admin", "platform_admin", "school"),
    ("district.admin@iqbalai.dev", "District Admin", "district_admin", "school"),
    ("school.admin@iqbalai.dev", "School Admin", "school_admin", "school"),
    ("coordinator@iqbalai.dev", "Coordinator", "coordinator", "school"),
    ("teacher@iqbalai.dev", "Teacher", "teacher", "school"),
    ("student@iqbalai.dev", "Student", "student", "school"),
    ("parent@iqbalai.dev", "Parent", "parent", "school"),
    ("ind.teacher@iqbalai.dev", "Independent Teacher", "independent_teacher", "independent"),
    ("ind.student@iqbalai.dev", "Independent Student", "independent_student", "independent"),
]

# 1) Scope mapping that emits role + tenant_type into the token (profile scope).
# Single-line expression on purpose: `ak shell < file` runs stdin through a REPL
# that mis-parses multi-line parenthesised strings.
EXPRESSION = 'return {"role": user.attributes.get("role"), "tenant_type": user.attributes.get("tenant_type", "school")}'
mapping, created = ScopeMapping.objects.get_or_create(name="IqbalAI role/tenant claims", defaults={"scope_name": "profile", "expression": EXPRESSION})
mapping.scope_name = "profile"
mapping.expression = EXPRESSION
mapping.save()
provider = OAuth2Provider.objects.filter(name=PROVIDER_NAME).first()
if provider and not provider.property_mappings.filter(pk=mapping.pk).exists():
    provider.property_mappings.add(mapping)
print("CLAIM_MAPPING", "created" if created else "updated", "| attached:", bool(provider))

# 2) One user per role.
made, refreshed = 0, 0
for email, name, role, tenant in ACCOUNTS:
    user, was_created = User.objects.get_or_create(
        username=email, defaults={"email": email, "name": name}
    )
    user.email = email
    user.name = name
    user.is_active = True
    attrs = dict(user.attributes or {})
    attrs["role"] = role
    attrs["tenant_type"] = tenant
    user.attributes = attrs
    user.set_password(PASSWORD)
    user.save()
    made += was_created
    refreshed += not was_created
    print("USER", "created" if was_created else "updated", email, "->", role, tenant)

print(f"SEED_DONE created={made} updated={refreshed} total={len(ACCOUNTS)}")
