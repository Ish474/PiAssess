import type { Student } from "../../api/types";
import { Badge, Button } from "../../components/ui";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/dialog";
import { fmtDate } from "../../lib/utils";
import { FieldRow } from "./FieldRow";

export function StudentProfileDialog({
  open, onOpenChange, student, onEdit,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  student: Student | null;
  onEdit: (s: Student) => void;
}) {
  if (!student) return null;

  const statusTone = student.status === "active" ? "green" : "amber";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between gap-2">
            <span>{student.full_name}</span>
            <Badge tone={statusTone as "green" | "amber"}>{student.status}</Badge>
          </DialogTitle>
          <DialogDescription>Student profile and registration details.</DialogDescription>
        </DialogHeader>
        <DialogBody className="grid grid-cols-2 gap-x-4 gap-y-1">
          <FieldRow label="Student ID" value={student.student_code} strong />
          <FieldRow label="Admission No." value={student.admission_no || "—"} />
          <FieldRow label="Class" value={student.class_name || "—"} />
          <FieldRow label="Section" value={student.section_name || "—"} />
          <FieldRow label="Roll Number" value={student.roll_no?.toString() ?? "—"} />
          <FieldRow label="Date of Birth" value={fmtDate(student.dob)} />
          <FieldRow label="Gender" value={student.gender ? student.gender.charAt(0).toUpperCase() + student.gender.slice(1) : "—"} />
          <FieldRow label="Admission Date" value={fmtDate(student.admission_date)} />
          <FieldRow label="Father's Name" value={student.father_name || "—"} />
          <FieldRow label="Mother's Name" value={student.mother_name || "—"} />
          <FieldRow label="Contact" value={student.phone || "—"} />
          <FieldRow label="Email" value={student.email || "—"} />
          <div className="col-span-2">
            <FieldRow label="Address" value={student.address || "—"} />
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
          <Button
            onClick={() => {
              onOpenChange(false);
              onEdit(student);
            }}
          >
            Edit Student
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
