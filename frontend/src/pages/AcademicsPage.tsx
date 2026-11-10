import { useCallback, useEffect, useState } from "react";
import { Plus, School, Trash2, Pencil } from "lucide-react";
import { api, ApiError } from "../api/client";
import type { Klass } from "../api/types";
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, EmptyState, ErrorState, Input, Label, PageHeader, Spinner } from "../components/ui";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/dialog";

export default function AcademicsPage() {
  const [classes, setClasses] = useState<Klass[]>([]);
  const [selected, setSelected] = useState<Klass | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [classDialog, setClassDialog] = useState<{ open: boolean; editing: Klass | null }>({ open: false, editing: null });
  const [subjectDialog, setSubjectDialog] = useState<{ open: boolean; editingId: number | null; name: string; code: string; maxMarks: string }>({ open: false, editingId: null, name: "", code: "", maxMarks: "100" });
  const [sectionName, setSectionName] = useState("");
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<Klass[]>("/api/academics/classes");
      setClasses(data);
      if (selected) setSelected(data.find((c) => c.id === selected.id) ?? data[0] ?? null);
      else setSelected(data[0] ?? null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load classes.");
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveClass(name: string, level: string) {
    setBusy(true);
    setDialogError("");
    try {
      const payload = { name: name.trim(), level: level ? Number(level) : null };
      if (classDialog.editing) await api.put(`/api/academics/classes/${classDialog.editing.id}`, payload);
      else await api.post("/api/academics/classes", payload);
      setClassDialog({ open: false, editing: null });
      load();
    } catch (e) {
      setDialogError(e instanceof ApiError ? e.message : "Could not save the class.");
    } finally {
      setBusy(false);
    }
  }

  async function addSection() {
    if (!selected || !sectionName.trim()) return;
    setBusy(true);
    setDialogError("");
    try {
      await api.post(`/api/academics/classes/${selected.id}/sections`, { name: sectionName.trim() });
      setSectionName("");
      load();
    } catch (e) {
      setDialogError(e instanceof ApiError ? e.message : "Could not add the section.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSection(id: number, name: string) {
    if (!confirm(`Remove Section ${name}? This is only possible when no student is assigned to it.`)) return;
    try {
      await api.delete(`/api/academics/classes/${selected!.id}/sections/${id}`);
      load();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Could not remove the section.");
    }
  }

  async function saveSubject() {
    setBusy(true);
    setDialogError("");
    try {
      const payload = { name: subjectDialog.name.trim(), code: subjectDialog.code.trim(), max_marks: Number(subjectDialog.maxMarks) || 100 };
      if (subjectDialog.editingId) await api.put(`/api/academics/subjects/${subjectDialog.editingId}`, payload);
      else await api.post(`/api/academics/classes/${selected!.id}/subjects`, payload);
      setSubjectDialog({ open: false, editingId: null, name: "", code: "", maxMarks: "100" });
      load();
    } catch (e) {
      setDialogError(e instanceof ApiError ? e.message : "Could not save the subject.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSubject(id: number, name: string) {
    if (!confirm(`Remove subject "${name}" from ${selected?.name}?`)) return;
    try {
      await api.delete(`/api/academics/subjects/${id}`);
      load();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Could not remove the subject.");
    }
  }

  async function deleteClass() {
    if (!selected) return;
    if (!confirm(`Delete ${selected.name}? All its sections and subjects will be removed. This is only possible when the class has no students.`)) return;
    try {
      await api.delete(`/api/academics/classes/${selected.id}`);
      setSelected(null);
      load();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Could not delete the class.");
    }
  }

  if (loading && classes.length === 0)
    return <div className="flex h-64 items-center justify-center"><Spinner /></div>;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="Class & Subject Management"
        description="Set up classes, sections and the subjects taught in each class."
        actions={
          <Button onClick={() => setClassDialog({ open: true, editing: null })}>
            <Plus size={15} /> Add Class
          </Button>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        {/* class list */}
        <Card className="self-start">
          <CardHeader><CardTitle>Classes ({classes.length})</CardTitle></CardHeader>
          <CardBody className="max-h-[60vh] space-y-1 overflow-y-auto p-2">
            {classes.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c)}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm ${
                  selected?.id === c.id ? "bg-brand-600 text-cream" : "text-ink hover:bg-cream"
                }`}
              >
                <span>{c.name}</span>
                <span className={`text-[11px] ${selected?.id === c.id ? "text-brand-200" : "text-stone-400"}`}>
                  {c.student_count} student{c.student_count === 1 ? "" : "s"}
                </span>
              </button>
            ))}
            {classes.length === 0 && <EmptyState icon={<School size={28} />} title="No classes yet" description="Add the first class to begin." />}
          </CardBody>
        </Card>

        {/* class detail */}
        {selected ? (
          <div className="space-y-5">
            <Card>
              <CardHeader>
                <CardTitle>{selected.name} — Sections</CardTitle>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setClassDialog({ open: true, editing: selected })}>
                    <Pencil size={13} /> Rename
                  </Button>
                  <Button variant="ghost" size="sm" className="text-red-600 hover:bg-red-50" onClick={deleteClass}>
                    <Trash2 size={13} /> Delete
                  </Button>
                </div>
              </CardHeader>
              <CardBody>
                <div className="flex flex-wrap items-center gap-2">
                  {selected.sections.map((s) => (
                    <span key={s.id} className="flex items-center gap-1.5 rounded-full bg-cream px-3 py-1 text-sm text-ink">
                      Section {s.name}
                      <button className="text-stone-400 hover:text-red-600" title={`Remove section ${s.name}`} onClick={() => deleteSection(s.id, s.name)}>
                        <Trash2 size={12} />
                      </button>
                    </span>
                  ))}
                  <span className="flex items-center gap-1.5">
                    <Input className="h-8 w-20" placeholder="e.g. D" value={sectionName} onChange={(e) => setSectionName(e.target.value)} maxLength={16} />
                    <Button size="sm" variant="secondary" onClick={addSection} loading={busy}>
                      <Plus size={13} /> Add Section
                    </Button>
                  </span>
                </div>
                {dialogError && <p className="mt-2 text-xs text-red-600">{dialogError}</p>}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{selected.name} — Subjects & Maximum Marks</CardTitle>
                <Button size="sm" variant="secondary" onClick={() => setSubjectDialog({ open: true, editingId: null, name: "", code: "", maxMarks: "100" })}>
                  <Plus size={13} /> Add Subject
                </Button>
              </CardHeader>
              {selected.subjects.length === 0 ? (
                <EmptyState title="No subjects yet" description={`Add the subjects taught in ${selected.name}, each with its maximum marks.`} />
              ) : (
                <CardBody className="grid gap-2 sm:grid-cols-2">
                  {selected.subjects.map((s) => (
                    <div key={s.id} className="flex items-center justify-between rounded-lg border border-stone-200 px-3 py-2">
                      <div>
                        <p className="text-sm font-medium text-ink">{s.name}</p>
                        <p className="text-[11px] text-stone-400">
                          {s.code ? `${s.code} · ` : ""}Max {s.max_marks} marks
                        </p>
                      </div>
                      <div className="flex gap-1">
                        <button
                          className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink"
                          title="Edit subject"
                          onClick={() => setSubjectDialog({ open: true, editingId: s.id, name: s.name, code: s.code, maxMarks: String(s.max_marks) })}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="rounded-md p-1.5 text-stone-400 hover:bg-red-50 hover:text-red-600"
                          title="Delete subject"
                          onClick={() => deleteSubject(s.id, s.name)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </CardBody>
              )}
            </Card>
          </div>
        ) : (
          <Card>
            <EmptyState icon={<School size={32} />} title="Select a class" description="Choose a class on the left, or add a new one." />
          </Card>
        )}
      </div>

      {/* class dialog */}
      <ClassDialog
        state={classDialog}
        onClose={() => setClassDialog({ open: false, editing: null })}
        onSave={saveClass}
        busy={busy}
        error={dialogError}
      />

      {/* subject dialog */}
      <Dialog
        open={subjectDialog.open}
        onOpenChange={(o) => setSubjectDialog((s) => ({ ...s, open: o }))}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{subjectDialog.editingId ? "Edit Subject" : `Add Subject to ${selected?.name ?? ""}`}</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div>
              <Label>Subject Name *</Label>
              <Input value={subjectDialog.name} onChange={(e) => setSubjectDialog((s) => ({ ...s, name: e.target.value }))} maxLength={120} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Subject Code (optional)</Label>
                <Input value={subjectDialog.code} onChange={(e) => setSubjectDialog((s) => ({ ...s, code: e.target.value }))} maxLength={24} />
              </div>
              <div>
                <Label>Maximum Marks</Label>
                <Input type="number" min={1} max={1000} value={subjectDialog.maxMarks} onChange={(e) => setSubjectDialog((s) => ({ ...s, maxMarks: e.target.value }))} />
              </div>
            </div>
            {dialogError && <p className="text-xs text-red-600">{dialogError}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSubjectDialog((s) => ({ ...s, open: false }))}>Cancel</Button>
            <Button onClick={saveSubject} loading={busy} disabled={!subjectDialog.name.trim()}>
              {subjectDialog.editingId ? "Save Changes" : "Add Subject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ClassDialog({
  state, onClose, onSave, busy, error,
}: {
  state: { open: boolean; editing: Klass | null };
  onClose: () => void;
  onSave: (name: string, level: string) => void;
  busy: boolean;
  error: string;
}) {
  const [name, setName] = useState("");
  const [level, setLevel] = useState("");

  useEffect(() => {
    if (state.open) {
      setName(state.editing?.name ?? "");
      setLevel(state.editing?.level?.toString() ?? "");
    }
  }, [state.open, state.editing]);

  return (
    <Dialog open={state.open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{state.editing ? "Rename Class" : "Add Class"}</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-3">
          <div>
            <Label>Class Name *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Class 5" maxLength={64} autoFocus />
          </div>
          <div>
            <Label>Level Number (1–12, used for ordering)</Label>
            <Input type="number" min={0} max={14} value={level} onChange={(e) => setLevel(e.target.value)} placeholder="e.g. 5" />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onSave(name, level)} loading={busy} disabled={!name.trim()}>
            {state.editing ? "Save Changes" : "Add Class"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
