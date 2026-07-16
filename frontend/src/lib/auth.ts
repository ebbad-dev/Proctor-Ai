export type Role = "student" | "instructor" | "admin";

export interface AuthUser {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
  tenant_id?: string;
  tenant_name?: string;
}

export interface AuthSession {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
  logged_in_at: string;
}

const KEY = "proctorai_auth";

export function getAuthSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as AuthSession) : null;
  } catch {
    return null;
  }
}

export function setAuthSession(session: Omit<AuthSession, "logged_in_at">) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    KEY,
    JSON.stringify({ ...session, logged_in_at: new Date().toISOString() }),
  );
  window.dispatchEvent(new Event("proctorai-auth-change"));
}

export function clearAuthSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
  window.dispatchEvent(new Event("proctorai-auth-change"));
}

export function authHeaders(): Record<string, string> {
  const session = getAuthSession();
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
}

export function redirectForRole(role?: Role): string {
  if (role === "student") return "/setup";
  if (role === "instructor") return "/instructor";
  if (role === "admin") return "/admin";
  return "/login";
}

export function roleCanAccess(role: Role | undefined, pathname: string): boolean {
  if (!role) return false;
  if (role === "admin") return true;
  if (pathname === "/" || pathname === "/login") return true;
  if (role === "instructor") {
    return [
      "/instructor",
      "/monitor",
      "/sessions",
      "/reports",
      "/browser-guard",
      "/assistant",
    ].some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  }
  return [
    "/setup",
    "/checklist",
    "/id-verification",
    "/room-scan",
    "/exam",
    "/reports",
    "/browser-guard",
    "/assistant",
    "/sessions",
  ].some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
