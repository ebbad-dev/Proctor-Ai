import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Building2, FileClock, KeyRound, Plus, Search, ShieldCheck, UserPlus, Users } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import {
  useAdminUsers,
  useAuditLogs,
  useCreateAdminUser,
  useCreateTenant,
  useSetAdminUserPassword,
  useTenants,
  useUpdateAdminUser,
} from "@/lib/queries";
import { getAuthSession } from "@/lib/auth";
import type { AdminUser, Tenant } from "@/lib/types";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Admin Console - ProctorAI" },
      {
        name: "description",
        content: "Manage institutions, users, and security audit activity.",
      },
    ],
  }),
  component: AdminConsole,
});

function AdminConsole() {
  const tenants = useTenants();
  const auditLogs = useAuditLogs();
  const createTenant = useCreateTenant();
  const user = getAuthSession()?.user;
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const recentActions = useMemo(() => auditLogs.data ?? [], [auditLogs.data]);
  const tenantRows = tenants.data ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl space-y-4">
        <GlassCard className="flex flex-wrap items-center gap-3 p-5">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-primary shadow-glow">
            <ShieldCheck className="h-5 w-5 text-primary-foreground" aria-hidden />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Enterprise admin console</h1>
            <p className="text-sm text-muted-foreground">
              {user?.tenant_name ?? "Default Institution"} - tenant isolation, user control, and audit accountability
            </p>
          </div>
        </GlassCard>

        <UserManagement tenants={tenantRows} />

        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <Building2 className="h-4 w-4 text-primary" aria-hidden />
              <h2 className="text-sm font-semibold">Institutions</h2>
            </div>

            <div className="space-y-2">
              {tenantRows.map((tenant) => (
                <div key={tenant.tenant_id} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{tenant.name}</div>
                      <div className="text-xs text-muted-foreground">{tenant.slug}</div>
                    </div>
                    <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-xs text-emerald-200">
                      {tenant.status}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">Plan: {tenant.plan_name || "enterprise"}</div>
                </div>
              ))}
              {!tenants.isLoading && !tenantRows.length && (
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-muted-foreground">
                  No institutions found.
                </div>
              )}
            </div>

            <form
              className="mt-5 space-y-3 border-t border-white/10 pt-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (!name.trim() || !slug.trim()) return;
                createTenant.mutate(
                  { name: name.trim(), slug: slug.trim().toLowerCase(), plan_name: "enterprise" },
                  {
                    onSuccess: () => {
                      setName("");
                      setSlug("");
                    },
                  },
                );
              }}
            >
              <div className="text-sm font-semibold">Add institution</div>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Institution name"
                className="h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none transition focus:border-primary/70"
              />
              <input
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                placeholder="institution-slug"
                className="h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none transition focus:border-primary/70"
              />
              <GlowButton type="submit" disabled={createTenant.isPending || !name.trim() || !slug.trim()} className="w-full">
                <Plus className="h-4 w-4" aria-hidden />
                {createTenant.isPending ? "Creating..." : "Create institution"}
              </GlowButton>
              {createTenant.error && (
                <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
                  {createTenant.error.message}
                </p>
              )}
            </form>
          </GlassCard>

          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <FileClock className="h-4 w-4 text-primary" aria-hidden />
              <h2 className="text-sm font-semibold">Recent audit activity</h2>
            </div>
            <div className="overflow-hidden rounded-xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/[0.04] text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">Action</th>
                    <th className="px-3 py-2 font-medium">Actor</th>
                    <th className="px-3 py-2 font-medium">Resource</th>
                    <th className="px-3 py-2 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {recentActions.map((log) => (
                    <tr key={log.audit_id} className="border-t border-white/10">
                      <td className="px-3 py-2 font-medium">{log.action}</td>
                      <td className="px-3 py-2 text-muted-foreground">{log.actor_email || "system"}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {log.resource_type || "-"} {log.resource_id ? `- ${log.resource_id}` : ""}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">{new Date(log.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                  {!auditLogs.isLoading && recentActions.length === 0 && (
                    <tr>
                      <td className="px-3 py-6 text-center text-muted-foreground" colSpan={4}>
                        No audit events have been recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </div>
      </div>
    </AppShell>
  );
}

function UserManagement({ tenants }: { tenants: Tenant[] }) {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [tenantId, setTenantId] = useState("");
  const users = useAdminUsers({ q, role, tenant_id: tenantId });
  const createUser = useCreateAdminUser();
  const updateUser = useUpdateAdminUser();
  const setPassword = useSetAdminUserPassword();
  const [draft, setDraft] = useState({
    email: "",
    full_name: "",
    role: "student" as AdminUser["role"],
    tenant_id: "tenant_default",
    password: "",
  });
  const [passwords, setPasswords] = useState<Record<string, string>>({});
  const tenantOptions = tenants.length
    ? tenants
    : [{ tenant_id: "tenant_default", name: "Default Institution", slug: "default", status: "active", plan_name: "enterprise" }];

  return (
    <GlassCard className="p-5">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-primary" aria-hidden />
          <h2 className="text-sm font-semibold">User management</h2>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search users"
              className="h-9 w-56 rounded-lg border border-white/10 bg-white/5 pl-9 pr-3 text-sm outline-none transition focus:border-primary/70"
            />
          </div>
          <select value={role} onChange={(event) => setRole(event.target.value)} className="h-9 rounded-lg border border-white/10 bg-background px-3 text-sm outline-none transition focus:border-primary/70">
            <option value="">All roles</option>
            <option value="student">Students</option>
            <option value="instructor">Instructors</option>
            <option value="admin">Admins</option>
          </select>
          <select value={tenantId} onChange={(event) => setTenantId(event.target.value)} className="h-9 rounded-lg border border-white/10 bg-background px-3 text-sm outline-none transition focus:border-primary/70">
            <option value="">All institutions</option>
            {tenantOptions.map((tenant) => (
              <option key={tenant.tenant_id} value={tenant.tenant_id}>{tenant.name}</option>
            ))}
          </select>
        </div>
      </div>

      <form
        className="mb-5 grid gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 md:grid-cols-[1fr_1fr_0.8fr_0.9fr_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          createUser.mutate(draft, {
            onSuccess: () =>
              setDraft({
                email: "",
                full_name: "",
                role: "student",
                tenant_id: draft.tenant_id,
                password: "",
              }),
          });
        }}
      >
        <input value={draft.email} onChange={(event) => setDraft((current) => ({ ...current, email: event.target.value }))} placeholder="email@institution.edu" className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none transition focus:border-primary/70" />
        <input value={draft.full_name} onChange={(event) => setDraft((current) => ({ ...current, full_name: event.target.value }))} placeholder="Full name" className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none transition focus:border-primary/70" />
        <select value={draft.role} onChange={(event) => setDraft((current) => ({ ...current, role: event.target.value as AdminUser["role"] }))} className="h-10 rounded-lg border border-white/10 bg-background px-3 text-sm outline-none transition focus:border-primary/70">
          <option value="student">Student</option>
          <option value="instructor">Instructor</option>
          <option value="admin">Admin</option>
        </select>
        <select value={draft.tenant_id} onChange={(event) => setDraft((current) => ({ ...current, tenant_id: event.target.value }))} className="h-10 rounded-lg border border-white/10 bg-background px-3 text-sm outline-none transition focus:border-primary/70">
          {tenantOptions.map((tenant) => (
            <option key={tenant.tenant_id} value={tenant.tenant_id}>{tenant.name}</option>
          ))}
        </select>
        <input value={draft.password} onChange={(event) => setDraft((current) => ({ ...current, password: event.target.value }))} placeholder="Temporary password" type="password" className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none transition focus:border-primary/70" />
        <GlowButton type="submit" disabled={createUser.isPending || !draft.email || !draft.full_name || !draft.password} className="h-10 whitespace-nowrap">
          <UserPlus className="h-4 w-4" aria-hidden />
          {createUser.isPending ? "Creating..." : "Create"}
        </GlowButton>
      </form>

      {createUser.error && <ErrorLine message={createUser.error.message} />}

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="bg-white/[0.04] text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">User</th>
              <th className="px-3 py-2 font-medium">Role</th>
              <th className="px-3 py-2 font-medium">Institution</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Temporary password</th>
              <th className="px-3 py-2 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {(users.data ?? []).map((row) => (
              <tr key={row.user_id} className="border-t border-white/10 align-top">
                <td className="px-3 py-3">
                  <div className="font-medium">{row.full_name}</div>
                  <div className="text-xs text-muted-foreground">{row.email}</div>
                </td>
                <td className="px-3 py-3">
                  <select value={row.role} onChange={(event) => updateUser.mutate({ user_id: row.user_id, values: { role: event.target.value as AdminUser["role"] } })} className="h-9 rounded-lg border border-white/10 bg-background px-2 text-sm outline-none">
                    <option value="student">Student</option>
                    <option value="instructor">Instructor</option>
                    <option value="admin">Admin</option>
                  </select>
                </td>
                <td className="px-3 py-3">
                  <select value={row.tenant_id ?? "tenant_default"} onChange={(event) => updateUser.mutate({ user_id: row.user_id, values: { tenant_id: event.target.value } })} className="h-9 max-w-44 rounded-lg border border-white/10 bg-background px-2 text-sm outline-none">
                    {tenantOptions.map((tenant) => (
                      <option key={tenant.tenant_id} value={tenant.tenant_id}>{tenant.name}</option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-3">
                  <button type="button" onClick={() => updateUser.mutate({ user_id: row.user_id, values: { is_active: !row.is_active } })} className={`rounded-full border px-2 py-1 text-xs transition ${row.is_active ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200" : "border-white/10 bg-white/5 text-muted-foreground"}`}>
                    {row.is_active ? "Active" : "Disabled"}
                  </button>
                </td>
                <td className="px-3 py-3">
                  <div className="flex items-center gap-2">
                    <input value={passwords[row.user_id] ?? ""} onChange={(event) => setPasswords((current) => ({ ...current, [row.user_id]: event.target.value }))} placeholder="New password" type="password" className="h-9 w-40 rounded-lg border border-white/10 bg-white/5 px-2 text-sm outline-none" />
                    <button type="button" title="Set temporary password" disabled={!passwords[row.user_id] || setPassword.isPending} onClick={() => setPassword.mutate({ user_id: row.user_id, password: passwords[row.user_id] ?? "" }, { onSuccess: () => setPasswords((current) => ({ ...current, [row.user_id]: "" })) })} className="inline-grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-muted-foreground transition hover:text-foreground disabled:opacity-40">
                      <KeyRound className="h-4 w-4" aria-hidden />
                    </button>
                  </div>
                </td>
                <td className="px-3 py-3 text-xs text-muted-foreground">
                  {row.created_at ? new Date(row.created_at).toLocaleDateString() : "-"}
                </td>
              </tr>
            ))}
            {!users.isLoading && !users.data?.length && (
              <tr>
                <td className="px-3 py-6 text-center text-muted-foreground" colSpan={6}>
                  No users match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {updateUser.error && <ErrorLine message={updateUser.error.message} />}
      {setPassword.error && <ErrorLine message={setPassword.error.message} />}
    </GlassCard>
  );
}

function ErrorLine({ message }: { message: string }) {
  return (
    <p className="my-3 rounded-lg border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
      {message}
    </p>
  );
}
