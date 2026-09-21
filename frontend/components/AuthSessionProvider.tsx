"use client";

import { SessionProvider, useSession } from "next-auth/react";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { recordLoginEvent } from "../lib/enterprise";

const LOGIN_BEACON_KEY = "kulima:login-beacon";

// Audit trail (Phase 4): record a User Login event once per browser session.
// The beacon is fire-and-forget — a failure must never block the app, and a
// repeated page load inside the same session must never duplicate the event.
function LoginBeacon() {
  const { status, data } = useSession();
  const userId = data?.user?.email || data?.user?.name || "session";

  useEffect(() => {
    if (status !== "authenticated") return;
    if (typeof window === "undefined") return;

    const key = `${LOGIN_BEACON_KEY}:${userId}`;
    try {
      if (window.sessionStorage.getItem(key)) return;
      // Mark first so a StrictMode double-invoke cannot double-record; the
      // marker is cleared on failure to allow a later retry.
      window.sessionStorage.setItem(key, new Date().toISOString());
    } catch {
      return;
    }

    recordLoginEvent().catch(() => {
      try {
        window.sessionStorage.removeItem(key);
      } catch {
        /* ignore */
      }
    });
  }, [status, userId]);

  return null;
}

export default function AuthSessionProvider({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <LoginBeacon />
      {children}
    </SessionProvider>
  );
}
