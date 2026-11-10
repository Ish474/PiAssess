import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import type {
  AIStatus, DraftQuestion, Exam, ExamList, GenerateResponse, GenerateTypeRow, Question,
} from "../../api/types";
import { QUESTION_TYPE_LABELS, DIFFICULTY_LABELS, VERIFICATION_LABELS } from "../../api/types";
import {
  Badge, Button, Card, CardBody, CardHeader, CardTitle, Input, Label, PageHeader, Select, Spinner, Textarea,
} from "../../components/ui";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/dialog";
import {
  Sparkles, Upload, CheckCircle2, AlertTriangle, Pencil, Trash2, ArrowRight, ArrowLeft, Wand2, FileText, ShieldCheck,
} from "lucide-react";
import { DraftEditorDialog } from "./DraftEditorDialog";

/** Questions per AI call — small batches keep the JSON intact and retries cheap. */
const GENERATION_BATCH = 10;

/** Wizard steps: 1 exam → 2 chapters/material → 3 question mix → 4 generate & review → 5 saved */
export function GeneratorWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);

  // step 1
  const [exams, setExams] = useState<ExamList | null>(null);
  const [examId, setExamId] = useState<number | null>(null);

  // step 2
  const [chapters, setChapters] = useState("");
  const [contentText, setContentText] = useState("");
  const [extra, setExtra] = useState("");
  const [extracting, setExtracting] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  // step 3
  const [rows, setRows] = useState<GenerateTypeRow[]>([
    { type: "mcq", count: 5, difficulty: "easy", marks: 1 },
  ]);

  // step 4
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState("");
  const [drafts, setDrafts] = useState<DraftQuestion[]>([]);
  const [providerInfo, setProviderInfo] = useState("");
  const [skipInfo, setSkipInfo] = useState("");
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [pendingChunks, setPendingChunks] = useState<GenerateTypeRow[] | null>(null);

  // step 5
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<{ saved: number; duplicates_skipped: number } | null>(null);

  const [editingDraft, setEditingDraft] = useState<number | null>(null);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);

  useEffect(() => {
    api.get<ExamList>("/api/exams").then(setExams).catch(() => setExams({ items: [], total: 0 }));
    api.get<AIStatus>("/api/ai/status").then(setAiStatus).catch(() => setAiStatus(null));
  }, []);

  const exam = exams?.items.find((e) => e.id === examId) ?? null;
  const totalQuestions = rows.reduce((s, r) => s + r.count, 0);
  const totalMarks = rows.reduce((s, r) => s + r.count * r.marks, 0);
  const verifiedCount = drafts.filter((d) => d.verification === "verified").length;
  const reviewCount = drafts.filter((d) => d.verification === "needs_review").length;

  async function extractFile(f: File) {
    setExtracting(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await api.postForm<{ chars: number; text: string }>("/api/ai/extract", fd);
      setContentText((prev) => (prev ? prev + "\n\n" + res.text : res.text));
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "The file could not be read.");
    } finally {
      setExtracting(false);
    }
  }

  /**
   * Batched generation: the AI is far more reliable writing 10 questions per
   * call than 100+ in one giant (often truncated) response. The requested mix
   * is split into batches; earlier questions are passed as avoid-lists.
   */
  function buildQueue(typeRows: GenerateTypeRow[]): GenerateTypeRow[] {
    const queue: GenerateTypeRow[] = [];
    for (const row of typeRows) {
      let remaining = row.count;
      while (remaining > 0) {
        const take = Math.min(GENERATION_BATCH, remaining);
        queue.push({ ...row, count: take });
        remaining -= take;
      }
    }
    return queue;
  }

  async function runBatches(chunks: GenerateTypeRow[], clearFirst: boolean) {
    if (!exam) return;
    setGenerating(true);
    setGenError("");
    setProgress({ done: 0, total: chunks.length });
    // questions already on screen (or just removed via "regenerate similar") must not repeat
    const avoid = [...drafts.map((d) => d.text)];
    if (clearFirst) setDrafts([]);
    const collected: DraftQuestion[] = [];
    let skippedTotal = 0;
    const skippedNotes: string[] = [];

    for (let i = 0; i < chunks.length; i++) {
      setProgress({ done: i, total: chunks.length });
      try {
        const res = await api.post<GenerateResponse>("/api/ai/generate", {
          class_id: exam.class_id,
          subject_id: exam.subject_id,
          chapters,
          content_text: contentText,
          types: [chunks[i]],
          extra_instructions: extra,
          avoid_texts: avoid.slice(-30),
        });
        collected.push(...res.questions);
        avoid.push(...res.questions.map((q) => q.text));
        setDrafts((prev) => [...prev, ...res.questions]);
        setProviderInfo(`${res.provider} · ${res.model}`);
        skippedTotal += res.skipped;
        skippedNotes.push(...res.skipped_notes);
      } catch (e) {
        const remaining = chunks.slice(i);
        setPendingChunks(remaining.length ? remaining : null);
        setSkipInfo(skippedTotal > 0 ? `${skippedTotal} draft(s) were skipped — ${skippedNotes[0] ?? "malformed reply"}` : "");
        setGenError(
          `Generation stopped at batch ${i + 1} of ${chunks.length} — ${collected.length} question(s) generated so far are safe below. ` +
          (e instanceof ApiError ? e.message : "Please try again.")
        );
        setStep(4);
        return;
      }
    }
    setPendingChunks(null);
    setProgress(null);
    setSkipInfo(skippedTotal > 0 ? `${skippedTotal} draft(s) were skipped — ${skippedNotes[0] ?? "malformed reply"}` : "");
    setStep(4);
  }

  /** Replace one draft with a fresh question of the same type, difficulty and marks. */
  function regenerateOne(idx: number) {
    const d = drafts[idx];
    if (!d) return;
    setDrafts(drafts.filter((_, i) => i !== idx));
    runBatches(
      [{ type: d.qtype, count: 1, difficulty: d.difficulty === "mixed" ? "moderate" : d.difficulty, marks: d.marks }],
      false
    );
  }

  async function saveAll() {
    if (!exam) return;
    setSaving(true);
    try {
      const res = await api.post<{ saved: number; duplicates_skipped: number; paper_id: number | null }>(
        "/api/questions/bulk-save",
        {
          class_id: exam.class_id,
          subject_id: exam.subject_id,
          exam_id: exam.id,
          questions: drafts,
        }
      );
      setSaveResult({ saved: res.saved, duplicates_skipped: res.duplicates_skipped });
      setDrafts((prev) => prev.filter((_, i) => i < res.saved));
      setStep(5);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Could not save the questions.");
    } finally {
      setSaving(false);
    }
  }

  const steps = ["Examination", "Chapters & Material", "Question Mix", "Generate & Review", "Saved"];

  return (
    <div>
      <PageHeader
        title="AI Question Paper Generator"
        description="Create original questions from your chapters, review them, and build the question paper."
      />

      {/* AI provider honesty banner */}
      {aiStatus && !aiStatus.configured && (
        <div className="no-print mb-4 flex flex-wrap items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
          <AlertTriangle size={13} />
          <span>
            The AI provider is not configured yet — generation is disabled. Fill in the Service Address, Model and API key under
          </span>
          <button className="font-semibold underline" onClick={() => navigate("/settings")}>Settings → AI Provider</button>.
        </div>
      )}

      {/* stepper */}
      <div className="mb-5 flex flex-wrap gap-2">
        {steps.map((label, i) => {
          const n = i + 1;
          const state = step === n ? "current" : step > n ? "done" : "todo";
          return (
            <button
              key={label}
              onClick={() => n < step && setStep(n)}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium ${
                state === "current" ? "bg-brand-600 text-cream"
                : state === "done" ? "bg-green-50 text-green-700 cursor-pointer" : "bg-white text-stone-400"
              }`}
            >
              {state === "done" ? <CheckCircle2 size={13} /> : <span className="opacity-60">{n}</span>}
              {label}
            </button>
          );
        })}
      </div>

      {/* ---------------------------------------------------------- step 1 */}
      {step === 1 && (
        <Card className="max-w-2xl">
          <CardHeader><CardTitle>Step 1 · Choose the examination</CardTitle></CardHeader>
          <CardBody className="space-y-3">
            {exams === null ? (
              <div className="flex h-24 items-center justify-center"><Spinner /></div>
            ) : exams.items.length === 0 ? (
              <div className="text-sm text-stone-500">
                No examinations yet. <button className="font-medium text-brand-600 underline" onClick={() => navigate("/exams")}>Create one in the Examination Manager</button> first.
              </div>
            ) : (
              <>
                <div>
                  <Label>Examination *</Label>
                  <Select value={examId ?? ""} onChange={(e) => setExamId(Number(e.target.value))}>
                    <option value="">Select examination…</option>
                    {exams.items.map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name} — {e.class_name}{e.subject_name ? ` · ${e.subject_name}` : ""}
                      </option>
                    ))}
                  </Select>
                </div>
                {exam && (
                  <p className="rounded-lg bg-cream px-3 py-2 text-xs text-stone-600">
                    {exam.class_name} · {exam.subject_name || "All subjects"} · {exam.exam_type} ·
                    Maximum {exam.max_marks} marks · {exam.duration_minutes} minutes
                  </p>
                )}
                <div className="flex justify-end">
                  <Button disabled={!examId} onClick={() => setStep(2)}>Next: Chapters <ArrowRight size={14} /></Button>
                </div>
              </>
            )}
          </CardBody>
        </Card>
      )}

      {/* ---------------------------------------------------------- step 2 */}
      {step === 2 && (
        <Card className="max-w-3xl">
          <CardHeader><CardTitle>Step 2 · Chapters and learning material</CardTitle></CardHeader>
          <CardBody className="space-y-3">
            <div>
              <Label>Chapter name(s), comma separated</Label>
              <Input value={chapters} onChange={(e) => setChapters(e.target.value)} placeholder="e.g. Integers, Fractions and Decimals" maxLength={1000} />
            </div>
            <div>
              <Label>Upload textbook extract (PDF, DOCX or TXT) — optional</Label>
              <input ref={fileInput} type="file" accept=".pdf,.docx,.txt" hidden
                onChange={(e) => e.target.files?.[0] && extractFile(e.target.files[0])} />
              <Button variant="outline" size="sm" loading={extracting} onClick={() => fileInput.current?.click()}>
                <Upload size={14} /> {extracting ? "Reading the file…" : "Choose file"}
              </Button>
              <span className="ml-2 text-[11px] text-stone-400">The text is extracted and used as the source of truth for questions.</span>
            </div>
            <div>
              <Label>Chapter material / syllabus text (editable — paste notes here or edit the extraction)</Label>
              <Textarea
                className="min-h-[160px] font-mono text-xs"
                value={contentText}
                onChange={(e) => setContentText(e.target.value)}
                maxLength={200000}
                placeholder="Paste chapter content, definitions, formulas… (leave empty to let the AI use the standard syllabus for this class)"
              />
              <p className="mt-1 text-[11px] text-stone-400">{contentText.length} characters (first 12,000 are sent to the AI).</p>
            </div>
            <div>
              <Label>Extra instructions for the AI — optional</Label>
              <Textarea className="min-h-[60px]" value={extra} onChange={(e) => setExtra(e.target.value)} maxLength={2000}
                placeholder="e.g. base word problems on cricket scores; include one question about the water cycle" />
            </div>
            {genError && <p className="text-xs text-red-600">{genError}</p>}
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}><ArrowLeft size={14} /> Back</Button>
              <Button onClick={() => setStep(3)}>Next: Question Mix <ArrowRight size={14} /></Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* ---------------------------------------------------------- step 3 */}
      {step === 3 && (
        <Card className="max-w-3xl">
          <CardHeader><CardTitle>Step 3 · How many questions of each type?</CardTitle></CardHeader>
          <CardBody className="space-y-3">
            {rows.map((row, idx) => (
              <div key={idx} className="flex flex-wrap items-end gap-2">
                <div className="min-w-[200px] flex-1">
                  <Label>Question type</Label>
                  <Select value={row.type} onChange={(e) => setRows(rows.map((r, i) => i === idx ? { ...r, type: e.target.value } : r))}>
                    {Object.entries(QUESTION_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </Select>
                </div>
                <div className="w-24">
                  <Label>Count</Label>
                  <Input type="number" min={1} max={100} value={row.count}
                    onChange={(e) => setRows(rows.map((r, i) => i === idx ? { ...r, count: Math.max(1, Number(e.target.value) || 1) } : r))} />
                </div>
                <div className="w-40">
                  <Label>Difficulty</Label>
                  <Select value={row.difficulty} onChange={(e) => setRows(rows.map((r, i) => i === idx ? { ...r, difficulty: e.target.value } : r))}>
                    {Object.entries(DIFFICULTY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </Select>
                </div>
                <div className="w-24">
                  <Label>Marks each</Label>
                  <Input type="number" min={1} max={100} value={row.marks}
                    onChange={(e) => setRows(rows.map((r, i) => i === idx ? { ...r, marks: Math.max(1, Number(e.target.value) || 1) } : r))} />
                </div>
                {rows.length > 1 && (
                  <Button variant="ghost" size="icon" className="mb-0.5 text-red-500" title="Remove row"
                    onClick={() => setRows(rows.filter((_, i) => i !== idx))}>
                    <Trash2 size={15} />
                  </Button>
                )}
              </div>
            ))}
            <Button variant="secondary" size="sm" onClick={() => setRows([...rows, { type: "short", count: 2, difficulty: "moderate", marks: 2 }])}>
              + Add another type
            </Button>
            <p className="rounded-lg bg-cream px-3 py-2 text-sm text-ink">
              Total: <strong>{totalQuestions}</strong> question(s) worth <strong>{totalMarks}</strong> mark(s)
              {exam && exam.max_marks !== totalMarks && (
                <span className="text-amber-600"> — the examination declares {exam.max_marks} marks; adjust counts/marks to match.</span>
              )}
              {totalQuestions > GENERATION_BATCH && (
                <span className="text-stone-500"> Generated in safe batches of {GENERATION_BATCH} — larger papers take a few minutes.</span>
              )}
            </p>
            {genError && <p className="text-xs text-red-600">{genError}</p>}
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}><ArrowLeft size={14} /> Back</Button>
              <div className="text-right">
                <Button onClick={() => runBatches(buildQueue(rows), true)} loading={generating} disabled={aiStatus !== null && !aiStatus.configured}>
                  <Sparkles size={15} /> {generating ? "The AI is writing questions…" : "Generate Questions"}
                </Button>
                {aiStatus !== null && !aiStatus.configured && (
                  <p className="mt-1 max-w-[240px] text-[11px] text-amber-600">Configure the AI provider in Settings first.</p>
                )}
              </div>
            </div>
            {generating && progress && (
              <div className="space-y-1">
                <p className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-700">
                  <Spinner className="h-4 w-4" /> Batch {Math.min(progress.done + 1, progress.total)} of {progress.total} — the AI writes {GENERATION_BATCH} questions per batch; every mathematical answer is re-checked with SymPy.
                </p>
                <div className="h-1.5 overflow-hidden rounded-full bg-stone-200">
                  <div className="h-full bg-brand-600 transition-all" style={{ width: `${(progress.done / progress.total) * 100}%` }} />
                </div>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* ---------------------------------------------------------- step 4 */}
      {step === 4 && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Step 4 · Review the drafts ({drafts.length})</CardTitle>
              <div className="flex items-center gap-2 text-[11px]">
                <Badge tone="green"><ShieldCheck size={11} className="mr-1" />{verifiedCount} math-verified</Badge>
                {reviewCount > 0 && <Badge tone="amber"><AlertTriangle size={11} className="mr-1" />{reviewCount} need review</Badge>}
                <Badge tone="neutral">{providerInfo}</Badge>
              </div>
            </CardHeader>
            <CardBody className="space-y-2">
              {drafts.length === 0 && (
                <div className="py-6 text-center text-sm text-stone-500">
                  No drafts yet. Go back and press <strong>Generate Questions</strong>.
                </div>
              )}
              {drafts.map((d, idx) => (
                <div key={idx} className="rounded-lg border border-stone-200 p-3">
                  <div className="flex flex-wrap items-center gap-1.5 pb-1.5">
                    <Badge tone="brand">{QUESTION_TYPE_LABELS[d.qtype] ?? d.qtype}</Badge>
                    <Badge tone="neutral">{DIFFICULTY_LABELS[d.difficulty] ?? d.difficulty}</Badge>
                    <Badge tone="blue">{d.marks} mark{d.marks !== 1 && "s"}</Badge>
                    <VerificationBadge state={d.verification} note={d.verification_note} />
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-ink">{d.text}</p>
                  {d.options.length > 0 && (
                    <ul className="mt-1 grid list-none gap-0.5 sm:grid-cols-2">
                      {d.options.map((o, i) => (
                        <li key={i} className={`text-xs ${d.correct_answer.includes(o) ? "font-medium text-green-700" : "text-stone-500"}`}>{o}</li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-1.5 text-xs text-stone-500">
                    <strong>Answer:</strong> {d.correct_answer || "—"}
                  </p>
                  {d.explanation && <p className="mt-0.5 line-clamp-2 text-[11px] text-stone-400">{d.explanation}</p>}
                  <div className="mt-2 flex gap-1.5">
                    <Button size="sm" variant="outline" onClick={() => setEditingDraft(idx)}><Pencil size={12} /> Edit</Button>
                    <Button size="sm" variant="ghost"
                      onClick={() => regenerateOne(idx)}
                      title="Replace this draft with a fresh question of the same type, difficulty and marks">
                      <Wand2 size={12} /> Regenerate similar
                    </Button>
                    <Button size="sm" variant="ghost" className="text-red-500 hover:bg-red-50"
                      onClick={() => setDrafts(drafts.filter((_, i) => i !== idx))}>
                      <Trash2 size={12} /> Remove
                    </Button>
                  </div>
                </div>
              ))}
            </CardBody>
          </Card>
          {genError && <p className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700"><AlertTriangle size={13} /> {genError}</p>}
          {skipInfo && !genError && (
            <p className="flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
              <AlertTriangle size={13} /> {skipInfo} Use "Regenerate similar" on the nearby drafts to replace them.
            </p>
          )}
          <div className="flex flex-wrap justify-between gap-2">
            <Button variant="outline" onClick={() => setStep(3)}><ArrowLeft size={14} /> Back to Question Mix</Button>
            {pendingChunks && (
              <Button
                onClick={() => {
                  const chunks = pendingChunks;
                  setGenError("");
                  runBatches(chunks, false);
                }}
                loading={generating}
              >
                <Sparkles size={15} /> Generate remaining {pendingChunks.reduce((s, c) => s + c.count, 0)} question(s)
              </Button>
            )}
            <Button variant="success" disabled={drafts.length === 0} onClick={saveAll} loading={saving}>
              <CheckCircle2 size={15} /> Save {drafts.length} Question(s) & Build Paper
            </Button>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------- step 5 */}
      {step === 5 && (
        <Card className="max-w-xl">
          <CardHeader><CardTitle>Saved</CardTitle></CardHeader>
          <CardBody className="space-y-3 text-sm">
            <p className="flex items-center gap-2 font-medium text-green-700"><CheckCircle2 size={16} /> {saveResult?.saved ?? 0} question(s) saved to the Question Bank.</p>
            {(saveResult?.duplicates_skipped ?? 0) > 0 && (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {saveResult?.duplicates_skipped} duplicate(s) were skipped automatically — the bank never keeps the same question twice.
              </p>
            )}
            <div className="flex gap-2 pt-1">
              <Button onClick={() => exam && navigate(`/exams/${exam.id}`)}>
                <FileText size={15} /> Open the Question Paper
              </Button>
              <Button variant="outline" onClick={() => { setStep(1); setDrafts([]); setSaveResult(null); }}>
                Generate Another Set
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* draft editor */}
      {editingDraft !== null && drafts[editingDraft] && (
        <DraftEditorDialog
          open
          draft={drafts[editingDraft]}
          onClose={() => setEditingDraft(null)}
          onSave={(updated) => {
            setDrafts(drafts.map((d, i) => (i === editingDraft ? updated : d)));
            setEditingDraft(null);
          }}
        />
      )}
    </div>
  );
}

export function VerificationBadge({ state, note }: { state: string; note?: string }) {
  const tone = state === "verified" ? "green" : state === "needs_review" ? "amber" : "neutral";
  const title = note ? `${VERIFICATION_LABELS[state] ?? state}: ${note}` : VERIFICATION_LABELS[state] ?? state;
  return (
    <span title={title}>
      <Badge tone={tone as "green" | "amber" | "neutral"}>{VERIFICATION_LABELS[state] ?? state}</Badge>
    </span>
  );
}
