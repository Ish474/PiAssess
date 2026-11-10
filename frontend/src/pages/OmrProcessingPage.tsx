import { useCallback, useEffect, useRef, useState } from "react";
import {
  ScanLine, Upload, Eye, Trash2, Play, CheckCircle2, AlertTriangle,
  XCircle, FileSearch, Loader2,
} from "lucide-react";
import { api, ApiError } from "../api/client";
import type { Exam, ExamList, OmrScan, OmrScanDetail, OmrScanList, OmrScanRow, Student, StudentList } from "../api/types";
import {
  Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, PageHeader,
  Select, Spinner, StatCard, Table, TD, TH,
} from "../components/ui";
import { Dialog, DialogBody, DialogContent, DialogHeader, DialogTitle } from "../components/dialog";
import { fmtDateTime } from "../lib/utils";

/** A..E for MCQ rows, 0..9 for integer rows. */
function optLabel(i: number, isInteger: boolean): string {
  return isInteger ? String(i) : String.fromCharCode(65 + i);
}

function bandInfo(scan: OmrScan): { tone: "green" | "amber" | "red" | "blue" | "neutral"; label: string } {
  if (scan.status === "processing") return { tone: "blue", label: "Reading…" };
  if (scan.status === "pending") return { tone: "neutral", label: "Waiting" };
  if (scan.status === "failed") return { tone: "red", label: "Unreadable" };
  if (scan.confidence_band === "GREEN") return { tone: "green", label: "Clean read" };
  if (scan.confidence_band === "YELLOW") return { tone: "amber", label: "Needs review" };
  if (scan.confidence_band === "RED") return { tone: "red", label: "Unreadable" };
  return { tone: "neutral", label: scan.status };
}

function verdictChip(r: OmrScanRow) {
  if (r.verdict === "multi") return <Badge tone="amber">Double mark</Badge>;
  if (r.verdict === "review") return <Badge tone="blue">Faint mark</Badge>;
  if (r.verdict === "unanswered") return <Badge tone="neutral">Blank</Badge>;
  return r.correct ? <Badge tone="green">Correct</Badge> : <Badge tone="red">Wrong</Badge>;
}

export default function OmrProcessingPage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [examId, setExamId] = useState<number | 0>(0);
  const [setLetter, setSetLetter] = useState("A");

  const [scans, setScans] = useState<OmrScanList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pageError, setPageError] = useState("");

  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [queue, setQueue] = useState<{ i: number; n: number; name: string } | null>(null);
  const queueCancelled = useRef(false);

  const [detail, setDetail] = useState<OmrScanDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [correcting, setCorrecting] = useState<number | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [assigning, setAssigning] = useState(false);

  const [deleting, setDeleting] = useState<OmrScan | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<ExamList>("/api/exams").then((r) => setExams(r.items)).catch(() => {});
  }, []);

  // students of the exam's class — for assigning scanned sheets
  useEffect(() => {
    const exam = exams.find((e) => e.id === examId);
    setStudents([]);
    if (exam) {
      api.get<StudentList>(`/api/students?class_id=${exam.class_id}&page_size=100`)
        .then((r) => setStudents(r.items))
        .catch(() => {});
    }
  }, [examId, exams]);

  const load = useCallback(async () => {
    if (!examId) return;
    setLoading(true);
    try {
      setScans(await api.get<OmrScanList>(`/api/papers/${examId}/omr-scans`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the scanned sheets.");
    } finally {
      setLoading(false);
    }
  }, [examId]);

  useEffect(() => {
    setScans(null);
    if (examId) load();
  }, [examId, load]);

  async function uploadAndProcess() {
    if (!examId || files.length === 0) return;
    setUploading(true);
    setPageError("");
    try {
      const fd = new FormData();
      fd.append("set", setLetter);
      files.forEach((f) => fd.append("files", f));
      const res = await api.postForm<{ items: OmrScan[] }>(`/api/papers/${examId}/omr-scans`, fd);
      setFiles([]);
      await load();
      // read every sheet one by one, keeping the table live
      queueCancelled.current = false;
      const ids = res.items.map((s) => s.id);
      for (let i = 0; i < ids.length; i++) {
        if (queueCancelled.current) break;
        setQueue({ i: i + 1, n: ids.length, name: res.items[i].original_name });
        try {
          await api.post(`/api/papers/${examId}/omr-scans/${ids[i]}/process`);
        } catch { /* the row keeps its failed status and message */ }
        await load();
      }
      setQueue(null);
    } catch (e) {
      setPageError(e instanceof ApiError ? e.message : "The upload failed.");
      setQueue(null);
    } finally {
      setUploading(false);
    }
  }

  async function processOne(scan: OmrScan) {
    if (!examId) return;
    setScans((prev) => prev ? {
      ...prev,
      items: prev.items.map((s) => s.id === scan.id ? { ...s, status: "processing" } : s),
    } : prev);
    try {
      await api.post(`/api/papers/${examId}/omr-scans/${scan.id}/process`);
    } catch (e) {
      setPageError(e instanceof ApiError ? e.message : "Could not read this sheet.");
    }
    await load();
  }

  const pendingCount = scans ? scans.items.filter((s) => s.status === "pending" || s.status === "failed").length : 0;

  async function processPending() {
    if (!examId || !scans) return;
    const targets = scans.items.filter((s) => s.status === "pending" || s.status === "failed");
    queueCancelled.current = false;
    for (let i = 0; i < targets.length; i++) {
      if (queueCancelled.current) break;
      setQueue({ i: i + 1, n: targets.length, name: targets[i].original_name });
      await processOne(targets[i]);
    }
    setQueue(null);
  }

  async function openDetail(scan: OmrScan) {
    if (!examId) return;
    setDetailLoading(true);
    try {
      setDetail(await api.get<OmrScanDetail>(`/api/papers/${examId}/omr-scans/${scan.id}`));
    } catch (e) {
      setPageError(e instanceof ApiError ? e.message : "Could not open this result.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function override(row: OmrScanRow, chosen: number | null) {
    if (!examId || !detail) return;
    setCorrecting(row.position);
    try {
      const q = chosen === null ? `?position=${row.position}` : `?position=${row.position}&chosen=${chosen}`;
      await api.patch(`/api/papers/${examId}/omr-scans/${detail.id}/responses${q}`);
      setDetail(await api.get<OmrScanDetail>(`/api/papers/${examId}/omr-scans/${detail.id}`));
      await load();
    } catch (e) {
      setPageError(e instanceof ApiError ? e.message : "Could not save the correction.");
    } finally {
      setCorrecting(null);
    }
  }

  async function assign(scanId: number, studentId: number | null) {
    if (!examId) return;
    setAssigning(true);
    try {
      await api.post(`/api/papers/${examId}/omr-scans/${scanId}/assign`, { student_id: studentId });
      setDetail(await api.get<OmrScanDetail>(`/api/papers/${examId}/omr-scans/${scanId}`));
      await load();
    } catch (e) {
      setPageError(e instanceof ApiError ? e.message : "Could not assign the student.");
    } finally {
      setAssigning(false);
    }
  }

  const exam = exams.find((e) => e.id === examId);

  return (
    <div>
      <PageHeader
        title="OMR Processing"
        description="Upload photos or scans of the OMR answer sheets — the app straightens each sheet, reads the bubbles and scores them against the answer key."
      />

      <Card className="mb-4 flex flex-wrap items-end gap-3 p-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-stone-600">Examination</label>
          <Select className="w-72" value={examId || ""} onChange={(e) => setExamId(Number(e.target.value) || 0)}>
            <option value="">Choose examination…</option>
            {exams.map((e) => (
              <option key={e.id} value={e.id}>{e.name} — {e.class_name}{e.subject_name ? ` · ${e.subject_name}` : ""}</option>
            ))}
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-stone-600">Question paper set</label>
          <Select className="w-24" value={setLetter} onChange={(e) => setSetLetter(e.target.value)} disabled={!examId}>
            {["A", "B", "C", "D"].map((s) => <option key={s} value={s}>Set {s}</option>)}
          </Select>
        </div>
        <div className="min-w-64 flex-1">
          <label className="mb-1 block text-xs font-medium text-stone-600">
            Scanned sheets (JPG / PNG images, or a PDF — each PDF page = one sheet)
          </label>
          <input
            type="file" multiple accept=".jpg,.jpeg,.png,.pdf" disabled={!examId || uploading}
            className="w-full text-xs text-stone-600"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
        </div>
        <Button onClick={uploadAndProcess} loading={uploading} disabled={!examId || files.length === 0}>
          <Upload size={15} /> Upload &amp; read {files.length > 0 ? `(${files.length})` : ""}
        </Button>
      </Card>

      {queue && (
        <Card className="mb-4 flex items-center gap-3 border-brand-200 bg-brand-50 p-3 text-sm text-brand-800">
          <Loader2 size={16} className="animate-spin" />
          Reading sheet {queue.i} of {queue.n}: <span className="font-medium">{queue.name}</span>
        </Card>
      )}
      {pageError && (
        <Card className="mb-4 border-red-200 bg-red-50 p-3 text-sm text-red-700">{pageError}</Card>
      )}

      {exam && exam.negative_marks > 0 && (
        <Card className="mb-4 border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <strong>Negative marking is on</strong> for this exam: every wrong answer deducts{" "}
          {exam.negative_marks} mark{exam.negative_marks === 1 ? "" : "s"} (blank questions lose nothing).
          Scores shown here already include the deduction.
        </Card>
      )}

      {!examId ? (
        <Card>
          <EmptyState
            icon={<ScanLine size={36} />}
            title="Choose an examination first"
            description="Pick the examination whose OMR sheets you scanned. Only its own paper design can read the sheets."
          />
        </Card>
      ) : loading && !scans ? (
        <Card><div className="flex h-40 items-center justify-center"><Spinner /></div></Card>
      ) : error ? (
        <Card><ErrorState message={error} onRetry={load} /></Card>
      ) : !scans || scans.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<ScanLine size={36} />}
            title="No scanned sheets yet"
            description={`Print the OMR sheets for ${exam?.name ?? "this exam"} (Set ${setLetter}), let students mark them, then upload a photo or scan of each sheet — JPG, PNG, or one PDF containing the whole class stack (every page becomes one sheet).`}
          />
        </Card>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Sheets" value={scans.summary.total} icon={<ScanLine size={16} />} />
            <StatCard label="Scored cleanly" value={scans.summary.processed} icon={<CheckCircle2 size={16} />} />
            <StatCard label="Needs review" value={scans.summary.needs_review} icon={<AlertTriangle size={16} />}
              hint="Faint or double marks a human should confirm" />
            <StatCard label="Unreadable" value={scans.summary.failed} icon={<XCircle size={16} />}
              hint="Wrong sheet, bad photo, or missing guide squares" />
          </div>

          <Card>
            <div className="flex items-center justify-between px-5 pt-4">
              <p className="text-xs text-stone-500">
                {exam?.name} · Set {setLetter} — sheets scanned for other sets keep the set they were uploaded with.
              </p>
              {pendingCount > 0 && (
                <Button size="sm" variant="outline" onClick={processPending} disabled={queue !== null}>
                  <Play size={13} /> Read {pendingCount} pending sheet{pendingCount > 1 ? "s" : ""}
                </Button>
              )}
            </div>
            <Table>
              <thead>
                <tr>
                  <TH>File</TH>
                  <TH>Set</TH>
                  <TH>Status</TH>
                  <TH>Score</TH>
                  <TH>Read at</TH>
                  <TH className="text-right">Actions</TH>
                </tr>
              </thead>
              <tbody>
                {scans.items.map((s) => {
                  const info = bandInfo(s);
                  return (
                    <tr key={s.id} className="hover:bg-cream/60">
                      <TD className="max-w-[260px]">
                        <span className="block truncate font-medium" title={s.original_name}>{s.original_name}</span>
                        {s.student_name && (
                          <span className="block text-xs text-brand-700">👤 {s.student_name}</span>
                        )}
                        {s.error_message && (
                          <span className="block max-w-[260px] truncate text-xs text-red-600" title={s.error_message}>
                            {s.error_message}
                          </span>
                        )}
                      </TD>
                      <TD><Badge tone="brand">{s.set_letter}</Badge></TD>
                      <TD><Badge tone={info.tone}>{info.label}</Badge></TD>
                      <TD>
                        {s.score !== null && s.max_score !== null
                          ? <span className="font-semibold">{s.score} / {s.max_score}</span>
                          : <span className="text-stone-400">—</span>}
                      </TD>
                      <TD className="text-stone-500">{s.processed_at ? fmtDateTime(s.processed_at) : "—"}</TD>
                      <TD className="text-right">
                        <div className="flex justify-end gap-1">
                          {(s.status === "pending" || s.status === "failed") && (
                            <button
                              className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink"
                              title={s.status === "failed" ? "Try reading again" : "Read this sheet"}
                              onClick={() => processOne(s)}
                            >
                              <Play size={15} />
                            </button>
                          )}
                          {(s.status === "processed" || s.status === "review") && (
                            <button
                              className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink"
                              title="View answers & correct"
                              onClick={() => openDetail(s)}
                            >
                              <FileSearch size={15} />
                            </button>
                          )}
                          <button
                            className="rounded-md p-1.5 text-stone-400 hover:bg-red-50 hover:text-red-600"
                            title="Delete"
                            onClick={() => setDeleting(s)}
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </TD>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </Card>
        </>
      )}

      {/* result detail + manual correction */}
      <Dialog open={detailLoading || detail !== null} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle className="flex flex-wrap items-center gap-2">
              {detail?.original_name ?? "Loading…"}
              {detail && <Badge tone={bandInfo(detail).tone}>{bandInfo(detail).label}</Badge>}
              {detail && detail.score !== null && detail.max_score !== null && (
                <span className="text-sm font-semibold text-ink">
                  Score {detail.score} / {detail.max_score}
                </span>
              )}
            </DialogTitle>
          </DialogHeader>
          <DialogBody>
            {detailLoading || !detail ? (
              <div className="flex h-40 items-center justify-center"><Spinner /></div>
            ) : (
              <div className="max-h-[60vh] space-y-1.5 overflow-y-auto pr-1">
                <div className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border border-brand-100 bg-brand-50 px-3 py-2">
                  <span className="text-xs font-medium text-brand-800">This sheet belongs to:</span>
                  <Select
                    className="w-56" disabled={assigning}
                    value={detail.student_id ?? ""}
                    onChange={(e) => assign(detail.id, e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">Not assigned (shows as sheet name)</option>
                    {students.map((st) => (
                      <option key={st.id} value={st.id}>
                        {st.roll_no ? `Roll ${st.roll_no} · ` : ""}{st.full_name}
                      </option>
                    ))}
                  </Select>
                  {assigning && <Spinner className="h-4 w-4" />}
                </div>
                <p className="mb-2 text-xs text-stone-500">
                  The outlined letter is the answer key. Click a letter to correct what the machine read
                  (useful for faint or double marks); corrections are recorded in the activity log.
                </p>
                {detail.responses.map((r) => {
                  const isInt = r.integer ?? false;
                  const n = r.n_opts ?? 4;
                  return (
                    <div key={r.position} className="flex flex-wrap items-center gap-2 rounded-lg border border-stone-100 px-3 py-1.5">
                      <span className="w-14 text-sm font-medium">Q{r.position}</span>
                      <span className="text-xs text-stone-400">{r.marks} mk</span>
                      {verdictChip(r)}
                      {r.overridden && <Badge tone="blue">edited</Badge>}
                      <span className="text-xs text-stone-400">
                        dark {Math.round(r.fill * 100)}%
                      </span>
                      <div className="ml-auto flex items-center gap-1">
                        {Array.from({ length: n }, (_, i) => {
                          const isChosen = r.chosen === i;
                          const isKey = r.key === i;
                          return (
                            <button
                              key={i}
                              disabled={correcting !== null}
                              onClick={() => override(r, i)}
                              title={isKey ? `Key answer (${optLabel(i, isInt)})` : `Mark ${optLabel(i, isInt)}`}
                              className={[
                                "h-6 w-6 rounded border text-[11px] font-medium",
                                isChosen
                                  ? "border-ink bg-ink text-white"
                                  : isKey
                                    ? "border-ink bg-white text-ink"
                                    : "border-stone-200 bg-white text-stone-500 hover:border-stone-400",
                                correcting === r.position ? "opacity-50" : "",
                              ].join(" ")}
                            >
                              {optLabel(i, isInt)}
                            </button>
                          );
                        })}
                        <button
                          disabled={correcting !== null}
                          onClick={() => override(r, null)}
                          title="Clear this answer"
                          className="h-6 rounded border border-stone-200 bg-white px-1.5 text-[11px] font-medium text-stone-500 hover:border-red-300 hover:text-red-600"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </DialogBody>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => { if (!o) setDeleting(null); }}
        title={`Delete scan "${deleting?.original_name ?? ""}"?`}
        description="The scanned image and its result are removed. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={async () => {
          if (!deleting || !examId) return;
          setBusy(true);
          try {
            await api.delete(`/api/papers/${examId}/omr-scans/${deleting.id}`);
            setDeleting(null);
            await load();
          } catch (e) {
            setPageError(e instanceof Error ? e.message : "Could not delete the scan.");
          } finally {
            setBusy(false);
          }
        }}
        loading={busy}
      />
    </div>
  );
}
