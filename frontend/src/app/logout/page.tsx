"use client";

import { useEffect } from "react";

import { authApi } from "@/lib/api";
import { clearToken } from "@/lib/auth";

/** Clears the server-side cookie session before returning to sign-in. */
export default function LogoutPage() {
  useEffect(() => {
    void authApi
      .logout()
      .catch(() => undefined)
      .finally(() => {
        clearToken();
        window.location.replace("/login");
      });
  }, []);

  return null;
}
