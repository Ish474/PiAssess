import { useMemo, useRef, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { ImportField, ImportPreview, ImportResult, Klass } from "../../api/types";
import { Badge, Button } from "../../components/ui";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/dialog";
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Upload } from "lucide-react";
import { cn } from "../../lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fields: ImportField[];
  onImported: () => void;
}

type Step = "upload" | "map" | "review" | "done";

export function ImportWizard({ open, onOpenChange, fields, onImported }: Props) {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  function reset() {
    setStep("upload");
    setFile(null);
    setPreview(null);
    setMapping({});
    setResult(null);
    setError("");
  }

  async function upload(f: File) {
    setError("");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await api.postForm<ImportPreview>("/api/students/import/preview", fd);
      setFile(f);
      setPreview(res);
      setMapping(res.mapping_hint);
      setStep("map");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The file could not be read.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!preview) return;
    setError("");
    setBusy(true);
    try {
      const res = await api.post<ImportResult>("/api/students/import/confirm", {
        rows: preview.rows.map((r) => r.data),
        mapping,
      });
      setResult(res);
      setStep("done");
      onImported();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The import could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  // Build the mapped row objects for the review step (mirrors server-side mapping)
  const reviewRows = useMemo(() => {
    if (!preview) return [];
    return preview.rows.map((r) => {
      const mapped: Record<string, string> = {};
      for (const [field, col] of Object.entries(mapping)) if (col) mapped[field] = r.data[col] ?? "";
      return { row_number: r.row_number, data: mapped };
    });
  }, [preview, mapping]);

  const requiredMissing = useMemo(
    () => fields.filter((f) => f.key === "full_name" || f.key === "class_name").filter((f) => !mapping[f.key]),
    [fields, mapping]
  );

  const steps: { id: Step; label: string }[] = [
    { id: "upload", label: "1 · Upload File" },
    { id: "map", label: "2 · Match Columns" },
    { id: "review", label: "3 · Check & Import" },
  ];
  const currentStepIndex = steps.findIndex((s) => s.id === step);

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) reset();
      }}
    >
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Import Students from Excel or CSV</DialogTitle>
          <DialogDescription>
            Every row is checked before saving — nothing is silently skipped. The first row of the file must contain column headings.
          </DialogDescription>
          <div className="mt-3 flex gap-2">
            {steps.map((s, i) => (
              <span
                key={s.id}
                className={cn(
                  "rounded-full px-3 py-1 text-[11px] font-medium",
                  step === s.id ? "bg-brand-600 text-cream" : currentStepIndex > i ? "bg-green-50 text-green-700" : "bg-stone-100 text-stone-500"
                )}
              >
                {s.label}
              </span>
            ))}
          </div>
        </DialogHeader>

        <DialogBody>
          {error && (
            <p className="mb-3 flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {error}
            </p>
          )}

          {step === "upload" && (
            <button
              onClick={() => fileInput.current?.click()}
              className="flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-stone-300 bg-cream px-6 py-10 text-center hover:border-brand-400"
            >
              <Upload className="h-8 w-8 text-stone-400" />
              <span className="text-sm font-medium text-ink">{busy ? "Checking the file…" : "Click to choose a file"}</span>
              <span className="text-xs text-stone-500">Excel (.xlsx) or CSV, up to 2000 rows. Column headings in the first row.</span>
              <FileSpreadsheet className="mt-2 h-5 w-5 text-stone-300" />
            </button>
          )}

          {step === "map" && preview && (
            <div className="space-y-3">
              <p className="text-xs text-stone-500">
                <strong>{file?.name}</strong> — {preview.rows.length} data row(s) found. Match each PiAssess field to a column from your file.
                Fields marked * are required.
              </p>
              <div className="grid max-h-64 grid-cols-1 gap-2 overflow-y-auto rounded-lg border border-stone-200 p-3 sm:grid-cols-2">
                {fields.map((f) => (
                  <div key={f.key} className="flex items-center justify-between gap-2 text-xs">
                    <span className="text-ink">
                      {f.label}
                      {f.key === "full_name" || f.key === "class_name" ? " *" : ""}
                    </span>
                    <select
                      className="h-7 w-40 rounded-md border border-stone-300 bg-white px-2 text-xs"
                      value={mapping[f.key] ?? ""}
                      onChange={(e) => setMapping((m) => ({ ...m, [f.key]: e.target.value }))}
                    >
                      <option value="">— not in file —</option>
                      {preview.columns.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              {requiredMissing.length > 0 && (
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  Please match: {requiredMissing.map((f) => f.label).join(", ")} — these fields are required for every student.
                </p>
              )}
            </div>
          )}

          {step === "review" && (
            <div>
              <div className="max-h-72 overflow-auto rounded-lg border border-stone-200">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-cream">
                    <tr>
                      <th className="px-2 py-1.5 text-left font-semibold text-stone-500">Row</th>
                      <th className="px-2 py-1.5 text-left font-semibold text-stone-500">Name</th>
                      <th className="px-2 py-1.5 text-left font-semibold text-stone-500">Class</th>
                      <th className="px-2 py-1.5 text-left font-semibold text-stone-500">Section</th>
                      <th className="px-2 py-1.5 text-left font-semibold text-stone-500">Roll</th>
                      <th className="px-2 py-1.5 text-left font-semibold text-stone-500">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reviewRows.map((r) => {
                      const problems = localValidate(r, fields);
                      return (
                        <tr key={r.row_number} className={problems.length ? "bg-red-50/60" : ""}>
                          <td className="border-t border-stone-100 px-2 py-1.5 text-stone-400">{r.row_number}</td>
                          <td className="border-t border-stone-100 px-2 py-1.5">{r.data.full_name || <span className="text-red-500">missing</span>}</td>
                          <td className="border-t border-stone-100 px-2 py-1.5">{r.data.class_name}</td>
                          <td className="border-t border-stone-100 px-2 py-1.5">{r.data.section_name}</td>
                          <td className="border-t border-stone-100 px-2 py-1.5">{r.data.roll_no}</td>
                          <td className="border-t border-stone-100 px-2 py-1.5">
                            {problems.length === 0 ? (
                              <Badge tone="green">Looks good</Badge>
                            ) : (
                              <Badge tone="red">{problems.join("; ")}</Badge>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px] text-stone-400">
                The school server checks every row again during the import (class names, duplicate admission numbers, dates).
                Rows with problems are reported and skipped — they are never saved partially.
              </p>
            </div>
          )}

          {step === "done" && result && (
            <div className="space-y-2 text-sm">
              <p className="flex items-center gap-2 font-medium text-green-700">
                <CheckCircle2 size={16} /> Import finished
              </p>
              <p className="text-ink">{result.imported} student(s) were added.</p>
              {result.skipped > 0 && (
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  {result.skipped} row(s) could not be imported because of problems such as missing names, unknown classes or duplicate
                  admission numbers. Nothing was lost — fix those rows in your file and import again; only the new students will be added.
                </p>
              )}
              {result.first_student_code && (
                <p className="text-xs text-stone-500">First ID assigned: <strong>{result.first_student_code}</strong></p>
              )}
            </div>
          )}
        </DialogBody>

        <DialogFooter>
          {step === "upload" && <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>}
          {step === "map" && (
            <>
              <Button variant="outline" onClick={reset}>Back</Button>
              <Button
                disabled={requiredMissing.length > 0}
                onClick={() => setStep("review")}
              >
                Check Rows
              </Button>
            </>
          )}
          {step === "review" && (
            <>
              <Button variant="outline" onClick={() => setStep("map")}>Back</Button>
              <Button onClick={confirm} loading={busy}>Import Now</Button>
            </>
          )}
          {step === "done" && (
            <Button onClick={() => { onOpenChange(false); reset(); }}>Done</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Light client-side pre-check; the server always re-validates authoritatively. */
function localValidate(row: { data: Record<string, string> }, _fields: ImportField[]): string[] {
  const problems: string[] = [];
  if (!row.data.full_name?.trim()) problems.push("name required");
  if (!row.data.class_name?.trim()) problems.push("class required");
  return problems;
}
