import { Link } from "react-router-dom";
import { Sparkles, LayoutGrid, ScanLine, BarChart3, UsersRound, CalendarCheck, School as SchoolIcon,
  Circle, CircleCheck, ArrowRight, Clock, FileText, Upload, ClipboardList,
} from "lucide-react";
import { useApiData } from "../hooks/useApiData";
import { useAuth } from "../hooks/useAuth";
import type { Dashboard as DashboardData } from "../api/types";
import { Button, Card, CardBody, CardHeader, CardTitle, EmptyState, ErrorState, Spinner, StatCard, Badge, TD, TH, Table } from "../components/ui";
import { fmtDate, fmtDateTime, greeting, STATUS_LABELS } from "../lib/utils";

const ACTIONS = [
  { to: "/ai-generator", icon: <Sparkles size={20} />, title: "Generate Question Paper", desc: "Create high-quality question papers with automatically generated answers." },
  { to: "/omr-designer", icon: <LayoutGrid size={20} />, title: "Design OMR Sheet", desc: "Create printable answer sheets for objective examinations." },
  { to: "/omr-processing", icon: <ScanLine size={20} />, title: "Scan & Evaluate OMR", desc: "Upload scanned answer sheets and automatically calculate marks." },
  { to: "/results", icon: <BarChart3 size={20} />, title: "Results & Reports", desc: "Rankings, class statistics and downloadable result sheets." },
];

const CHECKLIST: { key: string; label: string; to?: string }[] = [
  { key: "classes_created", label: "Set up classes and sections", to: "/academics" },
  { key: "subjects_added", label: "Add subjects with maximum marks", to: "/academics" },
  { key: "students_added", label: "Add or import students", to: "/students" },
  { key: "exam_created", label: "Create your first examination", to: "/exams" },
  { key: "question_paper", label: "Generate a question paper", to: "/ai-generator" },
  { key: "omr_evaluated", label: "Scan and evaluate OMR sheets", to: "/omr-processing" },
  { key: "results_published", label: "View results & reports", to: "/results" },
];

function activityIcon(action: string) {
  if (action.includes("import")) return <Upload size={14} />;
  if (action.includes("exam")) return <CalendarCheck size={14} />;
  if (action.includes("backup")) return <FileText size={14} />;
  return <ClipboardList size={14} />;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useApiData<DashboardData>("/api/dashboard");

  if (loading)
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  if (error || !data) return <ErrorState message={error || "Could not load the dashboard."} onRetry={reload} />;

  const done = CHECKLIST.filter((c) => data.checklist[c.key]).length;
  const nextStep = CHECKLIST.find((c) => !data.checklist[c.key]);

  return (
    <div className="space-y-6">
      {/* welcome */}
      <div className="rounded-xl bg-brand-600 px-6 py-5 shadow-card">
        <h1 className="text-lg font-semibold text-cream">{greeting()}, {user?.full_name || user?.username || "Administrator"}</h1>
        <p className="mt-0.5 text-sm text-brand-200">
          {data.checklist.school_profile ? "Pi World School" : "Welcome to PiAssess"} · Academic Session 2026–27
        </p>
      </div>

      {/* primary actions */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {ACTIONS.map((a) => (
          <Link key={a.to} to={a.to} className="group">
            <Card className="h-full p-5 transition-shadow hover:shadow-md">
              <div className="flex items-start justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-600">{a.icon}</div>
              </div>
              <p className="mt-3 text-sm font-semibold text-ink">{a.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-stone-500">{a.desc}</p>
              <p className="mt-3 flex items-center gap-1 text-xs font-medium text-brand-600 opacity-70 group-hover:opacity-100">
                Open <ArrowRight size={12} />
              </p>
            </Card>
          </Link>
        ))}
      </div>

      {/* stats */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Students" value={data.total_students} icon={<UsersRound size={18} />} />
        <StatCard label="Total Examinations" value={data.total_examinations} icon={<CalendarCheck size={18} />} />
        <StatCard label="Total Subjects" value={data.total_subjects} icon={<SchoolIcon size={18} />} />
        <StatCard
          label="Average Class Performance"
          value={data.average_performance != null ? `${data.average_performance.toFixed(1)}%` : "—"}
          icon={<BarChart3 size={18} />}
          hint={data.average_performance == null ? "Available after the first evaluation" : undefined}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        {/* recent exams */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Recent Examinations</CardTitle>
            <Link to="/exams">
              <Button variant="ghost" size="sm">
                View all <ArrowRight size={13} />
              </Button>
            </Link>
          </CardHeader>
          {data.recent_exams.length === 0 ? (
            <EmptyState
              icon={<CalendarCheck size={36} />}
              title="No examinations yet"
              description="Create your first examination in the Examination Manager."
              action={
                <Link to="/exams">
                  <Button size="sm" className="mt-2">Create Examination</Button>
                </Link>
              }
            />
          ) : (
            <Table>
              <thead>
                <tr>
                  <TH>Examination</TH>
                  <TH>Class</TH>
                  <TH>Date</TH>
                  <TH>Students</TH>
                  <TH>Status</TH>
                  <TH>Results</TH>
                </tr>
              </thead>
              <tbody>
                {data.recent_exams.map((e) => (
                  <tr key={e.id} className="hover:bg-cream/60">
                    <TD className="font-medium">{e.name}</TD>
                    <TD>{e.class_name}</TD>
                    <TD>{fmtDate(e.exam_date)}</TD>
                    <TD>{e.student_count}</TD>
                    <TD>
                      <Badge tone={e.status === "published" ? "green" : e.status === "ready" ? "blue" : e.status === "archived" ? "neutral" : "amber"}>
                        {STATUS_LABELS[e.status] ?? e.status}
                      </Badge>
                    </TD>
                    <TD>
                      {e.results_available ? (
                        <Link to={`/results?exam=${e.id}`}><Badge tone="green">Available</Badge></Link>
                      ) : (
                        <span className="text-xs text-stone-400">Not scanned yet</span>
                      )}
                    </TD>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        {/* getting started */}
        <Card>
          <CardHeader>
            <CardTitle>Getting Started</CardTitle>
            <Badge tone={done === CHECKLIST.length ? "green" : "brand"}>{done}/{CHECKLIST.length} done</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            {CHECKLIST.map((c) => {
              const complete = data.checklist[c.key];
              const item = (
                <div className={cn2("flex items-start gap-2 rounded-lg px-2 py-1.5 text-sm", complete ? "text-stone-400" : "text-ink", !complete && c.to && "hover:bg-cream")}>
                  {complete ? <CircleCheck size={15} className="mt-0.5 shrink-0 text-green-600" /> : <Circle size={15} className="mt-0.5 shrink-0 text-stone-300" />}
                  <span className={complete ? "line-through decoration-stone-300" : ""}>{c.label}</span>
                </div>
              );
              return !complete && c.to ? (
                <Link key={c.key} to={c.to} className="block">{item}</Link>
              ) : (
                <div key={c.key}>{item}</div>
              );
            })}
            {nextStep && (
              <p className="pt-1 text-[11px] text-stone-400">
                Next step: <strong>{nextStep.label}</strong> — click the item above to open that module.
              </p>
            )}
          </CardBody>
        </Card>
      </div>

      {/* activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        {data.activity.length === 0 ? (
          <EmptyState icon={<Clock size={32} />} title="Nothing here yet" description="Actions such as added students and created examinations will appear here." />
        ) : (
          <CardBody className="space-y-1">
            {data.activity.map((a) => (
              <div key={a.id} className="flex items-start gap-3 rounded-lg px-2 py-1.5 hover:bg-cream/70">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-600">
                  {activityIcon(a.action)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-ink">{a.details || a.action}</p>
                  <p className="text-[11px] text-stone-400">{a.username} · {fmtDateTime(a.created_at)}</p>
                </div>
              </div>
            ))}
          </CardBody>
        )}
      </Card>
    </div>
  );
}

function cn2(...classes: (string | false | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
