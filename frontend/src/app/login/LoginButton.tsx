"use client";

import { Button } from "@/components/ui/button";
import { getLoginUrl } from "@/lib/auth";

interface LoginButtonProps {
  label: string;
}

export function LoginButton({ label }: LoginButtonProps) {
  return (
    <Button
      variant="primary"
      size="lg"
      className="w-full"
      onClick={() => {
        window.location.href = getLoginUrl();
      }}
    >
      {label}
    </Button>
  );
}
