import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { Klass, Student } from "../../api/types";
import { Button, FieldError, Input, Label, Select } from "../../components/ui";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/dialog";
import { fmtDate } from "../../lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  classes: Klass[];
  student: Student | null; // null = create
  onSaved: () => void;
}

const empty = {
  full_name: "",
  admission_no: "",
  father_name: "",
  mother_name: "",
  class_id: "",
  section_id: "",
  roll_no: "",
  dob: "",
  gender: "",
  phone: "",
  email: "",
  address: "",
  admission_date: "",
  status: "active",
};

export function StudentFormDialog({ open, onOpenChange, classes, student, onSaved }: Props) {
  const [form, setForm] = useState<Record<string, string>>(empty);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError("");
    if (student) {
      setForm({
        full_name: student.full_name,
        admission_no: student.admission_no,
        father_name: student.father_name,
        mother_name: student.mother_name,
        class_id: String(student.class_id),
        section_id: student.section_id ? String(student.section_id) : "",
        roll_no: student.roll_no?.toString() ?? "",
        dob: student.dob ?? "",
        gender: student.gender,
        phone: student.phone,
        email: student.email,
        address: student.address,
        admission_date: student.admission_date ?? "",
        status: student.status,
      });
    } else {
      setForm(empty);
    }
  }, [open, student]);

  const klass = classes.find((c) => c.id === Number(form.class_id));
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const payload = {
        full_name: form.full_name.trim(),
        admission_no: form.admission_no.trim(),
        father_name: form.father_name.trim(),
        mother_name: form.mother_name.trim(),
        class_id: Number(form.class_id),
        section_id: form.section_id ? Number(form.section_id) : null,
        roll_no: form.roll_no ? Number(form.roll_no) : null,
        dob: form.dob || null,
        gender: form.gender,
        phone: form.phone.trim(),
        email: form.email.trim(),
        address: form.address.trim(),
        admission_date: form.admission_date || null,
        status: form.status,
      };
      if (student) await api.put(`/api/students/${student.id}`, payload);
      else await api.post("/api/students", payload);
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the student.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{student ? `Edit Student — ${student.full_name}` : "Add Student"}</DialogTitle>
          <DialogDescription>
            {student
              ? `Student ID ${student.student_code} stays the same.`
              : "The Student ID (e.g. APWS-2026-0001) is generated automatically."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit}>
          <DialogBody className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label>Student Name *</Label>
              <Input value={form.full_name} onChange={(e) => set("full_name", e.target.value)} required maxLength={160} />
            </div>
            <div>
              <Label>Class *</Label>
              <Select value={form.class_id} onChange={(e) => { set("class_id", e.target.value); set("section_id", ""); }} required>
                <option value="">Select class…</option>
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Section</Label>
              <Select value={form.section_id} onChange={(e) => set("section_id", e.target.value)} disabled={!klass}>
                <option value="">—</option>
                {klass?.sections.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Roll Number</Label>
              <Input type="number" min={1} max={999} value={form.roll_no} onChange={(e) => set("roll_no", e.target.value)} />
            </div>
            <div>
              <Label>Admission Number</Label>
              <Input value={form.admission_no} onChange={(e) => set("admission_no", e.target.value)} maxLength={32} />
            </div>
            <div>
              <Label>Father's Name</Label>
              <Input value={form.father_name} onChange={(e) => set("father_name", e.target.value)} maxLength={160} />
            </div>
            <div>
              <Label>Mother's Name</Label>
              <Input value={form.mother_name} onChange={(e) => set("mother_name", e.target.value)} maxLength={160} />
            </div>
            <div>
              <Label>Date of Birth</Label>
              <Input type="date" value={form.dob} onChange={(e) => set("dob", e.target.value)} />
            </div>
            <div>
              <Label>Gender</Label>
              <Select value={form.gender} onChange={(e) => set("gender", e.target.value)}>
                <option value="">—</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </Select>
            </div>
            <div>
              <Label>Contact Number</Label>
              <Input value={form.phone} onChange={(e) => set("phone", e.target.value)} maxLength={32} />
            </div>
            <div>
              <Label>Email</Label>
              <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} maxLength={160} />
            </div>
            <div>
              <Label>Admission Date</Label>
              <Input type="date" value={form.admission_date} onChange={(e) => set("admission_date", e.target.value)} />
            </div>
            <div>
              <Label>Status</Label>
              <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="passed">Passed out</option>
                <option value="transferred">Transferred</option>
              </Select>
            </div>
            <div className="sm:col-span-2">
              <Label>Address</Label>
              <Input value={form.address} onChange={(e) => set("address", e.target.value)} maxLength={500} />
            </div>
            {student && (
              <p className="text-[11px] text-stone-400 sm:col-span-2">
                Registered: {fmtDate(student.created_at)} · Last updated automatically on save.
              </p>
            )}
            <FieldError>{error}</FieldError>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" loading={busy}>{student ? "Save Changes" : "Add Student"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
