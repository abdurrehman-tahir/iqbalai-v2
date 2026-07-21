const required = [
  "NEXT_PUBLIC_AUTHENTIK_URL",
  "NEXT_PUBLIC_APP_URL",
  "NEXT_PUBLIC_AUTHENTIK_CLIENT_ID",
];

const missing = required.filter((name) => !process.env[name]);

if (missing.length > 0) {
  throw new Error(
    `Missing required production authentication environment variable(s): ${missing.join(", ")}`,
  );
}
