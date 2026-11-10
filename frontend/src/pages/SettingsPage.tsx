import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, downloadFile } from "../api/client";
import type { BackupFile, BackupOverview, DriveFile, Settings as SettingsType, User } from "../api/types";
import { useAuth } from "../hooks/useAuth";
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, ErrorState, Input, Label, PageHeader, Select, Spinner, Table, TD, TH } from "../components/ui";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/dialog";
import { fmtDateTime, fmtSize } from "../lib/utils";
import { Cloud, CloudUpload, DatabaseBackup, Download, HardDriveDownload, KeyRound, RefreshCw, ShieldCheck, Trash2, Upload } from "lucide-react";

const TABS = ["School", "Academic", "AI Provider", "Users", "Backup & Data"] as const;
type Tab = (typeof TABS)[number];

export default function SettingsPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("School");
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setSettings(await api.get<SettingsType>("/api/settings"));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function flash(msg: string) {
    setSaved(msg);
    setTimeout(() => setSaved(""), 2500);
  }

  if (loading && !settings)
    return <div className="flex h-64 items-center justify-center"><Spinner /></div>;
  if (error || !settings)
    return <ErrorState message={error || "Could not load settings."} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="Settings"
        description="School identity, academic configuration, AI provider, user accounts and backups."
        actions={saved ? <Badge tone="green">{saved}</Badge> : undefined}
      />

      <div className="mb-5 flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-lg px-3.5 py-1.5 text-sm font-medium ${tab === t ? "bg-brand-600 text-cream" : "bg-white text-stone-600 hover:bg-stone-100"}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "School" && <SchoolTab settings={settings} reload={load} flash={flash} admin={user?.role === "admin"} />}
      {tab === "Academic" && <AcademicTab settings={settings} reload={load} flash={flash} admin={user?.role === "admin"} />}
      {tab === "AI Provider" && <AiTab settings={settings} reload={load} flash={flash} admin={user?.role === "admin"} />}
      {tab === "Users" && <UsersTab admin={user?.role === "admin"} selfId={user?.id} />}
      {tab === "Backup & Data" && <BackupTab admin={user?.role === "admin"} flash={flash} />}
    </div>
  );
}

/* ---------------------------------- School --------------------------------- */
function SchoolTab({ settings, reload, flash, admin }: { settings: SettingsType; reload: () => void; flash: (m: string) => void; admin: boolean }) {
  const [schoolName, setSchoolName] = useState(settings.school_name);
  const [address, setAddress] = useState(settings.school_address);
  const [tagline, setTagline] = useState(settings.school_tagline);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const logoInput = useRef<HTMLInputElement>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api.put("/api/settings", { school_name: schoolName, school_address: address, school_tagline: tagline });
      flash("School details saved");
      reload();
    } catch (ex) {
      setErr(ex instanceof ApiError ? ex.message : "Could not save settings.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadLogo(f: File) {
    setBusy(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("file", f);
      await api.post("/api/settings/logo", fd);
      flash("School logo updated");
      reload();
    } catch (ex) {
      setErr(ex instanceof ApiError ? ex.message : "Could not upload the logo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="max-w-2xl space-y-5">
      <Card>
        <CardHeader><CardTitle>School Identity</CardTitle></CardHeader>
        <CardBody className="space-y-3">
          <div className="flex items-center gap-4">
            <img src={settings.logo_url || "/api/settings/logo"} alt="School logo" className="h-14 w-auto max-w-[220px] rounded-md border border-stone-200 bg-white object-contain px-2 py-1" />
            <div>
              <input ref={logoInput} type="file" accept=".png,.jpg,.jpeg" hidden onChange={(e) => e.target.files?.[0] && uploadLogo(e.target.files[0])} />
              <Button type="button" variant="outline" size="sm" onClick={() => logoInput.current?.click()} disabled={!admin} loading={busy}>
                <Upload size={14} /> Upload Official Logo (PNG/JPG)
              </Button>
              <p className="mt-1 text-[11px] text-stone-400">Shown on the dashboard, question papers, OMR sheets and report cards.</p>
            </div>
          </div>
          <div>
            <Label>School Name</Label>
            <Input value={schoolName} onChange={(e) => setSchoolName(e.target.value)} disabled={!admin} maxLength={120} />
          </div>
          <div>
            <Label>School Address</Label>
            <Input value={address} onChange={(e) => setAddress(e.target.value)} disabled={!admin} maxLength={300} />
          </div>
          <div>
            <Label>Tagline</Label>
            <Input value={tagline} onChange={(e) => setTagline(e.target.value)} disabled={!admin} maxLength={120} />
          </div>
        </CardBody>
      </Card>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <Button type="submit" disabled={!admin} loading={busy}>Save School Details</Button>
      {!admin && <p className="text-[11px] text-stone-400">Only an administrator can change these settings.</p>}
    </form>
  );
}

/* --------------------------------- Academic -------------------------------- */
function AcademicTab({ settings, reload, flash, admin }: { settings: SettingsType; reload: () => void; flash: (m: string) => void; admin: boolean }) {
  const [session, setSession] = useState(settings.academic_session);
  const [prefix, setPrefix] = useState(settings.student_id_prefix);
  const [passing, setPassing] = useState(String(settings.passing_marks_default));
  const [template, setTemplate] = useState(settings.default_question_template);
  const [examTypes, setExamTypes] = useState(settings.exam_types.join(", "));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api.put("/api/settings", {
        academic_session: session,
        student_id_prefix: prefix.toUpperCase(),
        passing_marks_default: Number(passing),
        default_question_template: template,
        exam_types: examTypes.split(",").map((t) => t.trim()).filter(Boolean),
      });
      flash("Academic settings saved");
      reload();
    } catch (ex) {
      setErr(ex instanceof ApiError ? ex.message : "Could not save settings.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="max-w-2xl space-y-5">
      <Card>
        <CardHeader><CardTitle>Academic Configuration</CardTitle></CardHeader>
        <CardBody className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Academic Session</Label>
              <Input value={session} onChange={(e) => setSession(e.target.value)} placeholder="2026-27" disabled={!admin} maxLength={32} />
            </div>
            <div>
              <Label>Student ID Prefix</Label>
              <Input value={prefix} onChange={(e) => setPrefix(e.target.value)} disabled={!admin} maxLength={10} />
              <p className="mt-1 text-[11px] text-stone-400">IDs look like {prefix || "APWS"}-{session.split("-")[0] || "2026"}-0001</p>
            </div>
            <div>
              <Label>Default Passing Marks (%)</Label>
              <Input type="number" min={0} max={100} value={passing} onChange={(e) => setPassing(e.target.value)} disabled={!admin} />
            </div>
            <div>
              <Label>Default Question Paper Template</Label>
              <Select value={template} onChange={(e) => setTemplate(e.target.value)} disabled={!admin}>
                <option>Pi-Edge Academic</option>
                <option>Standard Examination</option>
                <option>Weekly Test</option>
                <option>Monthly Test</option>
                <option>Olympiad Practice</option>
                <option>Minimal Worksheet</option>
              </Select>
            </div>
          </div>
          <div>
            <Label>Examination Types (comma separated)</Label>
            <Input value={examTypes} onChange={(e) => setExamTypes(e.target.value)} disabled={!admin} />
          </div>
          <p className="rounded-lg bg-blue-50 px-3 py-2 text-[11px] text-blue-700">
            Classes, sections and subjects are managed in <strong>Class &amp; Subjects</strong> in the sidebar.
          </p>
        </CardBody>
      </Card>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <Button type="submit" disabled={!admin} loading={busy}>Save Academic Settings</Button>
    </form>
  );
}

/* -------------------------------- AI provider ------------------------------- */
function AiTab({ settings, reload, flash, admin }: { settings: SettingsType; reload: () => void; flash: (m: string) => void; admin: boolean }) {
  const [provider, setProvider] = useState(settings.ai_provider);
  const [baseUrl, setBaseUrl] = useState(settings.ai_base_url);
  const [model, setModel] = useState(settings.ai_model);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api.put("/api/settings", {
        ai_provider: provider,
        ai_base_url: baseUrl,
        ai_model: model,
        ...(apiKey.trim() ? { ai_api_key: apiKey.trim() } : {}),
      });
      flash("AI provider settings saved");
      setApiKey("");
      reload();
    } catch (ex) {
      setErr(ex instanceof ApiError ? ex.message : "Could not save settings.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="max-w-2xl space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-brand-600" /> AI Question Generation</CardTitle>
        </CardHeader>
        <CardBody className="space-y-3">
          <p className="rounded-lg bg-blue-50 px-3 py-2 text-[11px] text-blue-700">
            PiAssess works with any OpenAI-compatible provider. For safety, an API key set in the
            environment variable <code>PIASSESS_AI_API_KEY</code> always takes priority over the value stored here.
            The key is never shown in full after saving.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Provider Name (any label)</Label>
              <Input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="e.g. OpenRouter, Ollama, Zhipu" disabled={!admin} maxLength={64} />
            </div>
            <div>
              <Label>Model</Label>
              <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. glm-4.7-flash" disabled={!admin} maxLength={120} />
            </div>
            <div className="col-span-2">
              <Label>Service Address (Base URL) — ends without a slash</Label>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1" disabled={!admin} maxLength={300} />
            </div>
          </div>
          <div>
            <Label>API Key {settings.ai_api_key_set ? `(saved: ${settings.ai_api_key_masked})` : "(not set)"}</Label>
            <Input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={settings.ai_api_key_set ? "Type a new key to replace it" : "Paste the provider API key"} disabled={!admin} />
          </div>
        </CardBody>
      </Card>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <Button type="submit" disabled={!admin} loading={busy}>Save AI Settings</Button>
    </form>
  );
}

/* ----------------------------------- Users ---------------------------------- */
const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator — full access",
  exam_controller: "Exam Controller — examinations, OMR, results",
  teacher: "Teacher — question papers, evaluation, performance",
  viewer: "Viewer — read-only reports",
};

function UsersTab({ admin, selfId }: { admin: boolean; selfId?: number }) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ username: "", password: "", full_name: "", role: "teacher" });
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [resetting, setResetting] = useState<User | null>(null);
  const [newPass, setNewPass] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await api.get<User[]>("/api/settings/users"));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load users.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function addUser(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError("");
    try {
      await api.post("/api/settings/users", form);
      setAddOpen(false);
      setForm({ username: "", password: "", full_name: "", role: "teacher" });
      load();
    } catch (ex) {
      setFormError(ex instanceof ApiError ? ex.message : "Could not create the user.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(u: User) {
    try {
      await api.put(`/api/settings/users/${u.id}`, { is_active: !u.is_active });
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not update the user.");
    }
  }

  async function resetPassword(e: FormEvent) {
    e.preventDefault();
    if (!resetting) return;
    setBusy(true);
    setFormError("");
    try {
      await api.post(`/api/settings/users/${resetting.id}/set-password`, { new_password: newPass });
      setResetting(null);
      setNewPass("");
      load();
    } catch (ex) {
      setFormError(ex instanceof ApiError ? ex.message : "Could not reset the password.");
    } finally {
      setBusy(false);
    }
  }

  if (!admin)
    return (
      <Card>
        <CardBody className="flex items-center gap-3 text-sm text-stone-500">
          <ShieldCheck className="h-5 w-5 text-brand-600" />
          User accounts can only be managed by an administrator.
        </CardBody>
      </Card>
    );

  return (
    <div className="max-w-3xl">
      <Card>
        <CardHeader>
          <CardTitle>User Accounts & Roles</CardTitle>
          <Button size="sm" onClick={() => setAddOpen(true)}>Add User</Button>
        </CardHeader>
        {loading ? (
          <div className="flex h-40 items-center justify-center"><Spinner /></div>
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <CardBody className="space-y-2">
            {users.map((u) => (
              <div key={u.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-stone-200 px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-ink">
                    {u.full_name || u.username}
                    {u.id === selfId && <span className="ml-2 text-[11px] text-stone-400">(you)</span>}
                    {!u.is_active && <Badge tone="red">Deactivated</Badge>}
                    {u.must_change_password && u.is_active && <Badge tone="amber">Must change password</Badge>}
                  </p>
                  <p className="text-[11px] text-stone-400">@{u.username} · {ROLE_LABELS[u.role] ?? u.role} · last sign-in {fmtDateTime(u.last_login_at)}</p>
                </div>
                <div className="flex gap-1.5">
                  <Button size="sm" variant="outline" onClick={() => { setResetting(u); setNewPass(""); }}>Reset Password</Button>
                  {u.id !== selfId && (
                    <Button size="sm" variant={u.is_active ? "danger" : "success"} onClick={() => toggleActive(u)}>
                      {u.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </CardBody>
        )}
      </Card>

      {/* add user dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add User</DialogTitle>
            <DialogDescription>The new user must change the password at first sign-in.</DialogDescription>
          </DialogHeader>
          <form onSubmit={addUser}>
            <DialogBody className="space-y-3">
              <div>
                <Label>Full Name</Label>
                <Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} maxLength={120} />
              </div>
              <div>
                <Label>Username *</Label>
                <Input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} pattern="[a-zA-Z0-9._-]+" minLength={3} maxLength={64} required />
              </div>
              <div>
                <Label>Temporary Password * (min 8 characters)</Label>
                <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} minLength={8} required />
              </div>
              <div>
                <Label>Role *</Label>
                <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  {Object.entries(ROLE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </Select>
              </div>
              {formError && <p className="text-xs text-red-600">{formError}</p>}
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
              <Button type="submit" loading={busy}>Create User</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* reset password dialog */}
      <Dialog open={resetting !== null} onOpenChange={(o) => !o && setResetting(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Reset password for {resetting?.full_name || resetting?.username}</DialogTitle>
            <DialogDescription>Share the new password privately. The user will be asked to change it at next sign-in.</DialogDescription>
          </DialogHeader>
          <form onSubmit={resetPassword}>
            <DialogBody>
              <Label>New Password (min 8 characters)</Label>
              <Input type="password" value={newPass} onChange={(e) => setNewPass(e.target.value)} minLength={8} required autoFocus />
              {formError && <p className="mt-2 text-xs text-red-600">{formError}</p>}
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setResetting(null)}>Cancel</Button>
              <Button type="submit" loading={busy}>Set Password</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ----------------------------------- Backup --------------------------------- */
function BackupTab({ admin, flash }: { admin: boolean; flash: (m: string) => void }) {
  const [overview, setOverview] = useState<BackupOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [note, setNote] = useState<{ text: string; tone: "green" | "amber" } | null>(null);
  const [backingUp, setBackingUp] = useState(false);

  // schedule + Drive setup form
  const [autoOn, setAutoOn] = useState(false);
  const [intervalH, setIntervalH] = useState(24);
  const [folderId, setFolderId] = useState("");
  const [saFile, setSaFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  // Google Drive backups
  const [driveFiles, setDriveFiles] = useState<DriveFile[] | null>(null);
  const [listingDrive, setListingDrive] = useState(false);

  // pending actions needing confirmation
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [restoreDrive, setRestoreDrive] = useState<DriveFile | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BackupFile | null>(null);
  const [busyAction, setBusyAction] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const ov = await api.get<BackupOverview>("/api/backups");
      setOverview(ov);
      setAutoOn(ov.status.auto_enabled);
      setIntervalH(ov.status.interval_hours);
      setFolderId(ov.status.drive_folder_id);
      setErr("");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not load backup information.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function backupNow() {
    setBackingUp(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("upload_to_drive", "true");
      const r = await api.postForm<{ name: string; size: number; drive_note: string | null }>("/api/backups", fd);
      setNote({
        text: r.drive_note
          ? `Backup created (${fmtSize(r.size)}). ${r.drive_note}`
          : `Backup created (${fmtSize(r.size)}) — stored in backend/data/backups${overview?.status.drive_connected ? " and on Google Drive" : ""}.`,
        tone: r.drive_note ? "amber" : "green",
      });
      flash("Backup created");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not create the backup.");
    } finally {
      setBackingUp(false);
    }
  }

  async function saveSettings(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("auto_enabled", autoOn ? "true" : "false");
      fd.append("interval_hours", String(intervalH));
      fd.append("folder_id", folderId.trim());
      if (saFile) fd.append("sa_file", saFile);
      await api.postForm("/api/backups/settings", fd);
      flash("Backup settings saved");
      setSaFile(null);
      await load();
    } catch (ex) {
      setErr(ex instanceof ApiError ? ex.message : "Could not save the backup settings.");
    } finally {
      setSaving(false);
    }
  }

  async function testDrive() {
    setTesting(true);
    setErr("");
    try {
      const r = await api.post<{ folder_name: string; service_account: string }>("/api/backups/drive/test");
      setNote({ text: `✓ Connected to Drive folder "${r.folder_name}" as ${r.service_account}.`, tone: "green" });
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not connect to Google Drive.");
    } finally {
      setTesting(false);
    }
  }

  async function listDrive() {
    setListingDrive(true);
    setErr("");
    try {
      const r = await api.get<{ files: DriveFile[] }>("/api/backups/drive/files");
      setDriveFiles(r.files);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not list the Google Drive backups.");
    } finally {
      setListingDrive(false);
    }
  }

  /** Restores, then reloads the whole app (the database underneath has changed). */
  async function doRestore() {
    if (!restoreFile && !restoreDrive) return;
    setBusyAction(true);
    try {
      if (restoreFile) {
        const fd = new FormData();
        fd.append("file", restoreFile);
        await api.postForm("/api/backups/restore", fd);
      } else if (restoreDrive) {
        await api.post(`/api/backups/drive/files/${restoreDrive.id}/restore`);
      }
      setRestoreFile(null);
      setRestoreDrive(null);
      flash("Restore complete");
      window.location.reload(); // the data underneath changed — a fresh start is the honest view
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not restore the backup.");
      setBusyAction(false);
    }
  }

  async function doDelete() {
    if (!deleteTarget) return;
    setBusyAction(true);
    try {
      await api.delete(`/api/backups/${deleteTarget.name}`);
      setDeleteTarget(null);
      flash("Backup deleted");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not delete the backup.");
    } finally {
      setBusyAction(false);
    }
  }

  function download(name: string) {
    downloadFile(`/api/backups/${name}/download`, name);
  }

  if (!admin)
    return (
      <Card>
        <CardBody className="flex items-center gap-3 text-sm text-stone-500">
          <ShieldCheck className="h-5 w-5 text-brand-600" />
          Backups and restore can only be managed by an administrator.
        </CardBody>
      </Card>
    );

  if (loading || !overview)
    return <div className="flex h-40 items-center justify-center"><Spinner /></div>;

  const st = overview.status;

  return (
    <div className="max-w-3xl space-y-5">
      {note && (
        <p className={`rounded-lg px-3 py-2 text-xs ${note.tone === "green" ? "bg-green-50 text-green-800" : "bg-amber-50 text-amber-800"}`}>
          {note.text}
        </p>
      )}
      {err && <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{err}</p>}

      {/* status + manual backup */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><DatabaseBackup className="h-4 w-4 text-brand-600" /> Data Backup</CardTitle>
          <Button size="sm" onClick={backupNow} loading={backingUp}>
            <CloudUpload size={14} /> Back up now
          </Button>
        </CardHeader>
        <CardBody className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge tone={st.auto_enabled ? "green" : "neutral"}>
              Automatic backup: {st.auto_enabled ? `every ${st.interval_hours} h` : "off"}
            </Badge>
            <Badge tone={st.drive_connected ? "green" : "amber"}>
              Google Drive: {st.drive_connected ? "connected" : "not connected"}
            </Badge>
            {st.drive_last_upload && (
              <Badge tone="brand">Last Drive upload: {fmtDateTime(st.drive_last_upload)}</Badge>
            )}
          </div>
          <p className="text-sm text-stone-600">
            A backup is a zip file containing the complete database (students, examinations, results,
            settings) and every uploaded file — logos, documents and scanned OMR sheets. It is stored in
            the <code className="rounded bg-cream px-1">backend/data/backups</code> folder, and when Google
            Drive is connected the same zip is uploaded there automatically.
          </p>
        </CardBody>
      </Card>

      {/* schedule + Drive setup */}
      <Card>
        <CardHeader><CardTitle>Automatic Backup & Google Drive</CardTitle></CardHeader>
        <CardBody>
          <form onSubmit={saveSettings} className="space-y-4">
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex items-center gap-2 text-sm font-medium text-ink">
                <input type="checkbox" checked={autoOn} onChange={(e) => setAutoOn(e.target.checked)} className="h-4 w-4 accent-brand-600" />
                Back up automatically
              </label>
              <div className="w-40">
                <Label>Every (hours)</Label>
                <Select value={intervalH} onChange={(e) => setIntervalH(Number(e.target.value))} disabled={!autoOn}>
                  {[1, 2, 6, 12, 24, 48, 72, 168].map((h) => (
                    <option key={h} value={h}>{h === 24 ? "Daily (24 h)" : h === 168 ? "Weekly (168 h)" : `${h} h`}</option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="rounded-lg border border-brand-100 bg-brand-50/60 p-3">
              <p className="flex items-center gap-1.5 text-sm font-semibold text-brand-800"><Cloud size={15} /> Store backups in Google Drive</p>
              <p className="mt-1.5 text-xs leading-relaxed text-brand-800/80">
                One-time setup (about 5 minutes): in <strong>Google Cloud Console</strong> create a project,
                enable the <strong>Google Drive API</strong>, create a <strong>service account</strong> and
                download its JSON key. In Drive, create a folder (e.g. <em>PiAssess Backups</em>), share it
                with the service account's email address as <strong>Editor</strong>, then upload the key here
                and paste the folder's ID (the long code at the end of the folder's web address).
              </p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <Label>Service-account key (JSON)</Label>
                  <input type="file" accept=".json,application/json" hidden id="sa-file-input"
                         onChange={(e) => { setSaFile(e.target.files?.[0] ?? null); e.target.value = ""; }} />
                  <Button type="button" variant="outline" size="sm" onClick={() => (document.getElementById("sa-file-input") as HTMLInputElement)?.click()} className="w-full">
                    <Upload size={13} /> {saFile ? `Selected: ${saFile.name}` : "Upload key JSON"}
                  </Button>
                  {!saFile && (
                    <p className="mt-1 text-[11px] text-stone-400">
                      {st.drive_connected ? "A key is already saved — upload only to replace it." : "No key saved yet."}
                    </p>
                  )}
                </div>
                <div>
                  <Label>Google Drive folder ID</Label>
                  <Input value={folderId} onChange={(e) => setFolderId(e.target.value)} placeholder="e.g. 1AbC-dEfGhIjKlMnOpQrStUvWxYz" maxLength={128} />
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="submit" size="sm" loading={saving}>Save Backup Settings</Button>
                <Button type="button" variant="outline" size="sm" onClick={testDrive} loading={testing}>Test connection</Button>
              </div>
            </div>
          </form>
        </CardBody>
      </Card>

      {/* local backups */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><HardDriveDownload className="h-4 w-4 text-brand-600" /> Backups on this computer</CardTitle>
          <Button size="sm" variant="outline" onClick={load}><RefreshCw size={13} /> Refresh</Button>
        </CardHeader>
        {overview.backups.length === 0 ? (
          <CardBody>
            <p className="text-sm text-stone-500">No backups yet — click <strong>Back up now</strong> above to create the first one.</p>
          </CardBody>
        ) : (
          <CardBody className="p-0">
            <Table>
              <thead>
                <tr>
                  <TH>Backup file</TH>
                  <TH className="w-24">Size</TH>
                  <TH className="w-44">Created</TH>
                  <TH className="w-40"></TH>
                </tr>
              </thead>
              <tbody>
                {overview.backups.map((b) => (
                  <tr key={b.name} className="hover:bg-cream/60">
                    <TD className="font-medium"><span className="block truncate" title={b.name}>{b.name}</span></TD>
                    <TD>{fmtSize(b.size)}</TD>
                    <TD className="text-stone-500">{fmtDateTime(b.created_at)}</TD>
                    <TD>
                      <div className="flex justify-end gap-1.5">
                        <Button size="sm" variant="outline" onClick={() => download(b.name)} title="Download a copy">
                          <Download size={13} />
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => setDeleteTarget(b)} title="Delete this backup">
                          <Trash2 size={13} />
                        </Button>
                      </div>
                    </TD>
                  </tr>
                ))}
              </tbody>
            </Table>
          </CardBody>
        )}
      </Card>

      {/* restore section */}
      <Card>
        <CardHeader><CardTitle>Restore from a Backup</CardTitle></CardHeader>
        <CardBody className="space-y-3">
          <p className="text-sm text-stone-600">
            Restoring replaces <strong>everything</strong> currently in PiAssess — students, examinations,
            results and settings — with the contents of the chosen backup. Choose the zip file from this
            computer (a copy you downloaded), or pick one directly from Google Drive.
          </p>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <Label>Backup file (.zip)</Label>
              <input type="file" accept=".zip,application/zip" hidden id="restore-file-input"
                     onChange={(e) => { const f = e.target.files?.[0] ?? null; if (f) setRestoreFile(f); e.target.value = ""; }} />
              <Button variant="outline" size="sm" onClick={() => (document.getElementById("restore-file-input") as HTMLInputElement)?.click()}>
                <Upload size={13} /> Choose file to restore
              </Button>
            </div>
            <div>
              <Label>Google Drive</Label>
              <Button variant="outline" size="sm" onClick={st.drive_connected ? listDrive : () => setErr("Connect Google Drive above first.")} loading={listingDrive}>
                <Cloud size={13} /> List Drive backups
              </Button>
            </div>
          </div>
          {driveFiles !== null && (
            driveFiles.length === 0 ? (
              <p className="text-sm text-stone-500">The Drive folder has no backups yet — create one with <strong>Back up now</strong>.</p>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <TH>Drive backup</TH>
                    <TH className="w-24">Size</TH>
                    <TH className="w-44">Uploaded</TH>
                    <TH className="w-28"></TH>
                  </tr>
                </thead>
                <tbody>
                  {driveFiles.map((f) => (
                    <tr key={f.id} className="hover:bg-cream/60">
                      <TD className="font-medium"><span className="block truncate" title={f.name}>{f.name}</span></TD>
                      <TD>{fmtSize(f.size ?? 0)}</TD>
                      <TD className="text-stone-500">{f.createdTime ? fmtDateTime(f.createdTime) : "—"}</TD>
                      <TD>
                        <div className="flex justify-end gap-1.5">
                          <Button size="sm" variant="outline" onClick={() => downloadDrive(f.id, f.name)} title="Download a copy to this computer">
                            <Download size={13} />
                          </Button>
                          <Button size="sm" onClick={() => setRestoreDrive(f)}>Restore</Button>
                        </div>
                      </TD>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader><CardTitle>Recommended routine</CardTitle></CardHeader>
        <CardBody>
          <ol className="list-decimal space-y-1.5 pl-5 text-sm text-stone-600">
            <li>Connect Google Drive above — then every backup is safely off this computer, automatically.</li>
            <li>Keep the automatic backup on (daily is a good choice for a school).</li>
            <li>Also click <strong>Back up now</strong> after bulk imports or result days.</li>
            <li>To move PiAssess to a new computer: install it there, then restore from the latest Drive backup.</li>
          </ol>
        </CardBody>
      </Card>

      {/* confirm: restore */}
      <Dialog open={restoreFile !== null || restoreDrive !== null} onOpenChange={(o) => { if (!o) { setRestoreFile(null); setRestoreDrive(null); } }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Restore this backup?</DialogTitle>
            <DialogDescription>
              {restoreFile
                ? `Everything currently in PiAssess will be replaced with the contents of "${restoreFile.name}".`
                : `Everything currently in PiAssess will be replaced with the Drive backup "${restoreDrive?.name}".`}
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
              This cannot be undone. Students, examinations, results and settings added after this backup
              will be lost. You may need to sign in again when the restore finishes.
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setRestoreFile(null); setRestoreDrive(null); }}>Cancel</Button>
            <Button variant="danger" loading={busyAction} onClick={doRestore}>Yes, restore everything</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* confirm: delete local backup */}
      <Dialog open={deleteTarget !== null} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete backup?</DialogTitle>
            <DialogDescription>
              {deleteTarget?.name} will be removed from this computer. Copies already uploaded to Google Drive stay there.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" loading={busyAction} onClick={doDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Downloads a backup straight from Google Drive via the app (admin only). */
function downloadDrive(fileId: string, name: string) {
  downloadFile(`/api/backups/drive/files/${fileId}/download`, name);
}
