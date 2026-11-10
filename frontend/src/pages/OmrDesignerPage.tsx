import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api, downloadFile } from "../api/client";
import type { ExamList, Paper } from "../api/types";
import { Button, Card, ErrorState, Label, PageHeader, Select, Spinner } from "../components/ui";

interface PaperInfo {
  hasPaper: boolean;
  mcqCount: number;
  totalQuestions: number;
  totalMarks: number;
  title: string;
}

export default function OmrDesignerPage() {
  const [exams, setExams] = useState<ExamList | null>(null);
  const [examId, setExamId] = useState("");
  const [setLetter, setSetLetter] = useState("A");
  const [keyCopy, setKeyCopy] = useState(false);
  const [info, setInfo] = useState<PaperInfo | null>(null);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [infoError, setInfoError] = useState("");

  useEffect(() => {
    api.get<ExamList>("/api/exams").then(setExams).catch(() => setLoadError("Could not load the examination list."));
  }, []);

  useEffect(() => {
    setInfo(null);
    setInfoError("");
    if (!examId) return;
    setLoadingInfo(true);
    api.get<Paper>(`/api/papers/${examId}`)
      .then((p) => {
        const mcqCount = p.items.filter((it) => (it.question.options?.length ?? 0) >= 2).length;
        setInfo({
          hasPaper: true,
          mcqCount,
          totalQuestions: p.items.length,
          totalMarks: p.total_marks,
          title: p.title || p.exam_name,
        });
        if (mcqCount === 0) setInfoError("This paper has no MCQ questions, so there is nothing to bubble on an OMR sheet.");
      })
      .catch((e) => {
        if (e instanceof Error && e.message.includes("No question paper")) {
          setInfo({ hasPaper: false, mcqCount: 0, totalQuestions: 0, totalMarks: 0, title: "" });
          setInfoError("No question paper exists for this examination yet. Assemble one in the paper editor first.");
        } else {
          setInfoError("Could not load this examination's paper.");
        }
      })
      .finally(() => setLoadingInfo(false));
  }, [examId]);

  function download() {
    if (!info?.hasPaper) return;
    const exam = exams?.items.find((e) => String(e.id) === examId);
    const base = (exam?.name || "omr-sheet").replace(/[^A-Za-z0-9 -]+/g, "").trim() || "omr-sheet";
    const kind = keyCopy ? "OMR-Answer-Key" : "OMR-Sheet";
    downloadFile(`/api/papers/${examId}/omr?set=${setLetter}&key=${keyCopy ? 1 : 0}`,
                 `${base}-${kind}-Set-${setLetter}.pdf`);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader
        title="OMR Sheet Designer"
        description="Download a scanner-ready OMR bubble sheet for an examination's MCQ questions."
      />

      <Card className="space-y-4 p-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Examination</Label>
            {loadError ? (
              <ErrorState message={loadError} />
            ) : !exams ? (
              <div className="flex h-12 items-center justify-center"><Spinner /></div>
            ) : exams.items.length === 0 ? (
              <p className="text-sm text-stone-500">No examinations yet — create one in the Examination Manager first.</p>
            ) : (
              <Select value={examId} onChange={(e) => setExamId(e.target.value)}>
                <option value="">Select an examination…</option>
                {exams.items.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} — {e.class_name}
                    {e.subject_name ? ` · ${e.subject_name}` : ""}
                  </option>
                ))}
              </Select>
            )}
          </div>
          <div>
            <Label>Paper set (printed on the corner tag)</Label>
            <Select value={setLetter} onChange={(e) => setSetLetter(e.target.value)} disabled={!info?.hasPaper}>
              {["A", "B", "C", "D"].map((s) => (
                <option key={s} value={s}>SET {s}</option>
              ))}
            </Select>
          </div>
        </div>

        <div>
          <Label>Sheet type</Label>
          <div className="grid grid-cols-2 gap-3">
            {[
              { value: false, title: "Blank sheet (for students)", desc: "Empty bubbles — print and hand out" },
              { value: true, title: "Answer-key copy (for checking)", desc: "Correct bubbles darkened in black, with a KEY COPY watermark" },
            ].map((opt) => (
              <button
                key={String(opt.value)}
                type="button"
                onClick={() => setKeyCopy(opt.value)}
                disabled={!info?.hasPaper}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  keyCopy === opt.value
                    ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600"
                    : "border-stone-200 bg-white hover:border-stone-300"
                }`}
              >
                <span className="block text-sm font-semibold text-ink">{opt.title}</span>
                <span className="mt-0.5 block text-xs text-stone-500">{opt.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {loadingInfo && <div className="flex h-12 items-center justify-center"><Spinner /></div>}

        {info?.hasPaper && info.totalQuestions > 0 && !infoError && (
          <div className="rounded-lg border border-brand-100 bg-cream p-4 text-sm text-ink">
            <p className="font-semibold text-brand-700">{info.title}</p>
            <p className="mt-1">
              {info.totalQuestions} question(s) · {info.totalMarks} marks · <b>{info.mcqCount} MCQ(s)</b> will appear as bubble rows.
            </p>
          </div>
        )}

        {infoError && (
          <ErrorState message={infoError} />
        )}

        <div className="rounded-lg border border-stone-200 p-4 text-sm text-stone-600">
          <p className="font-semibold text-ink">Every sheet includes:</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            <li>CLASS / SET corner tags and a dark maroon banner with your logo</li>
            <li>Candidate block: name, roll number, section, date and signatures</li>
            <li>Bordered instructions box, four parallel section boxes of 20 rows each</li>
            <li>Lettered bubbles for MCQs, digit bubbles (0–9) for integer questions</li>
            <li>QR code + black registration squares (for the future scanner)</li>
            <li>Numbered exactly like the printed paper — question 7 is row 7</li>
          </ul>
        </div>

        <div>
          <Button disabled={!info?.hasPaper || info.mcqCount === 0} onClick={download}>
            <Download size={15} /> {keyCopy ? "Download Answer-Key Copy (PDF)" : "Download OMR Sheet (PDF)"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
