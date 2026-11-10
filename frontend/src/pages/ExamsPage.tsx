import { useCallback, useEffect, useState } from "react";
import { CalendarCheck, ClipboardCheck, FileDown, FileText, ListChecks, Plus, Pencil, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, downloadFile } from "../api/client";
import type { Exam, ExamList, Klass } from "../api/types";
import { Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, Input, Label, PageHeader, Select, Spinner, Table, TD, TH, Textarea } from "../components/ui";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/dialog";
import { fmtDate, STATUS_LABELS } from "../lib/utils";

interface ExamForm {
  name: string;
  exam_type: string;
  academic_session: string;
  class_id: string;
  subject_id: string;
  exam_date: string;
  max_marks: string;
  passing_marks: string;
  negative_marks: string;
  duration_minutes: string;
  status: Exam["status"];
  instructions: string;
}

const emptyForm: ExamForm = {
  name: "", exam_type: "Unit Test", academic_session: "", class_id: "", subject_id: "",
  exam_date: "", max_marks: "100", passing_marks: "33", negative_marks: "0", duration_minutes: "60", status: "draft", instructions: "",
};

export default function ExamsPage() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<ExamList | null>(null);
  const [classes, setClasses] = useState<Klass[]>([]);
  const [examTypes, setExamTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Exam | null>(null);
  const [form, setForm] = useState<ExamForm>(emptyForm);
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<Exam | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [omrMenuFor, setOmrMenuFor] = useState<number | null>(null);

  function downloadOmr(exam: Exam, kind: "blank" | "key" | "combined") {
    const base = (exam.name || "omr-sheet").replace(/[^A-Za-z0-9 -]+/g, "").trim() || "omr-sheet";
    if (kind === "combined") {
      downloadFile(`/api/papers/${exam.id}/export?format=pdf&doc=paper&with_omr=1&set=A`,
                   `${base}-Question-Paper-with-OMR.pdf`);
    } else {
      const file = kind === "key" ? `${base}-OMR-Answer-Key-Set-A.pdf` : `${base}-OMR-Sheet-Set-A.pdf`;
      downloadFile(`/api/papers/${exam.id}/omr?set=A${kind === "key" ? "&key=1" : ""}`, file);
    }
    setOmrMenuFor(null);
  }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setExams(await api.get<ExamList>("/api/exams"));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load examinations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    api.get<Klass[]>("/api/academics/classes").then(setClasses).catch(() => {});
    api.get<{ exam_types: string[] }>("/api/exams/meta").then((r) => setExamTypes(r.exam_types)).catch(() => {});
  }, [load]);

  function openCreate() {
    setEditing(null);
    setForm({ ...emptyForm, academic_session: "2026-27" });
    setFormError("");
    setDialogOpen(true);
  }

  function openEdit(e: Exam) {
    setEditing(e);
    setForm({
      name: e.name,
      exam_type: e.exam_type,
      academic_session: e.academic_session,
      class_id: String(e.class_id),
      subject_id: e.subject_id ? String(e.subject_id) : "",
      exam_date: e.exam_date ?? "",
      max_marks: String(e.max_marks),
      passing_marks: String(e.passing_marks),
      negative_marks: String(e.negative_marks ?? 0),
      duration_minutes: String(e.duration_minutes),
      status: e.status,
      instructions: e.instructions,
    });
    setFormError("");
    setDialogOpen(true);
  }

  async function save() {
    setBusy(true);
    setFormError("");
    try {
      const payload = {
        name: form.name.trim(),
        exam_type: form.exam_type,
        academic_session: form.academic_session,
        class_id: Number(form.class_id),
        subject_id: form.subject_id ? Number(form.subject_id) : null,
        exam_date: form.exam_date || null,
        max_marks: Number(form.max_marks),
        passing_marks: Number(form.passing_marks),
        negative_marks: Number(form.negative_marks) || 0,
        duration_minutes: Number(form.duration_minutes),
        status: form.status,
        instructions: form.instructions,
      };
      if (editing) await api.put(`/api/exams/${editing.id}`, payload);
      else await api.post("/api/exams", payload);
      setDialogOpen(false);
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Could not save the examination.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await api.delete(`/api/exams/${deleting.id}`);
      setDeleting(null);
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not delete the examination.");
    } finally {
      setDeleteBusy(false);
    }
  }

  const formClass = classes.find((c) => String(c.id) === form.class_id);

  return (
    <div>
      <PageHeader
        title="Examination Manager"
        description="Create examinations, track their status and prepare for question paper generation."
        actions={
          <Button onClick={openCreate}><Plus size={15} /> Create Examination</Button>
        }
      />

      <Card>
        {loading && !exams ? (
          <div className="flex h-48 items-center justify-center"><Spinner /></div>
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !exams || exams.items.length === 0 ? (
          <EmptyState
            icon={<CalendarCheck size={36} />}
            title="No examinations yet"
            description="Create your first examination. Its question paper, OMR sheets, scanned evaluations and results are all managed from here."
            action={<Button size="sm" className="mt-2" onClick={openCreate}>Create Examination</Button>}
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <TH>Examination</TH>
                <TH>Type</TH>
                <TH>Class</TH>
                <TH>Subject</TH>
                <TH>Date</TH>
                <TH>Max Marks</TH>
                <TH>Students</TH>
                <TH>Status</TH>
                <TH className="text-right">Actions</TH>
              </tr>
            </thead>
            <tbody>
              {exams.items.map((e) => (
                <tr key={e.id} className="hover:bg-cream/60">
                  <TD className="font-medium">{e.name}</TD>
                  <TD className="text-stone-500">{e.exam_type}</TD>
                  <TD>{e.class_name}</TD>
                  <TD className="text-stone-500">{e.subject_name || "—"}</TD>
                  <TD>{fmtDate(e.exam_date)}</TD>
                  <TD>{e.max_marks}</TD>
                  <TD>{e.student_count}</TD>
                  <TD>
                    <Badge tone={e.status === "published" ? "green" : e.status === "ready" ? "blue" : e.status === "archived" ? "neutral" : "amber"}>
                      {STATUS_LABELS[e.status] ?? e.status}
                    </Badge>
                  </TD>
                  <TD className="text-right">
                    <div className="flex justify-end gap-1">
                      <div className="relative">
                        <button
                          className={`rounded-md p-1.5 hover:bg-brand-50 hover:text-brand-700 ${omrMenuFor === e.id ? "bg-brand-50 text-brand-700" : "text-stone-400"}`}
                          title="OMR sheets — blank, answer-key copy, or combined with the question paper"
                          onClick={() => setOmrMenuFor(omrMenuFor === e.id ? null : e.id)}
                        >
                          <ListChecks size={15} />
                        </button>
                        {omrMenuFor === e.id && (
                          <>
                            <div className="fixed inset-0 z-10" onClick={() => setOmrMenuFor(null)} />
                            <div className="absolute right-0 top-full z-20 mt-1 w-72 rounded-lg border border-stone-200 bg-white py-1 text-left shadow-lg">
                              <button className="flex w-full items-start gap-2.5 px-3 py-2 text-sm hover:bg-cream" onClick={() => downloadOmr(e, "blank")}>
                                <ListChecks size={15} className="mt-0.5 shrink-0 text-brand-700" />
                                <span><b>OMR sheet — blank</b><br /><span className="text-xs text-stone-500">For students to fill (Set A)</span></span>
                              </button>
                              <button className="flex w-full items-start gap-2.5 px-3 py-2 text-sm hover:bg-cream" onClick={() => downloadOmr(e, "key")}>
                                <ClipboardCheck size={15} className="mt-0.5 shrink-0 text-brand-700" />
                                <span><b>OMR answer-key copy</b><br /><span className="text-xs text-stone-500">Correct bubbles darkened — for checking</span></span>
                              </button>
                              <button className="flex w-full items-start gap-2.5 px-3 py-2 text-sm hover:bg-cream" onClick={() => downloadOmr(e, "combined")}>
                                <FileDown size={15} className="mt-0.5 shrink-0 text-brand-700" />
                                <span><b>Question paper + OMR (one PDF)</b><br /><span className="text-xs text-stone-500">Print once — paper and sheet together</span></span>
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                      <button className="rounded-md p-1.5 text-stone-400 hover:bg-brand-50 hover:text-brand-700" title="Open Question Paper" onClick={() => navigate(`/exams/${e.id}`)}>
                        <FileText size={15} />
                      </button>
                      <button className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink" title="Edit" onClick={() => openEdit(e)}>
                        <Pencil size={15} />
                      </button>
                      <button className="rounded-md p-1.5 text-stone-400 hover:bg-red-50 hover:text-red-600" title="Delete" onClick={() => setDeleting(e)}>
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </TD>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {/* create/edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Examination" : "Create Examination"}</DialogTitle>
            <DialogDescription>
              {editing ? `Editing "${editing.name}".` : "Question papers, OMR sheets and results all attach to this examination."}
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label>Examination Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Half-Yearly Examination 2026 — Mathematics" maxLength={200} />
            </div>
            <div>
              <Label>Examination Type</Label>
              <Select value={form.exam_type} onChange={(e) => setForm({ ...form, exam_type: e.target.value })}>
                {(examTypes.length ? examTypes : ["Unit Test"]).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Academic Session</Label>
              <Input value={form.academic_session} onChange={(e) => setForm({ ...form, academic_session: e.target.value })} placeholder="2026-27" maxLength={32} />
            </div>
            <div>
              <Label>Class *</Label>
              <Select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value, subject_id: "" })} required>
                <option value="">Select class…</option>
                {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </div>
            <div>
              <Label>Subject</Label>
              <Select value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} disabled={!formClass}>
                <option value="">— (whole class) —</option>
                {formClass?.subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </div>
            <div>
              <Label>Examination Date</Label>
              <Input type="date" value={form.exam_date} onChange={(e) => setForm({ ...form, exam_date: e.target.value })} />
            </div>
            <div>
              <Label>Duration (minutes)</Label>
              <Input type="number" min={1} max={600} value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} />
            </div>
            <div>
              <Label>Maximum Marks</Label>
              <Input type="number" min={1} max={1000} value={form.max_marks} onChange={(e) => setForm({ ...form, max_marks: e.target.value })} />
            </div>
            <div>
              <Label>Passing Marks</Label>
              <Input type="number" min={0} max={1000} value={form.passing_marks} onChange={(e) => setForm({ ...form, passing_marks: e.target.value })} />
            </div>
            <div>
              <Label>Negative Marking (per wrong answer)</Label>
              <Input type="number" min={0} max={100} step="0.25" value={form.negative_marks} onChange={(e) => setForm({ ...form, negative_marks: e.target.value })} />
              <p className="mt-1 text-[11px] text-stone-500">0 = no deduction. Example: 0.25 cuts ¼ mark per wrong answer in OMR scoring.</p>
            </div>
            <div>
              <Label>Status</Label>
              <Select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as Exam["status"] })}>
                <option value="draft">Draft — still being prepared</option>
                <option value="ready">Ready — question paper in progress</option>
                <option value="published">Published — exam conducted</option>
                <option value="archived">Archived</option>
              </Select>
            </div>
            <div className="sm:col-span-2">
              <Label>Instructions (printed on the question paper)</Label>
              <Textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} maxLength={4000} />
            </div>
            {formError && <p className="text-xs text-red-600 sm:col-span-2">{formError}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={save} loading={busy} disabled={!form.name.trim() || !form.class_id}>
              {editing ? "Save Changes" : "Create Examination"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete "${deleting?.name ?? "examination"}"?`}
        description="This permanently removes the examination and its configuration. Question papers and results linked to it would also be affected."
        confirmLabel="Delete Permanently"
        onConfirm={confirmDelete}
        loading={deleteBusy}
      />
    </div>
  );
}
