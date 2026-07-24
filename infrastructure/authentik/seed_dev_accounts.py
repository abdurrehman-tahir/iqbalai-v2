"""Dev-only Authentik seed: one login-able user per role, password 'devpassword'.

Run inside the Authentik container (idempotent — safe to re-run).

On Windows PowerShell, do NOT pipe the file into `ak shell` (REPL breaks
indented blocks). Copy + exec instead:

    docker cp infrastructure/authentik/seed_dev_accounts.py `
        iqbalai_v2-authentik-server-1:/tmp/seed_dev_accounts.py
    docker compose exec -T authentik-server `
        ak shell -c "exec(open('/tmp/seed_dev_accounts.py').read())"

On Linux/macOS either of these works:

    docker compose exec -T authentik-server \
        ak shell -c "exec(open('/tmp/seed_dev_accounts.py').read())"
    # after docker cp, or:
    docker compose exec -T authentik-server ak shell < \
        infrastructure/authentik/seed_dev_accounts.py

Also installs a scope mapping so the JWT carries `role` + `tenant_type` +
`district_id`/`school_id` from each user's attributes — without it every login
defaults to school/no-role and district admins get 403 on scoped routes.
Attaches to the IqbalAI OIDC provider (`iqbalai-api` from the blueprint;
falls back to legacy 'IqbalAI Frontend' name).

NOT for production: fixed weak password, self-set roles, bypasses the app's
independent_signup provisioning / ToS.
"""

from authentik.core.models import User
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

PASSWORD = "devpassword"
PROVIDER_NAMES = ("iqbalai-api", "IqbalAI Frontend")

# Match alembic school/0015 sample district + school — always present after migrate.
SAMPLE_DISTRICT_ID = "00000000-0000-0000-0000-0000000d1571"
SAMPLE_SCHOOL_ID = "00000000-0000-0000-0000-00000005c001"
# Coordinator may create grades only within scoped_ids (flow-2); empty ⇒ deny all.
COORDINATOR_SCOPE = ",".join(f"Grade {n}" for n in range(1, 13))

# (email, display name, role, tenant_type, district_id, school_id, scoped_ids)
ACCOUNTS = [
    ("platform.admin@iqbalai.dev", "Platform Admin", "platform_admin", "school", None, None, None),
    (
        "district.admin@iqbalai.dev",
        "District Admin",
        "district_admin",
        "school",
        SAMPLE_DISTRICT_ID,
        None,
        None,
    ),
    (
        "school.admin@iqbalai.dev",
        "School Admin",
        "school_admin",
        "school",
        SAMPLE_DISTRICT_ID,
        SAMPLE_SCHOOL_ID,
        None,
    ),
    (
        "coordinator@iqbalai.dev",
        "Coordinator",
        "coordinator",
        "school",
        SAMPLE_DISTRICT_ID,
        SAMPLE_SCHOOL_ID,
        COORDINATOR_SCOPE,
    ),
    (
        "teacher@iqbalai.dev",
        "Teacher",
        "teacher",
        "school",
        SAMPLE_DISTRICT_ID,
        SAMPLE_SCHOOL_ID,
        None,
    ),
    (
        "student@iqbalai.dev",
        "Student",
        "student",
        "school",
        SAMPLE_DISTRICT_ID,
        SAMPLE_SCHOOL_ID,
        None,
    ),
    ("parent@iqbalai.dev", "Parent", "parent", "school", None, None, None),
    ("ind.teacher@iqbalai.dev", "Independent Teacher", "independent_teacher", "independent", None, None, None),
    ("ind.student@iqbalai.dev", "Independent Student", "independent_student", "independent", None, None, None),
]

# 1) Scope mapping that emits role + tenant_type + org/grade scope into the token.
# Prefer the blueprint mapping (`scope_name=iqbalai`) — the API authorize URL
# must request that scope. Keep a profile-scoped backup for older clients.
# Use `request.user` (Authentik expression context), not bare `user`.
# Single-line expression: `ak shell < file` mis-parses multi-line strings.
EXPRESSION = (
    'return {"role": request.user.attributes.get("role", ""), '
    '"tenant_type": request.user.attributes.get("tenant_type", "school"), '
    '"district_id": request.user.attributes.get("district_id") or None, '
    '"school_id": request.user.attributes.get("school_id") or None, '
    '"scoped_ids": request.user.attributes.get("scoped_ids") or None}'
)
provider = None
for _pname in PROVIDER_NAMES:
    provider = OAuth2Provider.objects.filter(name=_pname).first()
    if provider:
        break

blueprint_mapping = ScopeMapping.objects.filter(name="IqbalAI Claims (role + tenant_type)").first()
if blueprint_mapping is not None:
    blueprint_mapping.scope_name = "iqbalai"
    blueprint_mapping.expression = EXPRESSION
    blueprint_mapping.save()
    if provider and not provider.property_mappings.filter(pk=blueprint_mapping.pk).exists():
        provider.property_mappings.add(blueprint_mapping)
    print(
        "CLAIM_MAPPING blueprint updated | attached:",
        bool(provider),
        "| provider:",
        getattr(provider, "name", None),
    )

mapping, created = ScopeMapping.objects.get_or_create(
    name="IqbalAI role/tenant claims",
    defaults={"scope_name": "profile", "expression": EXPRESSION},
)
mapping.scope_name = "profile"
mapping.expression = EXPRESSION
mapping.save()
if provider and not provider.property_mappings.filter(pk=mapping.pk).exists():
    provider.property_mappings.add(mapping)
print(
    "CLAIM_MAPPING profile backup",
    "created" if created else "updated",
    "| attached:",
    bool(provider),
    "| provider:",
    getattr(provider, "name", None),
)

# 2) One user per role.
made, refreshed = 0, 0
for email, name, role, tenant, district_id, school_id, scoped_ids in ACCOUNTS:
    user, was_created = User.objects.get_or_create(
        username=email, defaults={"email": email, "name": name}
    )
    user.email = email
    user.name = name
    user.is_active = True
    attrs = dict(user.attributes or {})
    attrs["role"] = role
    attrs["tenant_type"] = tenant
    if district_id:
        attrs["district_id"] = district_id
    else:
        attrs.pop("district_id", None)
    if school_id:
        attrs["school_id"] = school_id
    else:
        attrs.pop("school_id", None)
    if scoped_ids:
        attrs["scoped_ids"] = scoped_ids
    else:
        attrs.pop("scoped_ids", None)
    user.attributes = attrs
    user.set_password(PASSWORD)
    user.save()
    made += was_created
    refreshed += not was_created
    print(
        "USER",
        "created" if was_created else "updated",
        email,
        "->",
        role,
        tenant,
        "district=",
        district_id,
        "school=",
        school_id,
        "scoped=",
        scoped_ids,
    )

print(f"SEED_DONE created={made} updated={refreshed} total={len(ACCOUNTS)}")
