# Flow 13 — Subscriptions (Thin Spec)

**Status:** draft (v1 — thin spec; schema-only at launch; placeholder UI; full module deferred to Phase 2)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-14
**Related ARCHITECTURE sections:** §3.17 (subscription cross-cutting attribute), §4 (DB patterns), §6 (auth, §6.19 inheritance), §11.20 (Stripe webhook flow placeholder), §14.10 (audit log)
**Related feature specs:** `flow-1-platform-setup.md` (Platform Admin defines tiers), `flow-2-admin-coordinator-setup.md` (District / School subscribe placeholders)
**v2 doc features covered:** Subscription tier management (NEW concept introduced during v2 review)

---

## 1. Purpose

The full subscription module is deferred to Phase 2. At launch:

- **Schema exists** for subscription tiers, subscriptions, and payments
- **Platform Admin can define tiers** via a CRUD UI (purely informational at launch)
- **District / School subscribe buttons exist** in UI but open a "Coming soon" modal
- **No Stripe integration**, no payment processing, no cap enforcement, no webhook flow
- **All features free for all users at launch**

This spec exists to lock the data model so Phase 2 implementation doesn't require schema migrations across already-running schools. It also documents the planned full subscription flow for future implementation.

**Why thin:** subscription enforcement is not a Phase 1 priority. The pilot model is "free with manual support." Building a full billing flow that won't be used wastes pilot time. Schema + placeholder UI is the minimum to avoid Phase 2 migration pain.

---

## 2. Personas

| Persona | Role in this flow |
|---|---|
| **Platform Admin** | Creates / edits subscription tier definitions. Sees tier list in admin dashboard. At launch: this is the ONLY active subscription-related action. |
| **District Admin** | Sees a "Subscription" page in their dashboard. At launch: page shows "Coming soon" modal on subscribe button. |
| **School Admin** | Sees a "Subscription" page in their dashboard (HIDDEN if their District has a subscription, per Q1). At launch: "Coming soon" modal. |
| **Coordinator / Teacher / Student / Parent** | No direct subscription surfaces in this flow at launch. Phase 2 may surface tier capabilities. |

---

## 3. Lifecycle

### 3.1 Subscription tier definition lifecycle (Platform Admin only — ACTIVE at launch)

```
   DRAFT                      (Platform Admin creates tier definition)
       ↓ saved
   PUBLISHED                  (visible to District/School subscribe pages as placeholder option)
       ↓ Platform Admin edits
   EDITED                     (PUBLISHED with updates)
       ↓ Platform Admin action
   DEPRECATED                 (no longer offered to new subscribers; existing subscribers grandfathered — Phase 2)
```

**Locked rules:**
- Per Q2: ONE tier table with `applies_to_role` column ("district" or "school"). Each tier is scoped to one role level.
- Per Q3: caps stored in a JSONB column — flexible schema. Examples: `{"max_schools": 10, "max_teachers_per_school": 50, "max_lectures_per_month_per_teacher": null, "max_storage_gb": 100, "feature_flags": {"group_study": true}}`. NO cap enforcement at launch.
- Per Q4: per-month flat per-tier per-scope pricing model. Schema supports it; UI shows it.
- Per Q5: PKR currency only at launch. USD added in Phase 2 for international independents.
- Tier deactivation is reversible.

### 3.2 District subscription lifecycle (PLACEHOLDER at launch)

```
   NO_SUBSCRIPTION            (default state for any new District)
       ↓ District Admin clicks "Upgrade"
   PLACEHOLDER_MODAL          (UI shows "Coming soon" modal; no state change)

   FULL FLOW (PHASE 2):
       NO_SUBSCRIPTION → PENDING_PAYMENT (Stripe checkout) → ACTIVE → PAST_DUE (grace 14 days) → CANCELLED / EXPIRED
```

**Locked rule at launch:** subscribe button opens "Coming soon" modal. Schema rows for `subscriptions` table NOT created at launch (no rows exist yet).

### 3.3 School subscription lifecycle (PLACEHOLDER at launch)

```
   NO_SUBSCRIPTION            (default for any new School)
       ↓ Subscribe button visible only if school's District has NO subscription (per Q1 inheritance)
       ↓ School Admin clicks "Upgrade"
   PLACEHOLDER_MODAL          (UI shows "Coming soon" modal; no state change)
```

**Locked rules at launch:**
- Subscribe button HIDDEN if District has a subscription (subscription inherits from District to all member schools per Q1).
- Same placeholder modal as District.

### 3.4 Full subscription lifecycle (PHASE 2 — documented for future reference)

When the full module is built:

```
PHASE 2 ONLY:
   NO_SUBSCRIPTION
       ↓ District/School Admin selects tier + clicks "Upgrade"
   PENDING_PAYMENT             (Stripe Checkout session created)
       ↓ user completes payment
   ACTIVE                      (caps now enforced; webhook updates state)
       ↓ recurring billing cycle
   ACTIVE (renewed)
       ↓ payment fails
   PAST_DUE                    (14-day grace per Q7; daily warning notifications; account "read-only" — no new content creation; existing content visible)
       ↓ payment succeeds OR cancelled
   ACTIVE OR HARD_SUSPENDED
       (At 30 days unpaid → hard suspension)
```

---

## 4. Permissions matrix

Per §6.19 inheritance.

| Action | Platform Admin | District Admin | School Admin | (Other roles) |
|---|:---:|:---:|:---:|:---:|
| Create / edit subscription tier definition | ✅ | ❌ | ❌ | ❌ |
| Deprecate tier | ✅ | ❌ | ❌ | ❌ |
| View tier definitions list | ✅ | view (own scope's tiers) | view (own scope's tiers) | — |
| Subscribe to a District tier (PHASE 2) | n/a | ✅ (own district) | ❌ | ❌ |
| Subscribe to a School tier (PHASE 2; only if no District subscription) | n/a | n/a | ✅ (own school) | ❌ |
| Click "Upgrade" button at launch | ✅ (sees modal) | ✅ (sees modal) | ✅ (sees modal if no District subscription) | ❌ |
| View own current subscription state | n/a | ✅ (own) | ✅ (own) | view-only (Coordinator sees own school's per §6.19) |

---

## 5. Edge cases

### 5.1 Tier management (launch active)
- **Platform Admin creates tier with invalid caps JSON:** rejected with `VALIDATION_ERROR`.
- **Platform Admin deprecates a tier with no subscribers:** allowed; tier marked deprecated.
- **Platform Admin tries to delete a tier (instead of deprecating):** blocked — hard delete deferred to Phase 2.

### 5.2 Subscribe button (launch placeholder)
- **District Admin clicks "Upgrade" → modal:** confirms "Subscriptions coming soon; meanwhile all features are available."
- **School Admin in a district with subscription tries to subscribe at school level:** button HIDDEN. If somehow accessed via direct URL: `PRECONDITION_FAILED` "Your district already has a subscription."
- **School Admin in district without subscription:** button visible, opens placeholder modal.

### 5.3 Cross-tenant
- **Independent users:** no subscription surfaces visible at launch. Phase 2 may add independent-user subscription tiers.

### 5.4 Phase 2 (documented for future)
- **Subscription lapses mid-month:** 14-day grace; daily warnings; account → read-only; hard suspend at 30 days.
- **District subscribes after school already paid individually:** school subscription auto-cancelled with prorated refund (Phase 2 logic).
- **School transferred between districts:** subscription state recomputed based on new district's status.

---

## 6. Limits

### Launch
- Max tiers per role-scope: 10 at launch.
- Tier name max length: 100 chars.
- Caps JSONB max size: 16 KB.
- Currency: PKR only at launch.

### Phase 2 (planned)
- Stripe webhook retry: 5 attempts with exponential backoff.
- Grace period: 14 days (configurable via env var).
- Hard suspension threshold: 30 days unpaid.

---

## 7. Notifications

### Launch (`system` namespace)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Platform Admin creates new tier (placeholder for future use) | Platform Admin | In-app | `system.subscription_tier_created` |
| Platform Admin deprecates tier | Platform Admin | In-app | `system.subscription_tier_deprecated` |

### Phase 2 (planned, in `account` namespace)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Subscription activated | District/School Admin | In-app + email | `account.subscription_activated` |
| Payment past due | District/School Admin | In-app + email + SMS | `account.subscription_past_due` |
| Subscription cancelled | District/School Admin | In-app + email | `account.subscription_cancelled` |
| Grace period ending in 3 days | District/School Admin | In-app + email + SMS | `account.subscription_grace_warning` |
| Hard suspension | District/School Admin | In-app + email | `account.subscription_hard_suspended` |

---

## 8. Open questions

1. **Independent user subscription model.** Free at launch for all independents per Q10. **Question:** Phase 2 — do independents get their own tier hierarchy (e.g., free + paid)? Recommendation: yes, separate independent tier table. Add to Phase 2 TODO.

2. **Per-seat pricing.** Per-month flat at launch per Q4. **Question:** Phase 2 should add per-seat? Recommendation: yes — Pakistani context favors per-school flat for predictability, but per-seat may attract international independents.

3. **Subscription downgrades.** **Question:** Phase 2 — can District downgrade their tier? Recommendation: yes, with prorated refund at billing cycle boundary.

4. **Refund policy.** **Question:** Phase 2 — full refund window? Recommendation: 7 days from initial purchase; prorated thereafter.

5. **Manual invoicing for enterprise customers.** **Question:** Phase 2 — do we support manual invoice + bank transfer alongside Stripe? Recommendation: yes for enterprise (large districts); deferred to Phase 3.

6. **Cap calculation timing.** **Question:** if a District subscription's cap is "max 10 schools" and they currently have 12, do they auto-downgrade? Recommendation: grandfather existing schools; block new school creation until below cap.

7. **Phase 2 launch timing.** **Question:** when does Phase 2 subscription module land? Recommendation: after pilot succeeds (3-6 months post-launch); during commercial rollout phase.

---

## 9. Out of scope (for now)

EVERYTHING about subscription enforcement is out of scope at launch. Specifically:

- **Stripe integration** (Q6 deferral; placeholder env vars only)
- **Payment processing** of any kind
- **Cap enforcement** (max users, max teachers, max storage, etc.)
- **Feature flagging by tier** (e.g., "group study only in Pro tier")
- **Recurring billing**
- **Invoice generation**
- **Refund processing**
- **Webhook handling for payment events**
- **Customer portal** for managing payment methods
- **Tax handling** (Pakistan sales tax, etc.)
- **Multi-currency** (PKR only at launch)
- **Per-seat pricing**
- **Subscription downgrades**
- **Independent user paid tiers**
- **Manual invoicing for enterprise**
- **Annual prepayment / discounts**
- **Free trial periods**
- **Promotional pricing / coupon codes**
- **Cross-district subscription transfers**

All of these go into `TODO.md` as Phase 2 items.

---

## 10. Related ARCHITECTURE sections

- **§3.16** — Independent tenant (no subscription enforcement at launch)
- **§3.17** — Subscription as cross-cutting tenant attribute (schema only)
- **§4.2-4.8** — DB mixins
- **§4.12** — Alembic migration (this flow introduces subscription_tiers, subscriptions, subscription_payments tables — empty rows at launch)
- **§6.7** — Dependency primitives
- **§6.19** — Permission inheritance
- **§11.20** — Stripe webhook flow placeholder (Phase 2)
- **§14.10** — Audit log: tier creation/edit/deprecation events; future subscription state changes

### Data model sketch

```
# At launch — schema exists, mostly empty rows:

subscription_tiers
  id (uuidv7), name, description, applies_to_role (enum: district/school),
  caps_jsonb, pricing_monthly_pkr, currency (default 'PKR'),
  status (enum: draft/published/deprecated),
  created_by_user_id (Platform Admin), created_at, updated_at, deprecated_at

# These tables exist but have NO rows at launch:

subscriptions
  id (uuidv7), tier_id (FK), tenant_type (enum: district/school),
  district_id (nullable FK), school_id (nullable FK),
  status (enum: pending_payment/active/past_due/cancelled/expired/hard_suspended),
  started_at, current_period_start, current_period_end,
  grace_until (nullable), cancelled_at, stripe_subscription_id (nullable),
  created_at, updated_at
  -- ONE OF (district_id, school_id) must be set; not both

subscription_payments
  id (uuidv7), subscription_id (FK), amount_pkr, currency,
  status (enum: pending/succeeded/failed/refunded), 
  stripe_payment_intent_id (nullable), paid_at, failure_reason (nullable),
  created_at
```

---

## 11. Acceptance criteria

### Launch (active features)
- ✅ Platform Admin can create / edit / deprecate subscription tiers via admin UI
- ✅ Tier definition CRUD endpoint with validation (caps JSON valid, pricing positive, applies_to_role enum)
- ✅ Tier list visible to District/School Admin (their scope's tiers only)
- ✅ District Admin's "Upgrade" button opens "Coming soon" placeholder modal — NO state change
- ✅ School Admin's "Upgrade" button HIDDEN if District subscription exists (Q1 inheritance)
- ✅ School Admin's "Upgrade" button opens placeholder modal otherwise
- ✅ Schema for `subscriptions` and `subscription_payments` tables exists in DB
- ✅ NO rows in `subscriptions` table at launch (no actual subscriptions created)
- ✅ NO Stripe integration code; only env var placeholders
- ✅ Audit log: tier creation, edit, deprecation events per §14.10

### Phase 2 (deferred; documented for future implementation)
- ✅ Stripe Checkout integration
- ✅ Webhook handlers for payment events
- ✅ 14-day grace period state machine
- ✅ Cap enforcement at request time
- ✅ Subscription downgrades + refunds
- ✅ Independent user paid tiers
- ✅ Multi-currency
- ✅ Customer portal

---

**Last reviewed:** 2026-05-14
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log v1 (initial draft):**
- Thin spec only — schema-only at launch
- Platform Admin tier CRUD ACTIVE at launch
- District/School subscribe buttons placeholder modal at launch
- Per Q1: District subscription inherits to schools; School button hidden if District subscribed
- Per Q2: ONE tier table with applies_to_role column
- Per Q3: caps as JSONB (flexible; not enforced at launch)
- Per Q4: per-month flat per-tier
- Per Q5: PKR only at launch
- Per Q6 / Q7: no Stripe code; placeholder env vars only (STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET)
- Per Q8: free for all at launch
- Per Q10: independent users free at launch; Phase 2 considers paid tiers
- Full subscription module documented for Phase 2 implementation
- All Phase 2 features in §9 Out of Scope; mirrored in TODO entries
