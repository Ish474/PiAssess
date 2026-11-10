import { useCallback, useEffect, useState } from "react";
import { BookOpen, Pencil, Plus, Search, ShieldCheck, Trash2 } from "lucide-react";
import { api, ApiError } from "../api/client";
import type { Klass, Question, QuestionList } from "../api/types";
import { DIFFICULTY_LABELS, QUESTION_TYPE_LABELS, VERIFICATION_LABELS } from "../api/types";
import {
  Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, Input, Label, PageHeader, Select, Spinner, Table, TD, TH, Textarea,
} from "../components/ui";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/dialog";
import { VerificationBadge } from "./aigenerator/GeneratorWizard";

const BLANK = {
  class_id: "", chapter: "", topic: "", qtype: "short", difficulty: "moderate", marks: "2",
  text: "", options: [] as string[], correct_answer: "", explanation: "", keywords: [] as string[],
  marking_notes: "", check_expression: "",
};

export default function QuestionBankPage() {
  const [list, setList] = useState<QuestionList | null>(null);
  const [classes, setClasses] = useState<Klass[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");
  const [verificationFilter, setVerificationFilter] = useState("");
  const [page, setPage] = useState(1);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Question | null>(null);
  const [form, setForm] = useState({ ...BLANK });
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<Question | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const pageSize = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (search.trim()) params.set("search", search.trim());
      if (classFilter) params.set("class_id", classFilter);
      if (typeFilter) params.set("qtype", typeFilter);
      if (difficultyFilter) params.set("difficulty", difficultyFilter);
      if (verificationFilter) params.set("verification", verificationFilter);
      setList(await api.get<QuestionList>(`/api/questions?${params.toString()}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the question bank.");
    } finally {
      setLoading(false);
    }
  }, [search, classFilter, typeFilter, difficultyFilter, verificationFilter, page]);

  useEffect(() => {
    api.get<Klass[]>("/api/academics/classes").then(setClasses).catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, classFilter, typeFilter, difficultyFilter, verificationFilter, page]);

  function openAdd() {
    setEditing(null);
    setForm({ ...BLANK, class_id: classFilter || String(classes[0]?.id ?? "") });
    setFormError("");
    setFormOpen(true);
  }

  function openEdit(q: Question) {
    setEditing(q);
    setForm({
      class_id: String(q.class_id), chapter: q.chapter, topic: q.topic, qtype: q.qtype,
      difficulty: q.difficulty, marks: String(q.marks), text: q.text, options: q.options,
      correct_answer: q.correct_answer, explanation: q.explanation, keywords: q.keywords,
      marking_notes: q.marking_notes, check_expression: q.check_expression,
    });
    setFormError("");
    setFormOpen(true);
  }

  async function save() {
    setBusy(true);
    setFormError("");
    try {
      const payload = {
        class_id: Number(form.class_id), chapter: form.chapter, topic: form.topic,
        qtype: form.qtype, difficulty: form.difficulty, marks: Number(form.marks),
        text: form.text, options: form.options, correct_answer: form.correct_answer,
        explanation: form.explanation, keywords: form.keywords,
        marking_notes: form.marking_notes, check_expression: form.check_expression,
      };
      if (editing) await api.put(`/api/questions/${editing.id}`, payload);
      else await api.post("/api/questions", payload);
      setFormOpen(false);
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Could not save the question.");
    } finally {
      setBusy(false);
    }
  }

  async function markVerified(q: Question) {
    try {
      await api.post(`/api/questions/${q.id}/verify`, { verification: "verified", note: "Confirmed correct by teacher review." });
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not update the question.");
    }
  }

  const totalPages = list ? Math.max(1, Math.ceil(list.total / pageSize)) : 1;
  const klass = classes.find((c) => String(c.id) === form.class_id);

  return (
    <div>
      <PageHeader
        title="Question Bank"
        description="Every question the school owns — AI-generated or written by teachers. The same question can never be saved twice."
        actions={<Button onClick={openAdd}><Plus size={15} /> Add Question</Button>}
      />

      <Card className="mb-4 flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-[220px] flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
          <Input className="pl-9" placeholder="Search question text, chapter, topic…" value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        </div>
        <Select className="w-36" value={classFilter} onChange={(e) => { setClassFilter(e.target.value); setPage(1); }}>
          <option value="">All classes</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select className="w-44" value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}>
          <option value="">All types</option>
          {Object.entries(QUESTION_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select className="w-36" value={difficultyFilter} onChange={(e) => { setDifficultyFilter(e.target.value); setPage(1); }}>
          <option value="">All difficulty</option>
          {Object.entries(DIFFICULTY_LABELS).filter(([k]) => k !== "mixed").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select className="w-40" value={verificationFilter} onChange={(e) => { setVerificationFilter(e.target.value); setPage(1); }}>
          <option value="">Any status</option>
          {Object.entries(VERIFICATION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </Card>

      <Card>
        {loading && !list ? (
          <div className="flex h-48 items-center justify-center"><Spinner /></div>
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !list || list.items.length === 0 ? (
          <EmptyState
            icon={<BookOpen size={36} />}
            title="No questions found"
            description="Generate questions with the AI Question Paper Generator or add one manually."
          />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <TH className="w-10">#</TH>
                  <TH>Question</TH>
                  <TH>Type</TH>
                  <TH>Difficulty</TH>
                  <TH>Marks</TH>
                  <TH>Status</TH>
                  <TH className="text-right">Actions</TH>
                </tr>
              </thead>
              <tbody>
                {list.items.map((q) => (
                  <tr key={q.id} className="hover:bg-cream/60">
                    <TD className="text-stone-400">{q.id}</TD>
                    <TD className="max-w-[380px]">
                      <p className="line-clamp-2 whitespace-pre-wrap text-sm">{q.text}</p>
                      {(q.chapter || q.topic) && (
                        <p className="mt-0.5 text-[11px] text-stone-400">{[q.chapter, q.topic].filter(Boolean).join(" · ")}</p>
                      )}
                    </TD>
                    <TD><Badge tone="brand">{QUESTION_TYPE_LABELS[q.qtype] ?? q.qtype}</Badge></TD>
                    <TD className="text-stone-500">{DIFFICULTY_LABELS[q.difficulty] ?? q.difficulty}</TD>
                    <TD>{q.marks}</TD>
                    <TD>
                      {q.verification === "unverified" ? (
                        <button title={q.verification_note || "Mark as verified after checking"} onClick={() => markVerified(q)} className="hover:opacity-80">
                          <VerificationBadge state={q.verification} note={q.verification_note} />
                        </button>
                      ) : (
                        <span title={q.verification_note}>
                          <VerificationBadge state={q.verification} note={q.verification_note} />
                        </span>
                      )}
                    </TD>
                    <TD className="text-right">
                      <div className="flex justify-end gap-1">
                        {q.verification !== "verified" && (
                          <button className="rounded-md p-1.5 text-stone-400 hover:bg-green-50 hover:text-green-600" title="Mark verified" onClick={() => markVerified(q)}>
                            <ShieldCheck size={15} />
                          </button>
                        )}
                        <button className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink" title="Edit" onClick={() => openEdit(q)}>
                          <Pencil size={15} />
                        </button>
                        <button className="rounded-md p-1.5 text-stone-400 hover:bg-red-50 hover:text-red-600" title="Delete" onClick={() => setDeleting(q)}>
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </TD>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="flex items-center justify-between px-4 py-3 text-xs text-stone-500">
              <span>{list.total} question(s) · page {list.page} of {totalPages}</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
              </div>
            </div>
          </>
        )}
      </Card>

      {/* add / edit dialog */}
      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? `Edit Question #${editing.id}` : "Add Question"}</DialogTitle>
            <DialogDescription>{editing ? "Edits re-run the SymPy check where applicable." : "The bank refuses exact duplicates automatically."}</DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div className="grid grid-cols-4 gap-2">
              <div className="col-span-2">
                <Label>Class *</Label>
                <Select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })}>
                  {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </div>
              <div>
                <Label>Type</Label>
                <Select value={form.qtype} onChange={(e) => setForm({ ...form, qtype: e.target.value })}>
                  {Object.entries(QUESTION_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
              </div>
              <div>
                <Label>Marks</Label>
                <Input type="number" min={1} max={100} value={form.marks} onChange={(e) => setForm({ ...form, marks: e.target.value })} />
              </div>
              <div>
                <Label>Difficulty</Label>
                <Select value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })}>
                  {Object.entries(DIFFICULTY_LABELS).filter(([k]) => k !== "mixed").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
              </div>
              <div>
                <Label>Chapter</Label>
                <Input value={form.chapter} onChange={(e) => setForm({ ...form, chapter: e.target.value })} maxLength={200} />
              </div>
              <div className="col-span-2">
                <Label>Topic</Label>
                <Input value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} maxLength={200} />
              </div>
            </div>
            <div>
              <Label>Question text *</Label>
              <Textarea className="min-h-[90px]" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} maxLength={4000} />
            </div>
            {(form.qtype === "mcq" || form.qtype === "assertion_reason") && (
              <div className="space-y-1.5">
                <Label>Options — press ✓ to mark the correct one</Label>
                {(form.options.length ? form.options : ["", "", "", ""]).map((o, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      value={o || ""} maxLength={500}
                      onChange={(e) => {
                        const options = [...(form.options.length ? form.options : ["", "", "", ""])];
                        options[i] = e.target.value;
                        setForm({ ...form, options: options.map((x) => x ?? "") });
                      }}
                    />
                    <button
                      type="button"
                      className={`h-8 w-8 shrink-0 rounded-full border text-xs font-bold ${
                        form.correct_answer.includes(o) && o ? "border-green-500 bg-green-50 text-green-700" : "border-stone-300 text-stone-400 hover:border-green-400"
                      }`}
                      onClick={() => setForm({ ...form, correct_answer: o })}
                    >
                      ✓
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div>
              <Label>Correct answer *</Label>
              <Input value={form.correct_answer} onChange={(e) => setForm({ ...form, correct_answer: e.target.value })} maxLength={4000} />
            </div>
            {form.qtype === "numerical" && (
              <div>
                <Label>SymPy check expression (arithmetic equal to the answer)</Label>
                <Input value={form.check_expression} onChange={(e) => setForm({ ...form, check_expression: e.target.value })} placeholder="e.g. 45*12" maxLength={500} />
              </div>
            )}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label>Explanation</Label>
                <Textarea className="min-h-[60px]" value={form.explanation} onChange={(e) => setForm({ ...form, explanation: e.target.value })} maxLength={4000} />
              </div>
              <div>
                <Label>Marking notes</Label>
                <Textarea className="min-h-[60px]" value={form.marking_notes} onChange={(e) => setForm({ ...form, marking_notes: e.target.value })} maxLength={2000} />
              </div>
            </div>
            {formError && <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{formError}</p>}
            {!formError && form.class_id && !klass && <p className="text-xs text-red-600">Please choose a class.</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>Cancel</Button>
            <Button onClick={save} loading={busy} disabled={!form.text.trim() || !form.class_id}>
              {editing ? "Save Changes" : "Add to Bank"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete question #${deleting?.id ?? ""}?`}
        description="This removes the question from the bank and from any question paper that uses it. This cannot be undone."
        confirmLabel="Delete Permanently"
        onConfirm={async () => {
          if (!deleting) return;
          setDeleteBusy(true);
          try {
            await api.delete(`/api/questions/${deleting.id}`);
            setDeleting(null);
            load();
          } catch (e) {
            alert(e instanceof Error ? e.message : "Could not delete the question.");
          } finally {
            setDeleteBusy(false);
          }
        }}
        loading={deleteBusy}
      />
    </div>
  );
}
