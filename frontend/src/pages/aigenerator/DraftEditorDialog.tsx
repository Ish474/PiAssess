import { FormEvent, useState } from "react";
import type { DraftQuestion } from "../../api/types";
import { QUESTION_TYPE_LABELS, DIFFICULTY_LABELS } from "../../api/types";
import { Button, Input, Label, Select, Textarea } from "../../components/ui";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/dialog";

/** Edit one AI-drafted question before saving. Any edit resets verification to
 *  "unverified" — the SymPy check re-runs when the draft is saved server-side. */
export function DraftEditorDialog({
  open, draft, onClose, onSave,
}: {
  open: boolean;
  draft: DraftQuestion;
  onClose: () => void;
  onSave: (updated: DraftQuestion) => void;
}) {
  const [form, setForm] = useState<DraftQuestion>({ ...draft });

  const set = (patch: Partial<DraftQuestion>) =>
    setForm((f) => ({
      ...f,
      ...patch,
      verification: "unverified",
      verification_note: "Edited — please review before publishing.",
    }));

  function setOption(idx: number, value: string) {
    set({ options: form.options.map((o, i) => (i === idx ? value : o)) });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    onSave(form);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Edit Draft Question</DialogTitle>
          <DialogDescription>
            Changing the text or answer resets the verification status — the SymPy check runs again when the draft is saved.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit}>
          <DialogBody className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label>Type</Label>
                <Select value={form.qtype} onChange={(e) => set({ qtype: e.target.value })}>
                  {Object.entries(QUESTION_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Difficulty</Label>
                <Select value={form.difficulty} onChange={(e) => set({ difficulty: e.target.value })}>
                  {Object.entries(DIFFICULTY_LABELS)
                    .filter(([k]) => k !== "mixed")
                    .map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                </Select>
              </div>
              <div>
                <Label>Marks</Label>
                <Input
                  type="number" min={1} max={100} value={form.marks}
                  onChange={(e) => set({ marks: Math.max(1, Number(e.target.value) || 1) })}
                />
              </div>
            </div>

            <div>
              <Label>Question text *</Label>
              <Textarea
                className="min-h-[90px]" value={form.text}
                onChange={(e) => set({ text: e.target.value })} required maxLength={4000}
              />
            </div>

            {form.options.length > 0 && (
              <div className="space-y-1.5">
                <Label>Options — press ✓ to mark the correct one</Label>
                {form.options.map((o, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input value={o} onChange={(e) => setOption(i, e.target.value)} maxLength={500} />
                    <button
                      type="button"
                      title="Mark this as the correct option"
                      className={`h-8 w-8 shrink-0 rounded-full border text-xs font-bold ${
                        form.correct_answer.includes(o) && o
                          ? "border-green-500 bg-green-50 text-green-700"
                          : "border-stone-300 text-stone-400 hover:border-green-400"
                      }`}
                      onClick={() => set({ correct_answer: o })}
                    >
                      ✓
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div>
              <Label>Correct answer *</Label>
              <Input value={form.correct_answer} onChange={(e) => set({ correct_answer: e.target.value })} maxLength={4000} />
            </div>

            {form.qtype === "numerical" && (
              <div>
                <Label>SymPy check expression (arithmetic that must equal the answer)</Label>
                <Input
                  value={form.check_expression}
                  onChange={(e) => set({ check_expression: e.target.value })}
                  placeholder="e.g. 45*12" maxLength={500}
                />
              </div>
            )}

            <div>
              <Label>Explanation</Label>
              <Textarea
                className="min-h-[70px]" value={form.explanation}
                onChange={(e) => set({ explanation: e.target.value })} maxLength={4000}
              />
            </div>

            <div>
              <Label>Marking notes</Label>
              <Input value={form.marking_notes} onChange={(e) => set({ marking_notes: e.target.value })} maxLength={2000} />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!form.text.trim()}>Save Draft</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
