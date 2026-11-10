import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BarChart3, Award, TrendingUp, UsersRound, Download, ScanLine, Trophy, Medal } from "lucide-react";
import { api, ApiError } from "../api/client";
import type { Exam, ExamList, ExamResults } from "../api/types";
import {
  Badge, Button, Card, EmptyState, ErrorState, PageHeader, Select, Spinner,
  StatCard, Table, TD, TH,
} from "../components/ui";
import { fmtDate } from "../lib/utils";

export default function ResultsPage() {
  const [searchParams] = useSearchParams();
  const [exams, setExams] = useState<Exam[]>([]);
  const [examId, setExamId] = useState<number | 0>(0);
  const [results, setResults] = useState<ExamResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<ExamList>("/api/exams").then((r) => {
      setExams(r.items);
      const fromUrl = Number(searchParams.get("exam")) || 0;
      if (fromUrl && r.items.some((e) => e.id === fromUrl)) setExamId(fromUrl);
    }).catch(() => {});
  }, [searchParams]);

  const load = useCallback(async () => {
    if (!examId) return;
    setLoading(true);
    try {
      setResults(await api.get<ExamResults>(`/api/papers/${examId}/results`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the results.");
    } finally {
      setLoading(false);
    }
  }, [examId]);

  useEffect(() => {
    setResults(null);
    if (examId) load();
  }, [examId, load]);

  function exportCsv() {
    if (!results) return;
    const esc = (v: unknown) => {
      const s = v === null || v === undefined ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const head = ["Rank", "Student", "Roll No", "Set", "Score", "Max", "Percent", "Result", "Reading", "Sheet"];
    const lines = [
      [`Results — ${results.exam.name}`, `${results.exam.class_name}`, "", "", "", "", "", "", "", ""],
      head.join(","),
      ...results.rows.map((r) => [
        r.rank ?? "-", esc(r.student_name ?? "Not assigned"), r.roll_no ?? "", r.set,
        r.score, r.max_score, r.percent, r.passed ? "PASS" : "FAIL", r.band || "-", esc(r.sheet),
      ].join(",")),
      "",
      ["Sheets scored", results.stats.sheets_scored, "Highest", results.stats.highest ?? "-", "", "", "", "", "", ""].join(","),
      ["Class average %", results.stats.average_percent ?? "-", "Pass %", results.stats.pass_percent ?? "-", "", "", "", "", "", ""].join(","),
    ];
    const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `results-${results.exam.name.replace(/[^\w-]+/g, "_").toLowerCase()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const exam = exams.find((e) => e.id === examId);
  const hasData = results && results.rows.length > 0;

  return (
    <div>
      <PageHeader
        title="Results & Reports"
        description="Exam-wise results assembled from the evaluated OMR sheets — rankings, class statistics and a downloadable result sheet."
      />

      <Card className="mb-4 flex flex-wrap items-center gap-3 p-4">
        <div className="flex-1 min-w-64">
          <label className="mb-1 block text-xs font-medium text-stone-600">Examination</label>
          <Select className="w-full max-w-md" value={examId || ""} onChange={(e) => setExamId(Number(e.target.value) || 0)}>
            <option value="">Choose examination…</option>
            {exams.map((e) => (
              <option key={e.id} value={e.id}>{e.name} — {e.class_name}{e.subject_name ? ` · ${e.subject_name}` : ""}</option>
            ))}
          </Select>
        </div>
        {hasData && (
          <Button variant="outline" onClick={exportCsv}>
            <Download size={15} /> Download result sheet (CSV)
          </Button>
        )}
      </Card>

      {!examId ? (
        <Card>
          <EmptyState
            icon={<BarChart3 size={36} />}
            title="Choose an examination"
            description="Pick an examination whose OMR sheets have been scanned and evaluated — the results appear here automatically."
          />
        </Card>
      ) : loading && !results ? (
        <Card><div className="flex h-40 items-center justify-center"><Spinner /></div></Card>
      ) : error ? (
        <Card><ErrorState message={error} onRetry={load} /></Card>
      ) : !results || !hasData ? (
        <Card>
          <EmptyState
            icon={<ScanLine size={36} />}
            title="No scored sheets for this exam yet"
            description="Upload and evaluate the scanned OMR sheets first. Results appear here as soon as the first sheet is scored."
            action={
              <Link to={`/omr-processing${examId ? `?exam=${examId}` : ""}`}>
                <Button size="sm" className="mt-2"><ScanLine size={14} /> Open OMR Processing</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          <Card className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-1 p-4 text-sm">
            <span className="font-semibold text-ink">{results.exam.name}</span>
            <span className="text-stone-500">{results.exam.class_name}{results.exam.subject_name ? ` · ${results.exam.subject_name}` : ""}</span>
            {results.exam.exam_date && <span className="text-stone-500">{fmtDate(results.exam.exam_date)}</span>}
            <span className="text-stone-500">Max {results.exam.max_marks} · Pass at {results.exam.passing_marks}</span>
            {results.exam.negative_marks > 0 && (
              <Badge tone="amber">Negative marking −{results.exam.negative_marks} per wrong</Badge>
            )}
          </Card>

          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
            <StatCard label="Sheets scored" value={results.stats.sheets_scored} icon={<ScanLine size={16} />} />
            <StatCard label="Students ranked" value={results.stats.students_ranked} icon={<UsersRound size={16} />}
              hint={results.stats.unassigned > 0 ? `${results.stats.unassigned} sheet(s) not assigned yet` : "Every sheet has a student"} />
            <StatCard label="Highest score" value={results.stats.highest ?? "—"} icon={<Trophy size={16} />} />
            <StatCard label="Class average" value={results.stats.average_percent != null ? `${results.stats.average_percent}%` : "—"} icon={<TrendingUp size={16} />} />
            <StatCard label="Pass percentage" value={results.stats.pass_percent != null ? `${results.stats.pass_percent}%` : "—"}
              icon={<Award size={16} />} hint={`${results.stats.pass_count} of ${results.stats.sheets_scored} passed`} />
          </div>

          {results.stats.unassigned > 0 && (
            <Card className="mb-4 border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {results.stats.unassigned} sheet{results.stats.unassigned > 1 ? "s are" : " is"} not assigned to a student yet —
              open <Link className="font-semibold underline" to={`/omr-processing?exam=${examId}`}>OMR Processing</Link> and pick
              the student for each sheet (the printed roll number is handwritten, so the scanner cannot read it honestly).
            </Card>
          )}

          <Card>
            <Table>
              <thead>
                <tr>
                  <TH className="w-14">Rank</TH>
                  <TH>Student</TH>
                  <TH>Roll No</TH>
                  <TH>Set</TH>
                  <TH>Score</TH>
                  <TH>Percent</TH>
                  <TH>Result</TH>
                  <TH>Reading</TH>
                  <TH>Sheet</TH>
                </tr>
              </thead>
              <tbody>
                {results.rows.map((r) => (
                  <tr key={r.scan_id} className="hover:bg-cream/60">
                    <TD>
                      {r.rank === 1 ? <Trophy size={15} className="text-amber-500" />
                        : r.rank === 2 ? <Medal size={15} className="text-stone-400" />
                        : r.rank === 3 ? <Medal size={15} className="text-amber-700" />
                        : r.rank ?? <span className="text-stone-300">—</span>}
                      {r.rank ? <span className="ml-1 text-xs text-stone-500">{r.rank}</span> : null}
                    </TD>
                    <TD className="font-medium">
                      {r.student_name ?? <span className="text-stone-400">Not assigned</span>}
                    </TD>
                    <TD className="text-stone-500">{r.roll_no ?? "—"}</TD>
                    <TD><Badge tone="brand">{r.set}</Badge></TD>
                    <TD className="font-semibold">{r.score} / {r.max_score}</TD>
                    <TD>{r.percent}%</TD>
                    <TD>
                      {r.passed ? <Badge tone="green">PASS</Badge> : <Badge tone="red">FAIL</Badge>}
                    </TD>
                    <TD>
                      {r.band === "GREEN" ? <Badge tone="green">Clean</Badge>
                        : r.band === "YELLOW" ? <Badge tone="amber">Reviewed</Badge>
                        : <Badge tone="neutral">—</Badge>}
                    </TD>
                    <TD className="max-w-[180px] truncate text-stone-400" title={r.sheet}>{r.sheet}</TD>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        </>
      )}
    </div>
  );
}
