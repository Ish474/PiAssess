import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, CalendarCheck, Sparkles, BookOpen, LayoutGrid, ScanLine, BarChart3,
  UsersRound, School, FolderOpen, Settings as SettingsIcon, LifeBuoy, LogOut, Bell, ChevronsUpDown, CircleCheck,
  CheckCheck, ClipboardList,
} from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { cn } from "../../lib/utils";
import { api } from "../../api/client";
import type { NotificationItem, Settings } from "../../api/types";
import { Dialog, DialogBody, DialogContent, DialogHeader, DialogTitle } from "../dialog";
import { Button, Spinner } from "../ui";
import { fmtDateTime } from "../../lib/utils";

const NOTIFS_SEEN_KEY = "piassess_notifs_seen";

function activityGlyph(action: string) {
  if (action.includes("upload") || action.includes("import")) return "⬆";
  if (action.includes("process") || action.includes("correct")) return "✓";
  if (action.includes("delete")) return "✕";
  if (action.includes("backup") || action.includes("export")) return "↧";
  return "•";
}

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  roles?: string[]; // when omitted, visible to everyone
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Overview",
    items: [{ to: "/", label: "Dashboard", icon: <LayoutDashboard size={17} /> }],
  },
  {
    section: "Examinations",
    items: [
      { to: "/exams", label: "Examination Manager", icon: <CalendarCheck size={17} /> },
      { to: "/ai-generator", label: "AI Question Paper Generator", icon: <Sparkles size={17} />, roles: ["admin", "exam_controller", "teacher"] },
      { to: "/question-bank", label: "Question Bank", icon: <BookOpen size={17} />, roles: ["admin", "exam_controller", "teacher"] },
    ],
  },
  {
    section: "OMR & Evaluation",
    items: [
      { to: "/omr-designer", label: "OMR Sheet Designer", icon: <LayoutGrid size={17} />, roles: ["admin", "exam_controller"] },
      { to: "/omr-processing", label: "OMR Processing", icon: <ScanLine size={17} />, roles: ["admin", "exam_controller", "teacher"] },
    ],
  },
  {
    section: "Results",
    items: [
      { to: "/results", label: "Results & Reports", icon: <BarChart3 size={17} /> },
    ],
  },
  {
    section: "Records",
    items: [
      { to: "/students", label: "Student Database", icon: <UsersRound size={17} />, roles: ["admin", "exam_controller", "teacher"] },
      { to: "/academics", label: "Class & Subjects", icon: <School size={17} />, roles: ["admin", "exam_controller"] },
      { to: "/documents", label: "Document Library", icon: <FolderOpen size={17} /> },
    ],
  },
  {
    section: "System",
    items: [{ to: "/settings", label: "Settings", icon: <SettingsIcon size={17} />, roles: ["admin", "exam_controller", "teacher"] }],
  },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [userMenu, setUserMenu] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifs, setNotifs] = useState<NotificationItem[] | null>(null);
  const [unread, setUnread] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);

  const refreshNotifications = () => {
    api.get<{ items: NotificationItem[] }>("/api/dashboard/notifications").then((r) => {
      setNotifs(r.items);
      const seen = localStorage.getItem(NOTIFS_SEEN_KEY) || "";
      setUnread(r.items.filter((n) => n.created_at > seen).length);
    }).catch(() => {});
  };

  useEffect(() => {
    api.get<Settings>("/api/settings").then(setSettings).catch(() => {});
    refreshNotifications();
  }, [location.pathname]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setUserMenu(false);
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, []);

  function toggleNotifs() {
    const next = !notifOpen;
    setNotifOpen(next);
    if (next && notifs === null) refreshNotifications();
  }

  function markAllSeen() {
    if (notifs && notifs.length > 0) {
      localStorage.setItem(NOTIFS_SEEN_KEY, notifs[0].created_at);
      setUnread(0);
    }
  }

  const role = user?.role ?? "viewer";
  const pageTitle =
    NAV.flatMap((s) => s.items).find((i) => i.to === location.pathname)?.label ??
    (location.pathname.startsWith("/exams/") ? "Question Paper"
      : location.pathname === "/students" ? "Student Database" : "PiAssess");

  return (
    <div className="flex min-h-screen bg-cream">
      {/* -------------------------------- sidebar -------------------------------- */}
      <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-brand-600">
        <div className="flex items-center gap-3 px-4 py-4">
          <img
            src={settings?.logo_url || "/logo.svg"}
            alt="School logo"
            className="h-10 w-auto max-w-[180px] rounded-md bg-white object-contain px-1.5 py-1"
          />
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-2">
          {NAV.map((group) => {
            const items = group.items.filter((i) => !i.roles || i.roles.includes(role));
            if (!items.length) return null;
            return (
              <div key={group.section}>
                <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-brand-300">{group.section}</p>
                <div className="space-y-0.5">
                  {items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors",
                          isActive ? "bg-brand-800 text-cream" : "text-brand-100 hover:bg-brand-500/40 hover:text-cream"
                        )
                      }
                    >
                      <span className="shrink-0">{item.icon}</span>
                      <span className="flex-1 truncate">{item.label}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            );
          })}
        </nav>

        <div className="border-t border-brand-500/40 px-4 py-3">
          <p className="text-xs font-medium text-cream">Pi World School</p>
          <p className="text-[11px] text-brand-200">Forbesganj, Bihar</p>
        </div>
      </aside>

      {/* --------------------------------- main ---------------------------------- */}
      <div className="ml-60 flex min-h-screen flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-stone-200 bg-white px-6">
          <h1 className="text-sm font-semibold text-ink">{pageTitle}</h1>
          <div className="flex items-center gap-3">
            <span className="hidden rounded-full bg-brand-100 px-3 py-1 text-[11px] font-medium text-brand-700 sm:inline">
              Academic Session {settings?.academic_session ?? "2026–27"}
            </span>
            <div className="relative" ref={notifRef}>
              <button
                onClick={toggleNotifs}
                className="relative rounded-lg p-2 text-stone-500 hover:bg-stone-100"
                title="Notifications"
              >
                <Bell size={17} />
                {unread > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white">
                    {unread > 9 ? "9+" : unread}
                  </span>
                )}
              </button>
              {notifOpen && (
                <div className="absolute right-0 top-11 w-80 overflow-hidden rounded-xl border border-stone-200 bg-white shadow-lg">
                  <div className="flex items-center justify-between border-b border-stone-100 px-3.5 py-2.5">
                    <p className="text-sm font-semibold text-ink">Recent activity</p>
                    {unread > 0 && (
                      <button onClick={markAllSeen} className="flex items-center gap-1 text-[11px] font-medium text-brand-600 hover:text-brand-700">
                        <CheckCheck size={13} /> Mark all seen
                      </button>
                    )}
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    {!notifs ? (
                      <div className="px-3.5 py-6 text-center"><Spinner /></div>
                    ) : notifs.length === 0 ? (
                      <p className="px-3.5 py-6 text-center text-xs text-stone-400">Nothing yet — activity such as uploads and scans will appear here.</p>
                    ) : (
                      notifs.map((n) => (
                        <div key={n.id} className="flex items-start gap-2.5 border-b border-stone-50 px-3.5 py-2.5 last:border-0 hover:bg-cream/60">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[10px] text-brand-700">
                            {activityGlyph(n.action)}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-xs text-ink" title={n.details}>{n.details || n.action}</p>
                            <p className="text-[10px] text-stone-400">{n.username} · {fmtDateTime(n.created_at)}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
            <button onClick={() => setHelpOpen(true)} className="rounded-lg p-2 text-stone-500 hover:bg-stone-100" title="Help & support">
              <LifeBuoy size={17} />
            </button>
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setUserMenu((v) => !v)}
                className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-stone-100"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-cream">
                  {(user?.full_name || user?.username || "?").slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden text-xs font-medium text-ink md:inline">{user?.full_name || user?.username}</span>
                <ChevronsUpDown size={13} className="text-stone-400" />
              </button>
              {userMenu && (
                <div className="absolute right-0 top-11 w-52 rounded-xl border border-stone-200 bg-white py-1.5 shadow-lg">
                  <div className="px-3.5 py-2">
                    <p className="text-sm font-medium text-ink">{user?.full_name || user?.username}</p>
                    <p className="text-[11px] capitalize text-stone-500">{user?.role?.replace("_", " ")}</p>
                  </div>
                  <button
                    onClick={async () => {
                      await logout();
                      navigate("/login");
                    }}
                    className="flex w-full items-center gap-2 px-3.5 py-2 text-sm text-red-600 hover:bg-red-50"
                  >
                    <LogOut size={15} /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 px-6 py-6">
          <Outlet />
        </main>

        <footer className="px-6 pb-5 pt-1 text-[11px] text-stone-400">
          PiAssess · Academic Evaluation Suite · Pi World School, Forbesganj, Bihar
        </footer>
      </div>

      {/* help dialog */}
      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CircleCheck className="h-4 w-4 text-green-600" /> Help & Support
            </DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3 text-sm text-ink">
            <p><strong>Getting started:</strong> follow the checklist on the Dashboard — add classes and subjects, then students, then create an examination.</p>
            <p><strong>Students:</strong> use "Import" to upload an Excel or CSV file; the import wizard checks every row and reports problems before anything is saved.</p>
            <p><strong>Security:</strong> sign out when you leave the computer. Sessions expire automatically after 12 hours.</p>
            <p className="rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700">
              For further assistance, contact the system administrator at the school office.
            </p>
            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setHelpOpen(false)}>Close</Button>
            </div>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  );
}
