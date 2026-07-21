# Real authentication E2E

`auth-real.spec.ts` is non-mocked and tagged `@auth @real`. It needs a reachable
API configured through `NEXT_PUBLIC_API_URL` (for example,
`http://localhost:8000/api/v1`).

The unauthenticated API and login-entry tests run with only that API. Each
full-role OIDC test skips unless both of these variables are present for its
role:

```sh
E2E_OIDC_<ROLE>_EMAIL
E2E_OIDC_<ROLE>_PASSWORD
```

`<ROLE>` is one of `PLATFORM_ADMIN`, `DISTRICT_ADMIN`, `SCHOOL_ADMIN`,
`COORDINATOR`, `TEACHER`, `STUDENT`, `PARENT`, `INDEPENDENT_TEACHER`, or
`INDEPENDENT_STUDENT`. Configure each account in the real Authentik instance
with accepted terms and the matching application role; credentials are never
committed to the repository.

Run the suite with:

```sh
pnpm e2e --grep "@auth.*@real"
```
