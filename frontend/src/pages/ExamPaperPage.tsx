import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowDown, ArrowUp, FileDown, FileText, ListChecks, ListPlus, Printer, Save, Sparkles, Trash2,
} from "lucide-react";
import { api, ApiError, downloadFile } from "../api/client";
import type { Paper, PaperItem, Question, QuestionList, Settings } from "../api/types";
import { DIFFICULTY_LABELS, QUESTION_TYPE_LABELS, VERIFICATION_LABELS } from "../api/types";
import {
  Badge, Button, Card, CardBody, CardHeader, CardTitle, EmptyState, ErrorState,
  Input, Label, PageHeader, Select, Spinner,
} from "../components/ui";
import {
  Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "../components/dialog";
import { useAuth } from "../hooks/useAuth";
import { VerificationBadge } from "./aigenerator/GeneratorWizard";
import { fmtDate } from "../lib/utils";

type Row = { question_id: number; marks: number; question: Question };

export default function ExamPaperPage() {
  const { id } = useParams<{ id: string }>();
  const examId = Number(id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const canEdit = ["admin", "exam_controller", "teacher"].includes(user?.role ?? "");

  const [paper, setPaper] = useState<Paper | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [view, setView] = useState<"paper" | "key">("paper");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [bankOpen, setBankOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await api.get<Paper>(`/api/papers/${examId}`);
      setPaper(p);
      setRows(p.items.map((i) => ({ question_id: i.question_id, marks: i.marks, question: i.question })));
      setTitle(p.title);
      setInstructions(p.instructions);
      setLoadError("");
      setDirty(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setPaper(null);
      } else {
        setLoadError(e instanceof ApiError ? e.message : "Could not load the question paper.");
      }
    } finally {
      setLoading(false);
    }
  }, [examId]);

  useEffect(() => {
    load();
    api.get<Settings>("/api/settings").then(setSettings).catch(() => {});
  }, [load]);

  const totalMarks = useMemo(() => rows.reduce((s, r) => s + r.marks, 0), [rows]);

  function update(rowsNext: Row[]) {
    setRows(rowsNext);
    setDirty(true);
  }

  function move(idx: number, dir: -1 | 1) {
    const next = [...rows];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    update(next);
  }

  async function save() {
    setSaving(true);
    setSaveError("");
    try {
      const p = await api.put<Paper>(`/api/papers/${examId}`, {
        title,
        instructions,
        items: rows.map((r, i) => ({ question_id: r.question_id, position: i + 1, marks: r.marks })),
      });
      setPaper(p);
      setRows(p.items.map((i) => ({ question_id: i.question_id, marks: i.marks, question: i.question })));
      setDirty(false);
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Could not save the paper.");
    } finally {
      setSaving(false);
    }
  }

  async function createEmptyPaper() {
    setSaving(true);
    setSaveError("");
    try {
      const p = await api.put<Paper>(`/api/papers/${examId}`, { title: "", instructions: "", items: [] });
      setPaper(p);
      setDirty(false);
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Could not create the paper.");
    } finally {
      setSaving(false);
    }
  }

  function print() {
    window.print();
  }

  const hasObjective = (paper?.items ?? []).some((it) => (it.question.options?.length ?? 0) >= 2);

  function exportPaper(format: "pdf" | "docx", withOmr = false) {
    const base = (paper?.exam_name || "question-paper").replace(/[^A-Za-z0-9 -]+/g, "").trim() || "question-paper";
    const label = (view === "key" ? "Answer-Key" : "Question-Paper") + (withOmr ? "-with-OMR-Sheet" : "");
    const omrParams = withOmr ? "&with_omr=1&set=A" : "";
    downloadFile(`/api/papers/${examId}/export?format=${format}&doc=${view}${omrParams}`, `${base}-${label}.${format}`);
  }

  function exportOmr() {
    const base = (paper?.exam_name || "question-paper").replace(/[^A-Za-z0-9 -]+/g, "").trim() || "question-paper";
    downloadFile(`/api/papers/${examId}/omr?set=A`, `${base}-OMR-Sheet-Set-A.pdf`);
  }

  if (loading) {
    return <div className="flex h-64 items-center justify-center"><Spinner /></div>;
  }

  // ------------------------------------------------------- no paper yet
  if (paper === null) {
    return (
      <div>
        <PageHeader
          title="Question Paper"
          description={`Examination #${examId} — no question paper has been assembled yet.`}
          actions={<Button variant="outline" onClick={() => navigate("/exams")}><FileText size={15} /> All Examinations</Button>}
        />
        <Card className="max-w-2xl">
          {loadError ? (
            <ErrorState message={loadError} onRetry={load} />
          ) : (
            <EmptyState
              icon={<FileText size={36} />}
              title="No question paper yet"
              description="Generate questions with the AI Question Paper Generator, or create an empty paper and add questions from the Question Bank."
              action={
                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  <Button onClick={() => navigate("/ai-generator")}><Sparkles size={15} /> Open AI Generator</Button>
                  {canEdit && (
                    <Button variant="outline" loading={saving} onClick={createEmptyPaper}>
                      <ListPlus size={15} /> Start an Empty Paper
                    </Button>
                  )}
                </div>
              }
            />
          )}
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="no-print">
        <PageHeader
          title={paper.exam_name || "Question Paper"}
          description={`${paper.class_name}${paper.subject_name ? " · " + paper.subject_name : ""} — edit the list on the left; the print preview updates on the right.`}
          actions={
            <>
              <Button variant="outline" onClick={() => navigate("/exams")}>All Examinations</Button>
              {canEdit && (
                <Button onClick={() => setBankOpen(true)}><ListPlus size={15} /> Add from Bank</Button>
              )}
              <Button variant="outline" onClick={print}><Printer size={15} /> Print</Button>
              <Button variant="outline" onClick={() => exportPaper("pdf")} title={`Download the ${view === "key" ? "answer key" : "question paper"} as a print-ready PDF`}>
                <FileDown size={15} /> PDF
              </Button>
              <Button variant="outline" onClick={() => exportPaper("docx")} title={`Download the ${view === "key" ? "answer key" : "question paper"} as an editable Word file`}>
                <FileDown size={15} /> Word
              </Button>
              {hasObjective && (
                <Button variant="outline" onClick={exportOmr} title="Download a printable OMR bubble sheet for the paper's MCQ questions">
                  <ListChecks size={15} /> OMR
                </Button>
              )}
              {view === "paper" && hasObjective && (
                <Button variant="outline" onClick={() => exportPaper("pdf", true)} title="Question paper and OMR bubble sheet combined into one PDF — print once, hand out both">
                  <FileDown size={15} /> PDF + OMR
                </Button>
              )}
              {canEdit && (
                <Button variant="success" onClick={save} loading={saving} disabled={!dirty}>
                  <Save size={15} /> {dirty ? "Save Changes" : "Saved"}
                </Button>
              )}
            </>
          }
        />
        {saveError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{saveError}</p>}
        {dirty && !saveError && (
          <p className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
            You have unsaved changes — press <strong>Save Changes</strong> to keep them.
          </p>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        {/* ------------------------------------------------ editor column */}
        <div className="no-print space-y-4">
          {canEdit ? (
            <>
              <Card>
                <CardHeader><CardTitle>Paper heading</CardTitle></CardHeader>
                <CardBody className="space-y-3">
                  <div>
                    <Label>Paper title (shown above the questions)</Label>
                    <Input value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} maxLength={200}
                      placeholder={paper.exam_name} />
                  </div>
                  <div>
                    <Label>General instructions (printed under the heading)</Label>
                    <textarea
                      className="min-h-[90px] w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                      value={instructions}
                      onChange={(e) => { setInstructions(e.target.value); setDirty(true); }}
                      maxLength={4000}
                      placeholder="e.g. All questions are compulsory. Marks are shown in the right margin."
                    />
                  </div>
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Questions ({rows.length}) · {totalMarks} marks</CardTitle>
                  <span className="text-[11px] text-stone-400">Use the arrows to set the order.</span>
                </CardHeader>
                <CardBody className="space-y-2">
                  {rows.length === 0 && (
                    <p className="py-4 text-center text-sm text-stone-500">
                      No questions yet. Use <strong>Add from Bank</strong> or the AI Generator.
                    </p>
                  )}
                  {rows.map((r, idx) => (
                    <div key={r.question_id} className="flex items-start gap-2 rounded-lg border border-stone-200 p-2.5">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                        {idx + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="line-clamp-2 whitespace-pre-wrap text-sm text-ink">{r.question.text}</p>
                        <div className="mt-1 flex flex-wrap items-center gap-1">
                          <Badge tone="brand">{QUESTION_TYPE_LABELS[r.question.qtype] ?? r.question.qtype}</Badge>
                          <Badge tone="neutral">{DIFFICULTY_LABELS[r.question.difficulty] ?? r.question.difficulty}</Badge>
                          {r.question.verification === "verified" && (
                            <Badge tone="green">{VERIFICATION_LABELS.verified}</Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex w-16 shrink-0 items-center gap-1">
                        <Label className="sr-only">Marks</Label>
                        <Input
                          type="number" min={1} max={100} value={r.marks} disabled={!canEdit}
                          onChange={(e) => update(rows.map((x, i) => (i === idx ? { ...r, marks: Math.max(1, Number(e.target.value) || 1) } : x)))}
                          title="Marks for this question"
                        />
                      </div>
                      <div className="flex shrink-0 flex-col">
                        <button className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-ink disabled:opacity-30"
                          disabled={idx === 0} onClick={() => move(idx, -1)} title="Move up"><ArrowUp size={14} /></button>
                        <button className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-ink disabled:opacity-30"
                          disabled={idx === rows.length - 1} onClick={() => move(idx, 1)} title="Move down"><ArrowDown size={14} /></button>
                      </div>
                      <button className="mt-0.5 shrink-0 rounded p-1 text-stone-400 hover:bg-red-50 hover:text-red-600"
                        onClick={() => update(rows.filter((_, i) => i !== idx))} title="Remove from paper">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </CardBody>
              </Card>
            </>
          ) : (
            <Card>
              <CardBody className="text-sm text-stone-500">
                You have read-only access. Ask an exam controller or teacher to edit the paper.
              </CardBody>
            </Card>
          )}
        </div>

        {/* ------------------------------------------------ preview column */}
        <div>
          <div className="no-print mb-2 flex items-center justify-between">
            <div className="flex rounded-lg border border-stone-200 bg-white p-0.5 text-xs">
              {(["paper", "key"] as const).map((v) => (
                <button key={v}
                  className={`rounded-md px-3 py-1.5 font-medium ${view === v ? "bg-brand-600 text-cream" : "text-stone-500 hover:text-ink"}`}
                  onClick={() => setView(v)}>
                  {v === "paper" ? "Question Paper" : "Answer Key"}
                </button>
              ))}
            </div>
            <span className="text-[11px] text-stone-400">Live preview — exactly what prints</span>
          </div>

          <PaperPreview
            view={view}
            title={title || paper.exam_name}
            instructions={instructions || paper.instructions}
            classNameLabel={paper.class_name}
            subject={paper.subject_name}
            session={paper.academic_session}
            date={paper.exam_date}
            duration={paper.duration_minutes}
            maxMarks={paper.exam_max_marks || totalMarks}
            totalMarks={totalMarks}
            rows={rows}
            logoUrl={settings?.logo_url || "/logo.svg"}
          />
        </div>
      </div>

      <AddFromBankDialog
        open={bankOpen}
        onClose={() => setBankOpen(false)}
        defaultClassId={paper.class_id}
        existingIds={new Set(rows.map((r) => r.question_id))}
        onAdd={(picked) => {
          update([...rows, ...picked.map((q) => ({ question_id: q.id, marks: q.marks, question: q }))]);
          setBankOpen(false);
        }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ preview */
function PaperPreview({
  view, title, instructions, classNameLabel, subject, session, date, duration,
  maxMarks, totalMarks, rows, logoUrl,
}: {
  view: "paper" | "key";
  title: string;
  instructions: string;
  classNameLabel: string;
  subject: string;
  session: string;
  date: string | null;
  duration: number;
  maxMarks: number;
  totalMarks: number;
  rows: Row[];
  logoUrl: string;
}) {
  return (
    <div className="print-area rounded-xl border border-stone-300 bg-white p-6 shadow-sm md:p-8">
      <header className="border-b-2 border-brand-600 pb-3 text-center">
        <img src={logoUrl} alt="" className="mx-auto h-14 w-auto object-contain" />
        <h2 className="mt-1 text-lg font-bold uppercase tracking-wide text-ink">Pi World School</h2>
        <p className="text-[11px] text-stone-500">Forbesganj, Bihar{session ? ` · Session ${session}` : ""}</p>
        <h3 className="mt-3 text-base font-semibold text-ink">{title}</h3>
        <p className="mt-0.5 text-xs text-stone-600">
          {[
            classNameLabel && `Class: ${classNameLabel}`,
            subject && `Subject: ${subject}`,
            date && `Date: ${fmtDate(date)}`,
            duration ? `Time: ${duration} minutes` : "",
            `Maximum Marks: ${maxMarks}`,
          ].filter(Boolean).join("  ·  ")}
        </p>
      </header>

      {instructions && (
        <div className="mt-3 rounded-lg bg-cream px-3 py-2 text-xs text-ink">
          <p className="font-semibold">General Instructions:</p>
          <p className="whitespace-pre-wrap">{instructions}</p>
        </div>
      )}

      {view === "paper" ? (
        <ol className="mt-4 space-y-4">
          {rows.map((r, idx) => (
            <li key={r.question_id} className="flex gap-3">
              <span className="text-sm font-semibold text-ink">{idx + 1}.</span>
              <div className="min-w-0 flex-1">
                <p className="whitespace-pre-wrap text-sm text-ink">{r.question.text}</p>
                {r.question.options.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {r.question.options.map((o, i) => (
                      <li key={i} className="text-sm text-stone-700">{o}</li>
                    ))}
                  </ul>
                )}
              </div>
              <span className="shrink-0 text-sm text-stone-600">[{r.marks}]</span>
            </li>
          ))}
          {rows.length === 0 && (
            <li className="py-6 text-center text-sm text-stone-400">No questions added yet.</li>
          )}
        </ol>
      ) : (
        <div className="mt-4 space-y-2">
          <p className="text-center text-xs font-semibold uppercase tracking-wide text-brand-700">Answer Key — for examiner use only</p>
          {rows.map((r, idx) => (
            <div key={r.question_id} className="flex gap-3 border-b border-stone-100 pb-2">
              <span className="text-sm font-semibold text-ink">{idx + 1}.</span>
              <div className="min-w-0 flex-1">
                <p className="line-clamp-1 text-xs text-stone-500">{r.question.text}</p>
                <p className="text-sm text-ink"><strong>Ans:</strong> {r.question.correct_answer || "—"}</p>
                {r.question.marking_notes && (
                  <p className="text-[11px] text-stone-500">Marking: {r.question.marking_notes}</p>
                )}
                <VerificationBadge state={r.question.verification} note={r.question.verification_note} />
              </div>
              <span className="shrink-0 text-sm text-stone-600">[{r.marks}]</span>
            </div>
          ))}
          {rows.length === 0 && <p className="py-6 text-center text-sm text-stone-400">No questions added yet.</p>}
        </div>
      )}

      <footer className="mt-5 flex justify-between border-t border-stone-200 pt-2 text-[11px] text-stone-500">
        <span>Total: {rows.length} question(s)</span>
        <span>Total Marks: {totalMarks}</span>
      </footer>
    </div>
  );
}

/* ----------------------------------------------------- add from bank dialog */
function AddFromBankDialog({
  open, onClose, defaultClassId, existingIds, onAdd,
}: {
  open: boolean;
  onClose: () => void;
  defaultClassId: number;
  existingIds: Set<number>;
  onAdd: (picked: Question[]) => void;
}) {
  const [items, setItems] = useState<QuestionList | null>(null);
  const [classes, setClasses] = useState<{ id: number; name: string }[]>([]);
  const [classId, setClassId] = useState(String(defaultClassId || ""));
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    api.get<{ id: number; name: string }[]>("/api/academics/classes").then(setClasses).catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    const params = new URLSearchParams({ page_size: "50" });
    if (classId) params.set("class_id", classId);
    if (search.trim()) params.set("search", search.trim());
    if (typeFilter) params.set("qtype", typeFilter);
    const t = setTimeout(() => {
      api.get<QuestionList>(`/api/questions?${params.toString()}`)
        .then((r) => { setItems(r); setError(""); })
        .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load the bank."))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [open, classId, search, typeFilter]);

  const pickedQuestions = (items?.items ?? []).filter((q) => picked.has(q.id));

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Add Questions from the Bank</DialogTitle>
          <DialogDescription>
            Questions already in this paper are dimmed. Added questions start with their bank marks.
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Input className="min-w-[180px] flex-1" placeholder="Search the bank…" value={search}
              onChange={(e) => setSearch(e.target.value)} />
            <Select className="w-32" value={classId} onChange={(e) => setClassId(e.target.value)}>
              <option value="">All classes</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
            <Select className="w-44" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">All types</option>
              {Object.entries(QUESTION_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </div>

          <div className="max-h-[50vh] space-y-1.5 overflow-y-auto rounded-lg border border-stone-200 p-2">
            {loading && !items ? (
              <div className="flex h-24 items-center justify-center"><Spinner /></div>
            ) : error ? (
              <ErrorState message={error} />
            ) : !items || items.items.length === 0 ? (
              <p className="py-8 text-center text-sm text-stone-500">
                No matching questions. Generate some with the AI Generator first.
              </p>
            ) : (
              items.items.map((q) => {
                const inPaper = existingIds.has(q.id);
                const isPicked = picked.has(q.id);
                return (
                  <label key={q.id}
                    className={`flex cursor-pointer items-start gap-2.5 rounded-lg border p-2.5 text-sm ${
                      inPaper ? "border-stone-100 bg-stone-50 opacity-50" : isPicked ? "border-brand-400 bg-brand-50" : "border-stone-200 hover:bg-cream/60"
                    }`}>
                    <input type="checkbox" className="mt-1 accent-[#791D32]" disabled={inPaper}
                      checked={isPicked}
                      onChange={(e) => {
                        const next = new Set(picked);
                        if (e.target.checked) next.add(q.id); else next.delete(q.id);
                        setPicked(next);
                      }} />
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 whitespace-pre-wrap text-ink">{q.text}</p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        <Badge tone="brand">{QUESTION_TYPE_LABELS[q.qtype] ?? q.qtype}</Badge>
                        <Badge tone="neutral">{q.marks} mark{q.marks !== 1 && "s"}</Badge>
                        {inPaper && <Badge tone="amber">already in paper</Badge>}
                      </div>
                    </div>
                  </label>
                );
              })
            )}
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button disabled={pickedQuestions.length === 0} onClick={() => onAdd(pickedQuestions)}>
            Add {pickedQuestions.length || ""} Question{pickedQuestions.length !== 1 && "s"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
