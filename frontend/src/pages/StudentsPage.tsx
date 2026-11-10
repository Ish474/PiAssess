import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Upload, Download, Pencil, Trash2, Eye, UsersRound } from "lucide-react";
import { api, ApiError, downloadFile } from "../api/client";
import type { ImportField, Klass, Student, StudentList } from "../api/types";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, Select, Spinner, Table, TD, TH, ConfirmDialog } from "../components/ui";
import { STATUS_LABELS } from "../lib/utils";
import { StudentFormDialog } from "./students/StudentFormDialog";
import { StudentProfileDialog } from "./students/StudentProfileDialog";
import { ImportWizard } from "./students/ImportWizard";

export default function StudentsPage() {
  const [classes, setClasses] = useState<Klass[]>([]);
  const [fields, setFields] = useState<ImportField[]>([]);
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [sectionFilter, setSectionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [list, setList] = useState<StudentList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Student | null>(null);
  const [profile, setProfile] = useState<Student | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [deleting, setDeleting] = useState<Student | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const pageSize = 20;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (search.trim()) params.set("search", search.trim());
      if (classFilter) params.set("class_id", classFilter);
      if (sectionFilter) params.set("section_id", sectionFilter);
      if (statusFilter) params.set("status", statusFilter);
      setList(await api.get<StudentList>(`/api/students?${params.toString()}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load students.");
    } finally {
      setLoading(false);
    }
  }, [search, classFilter, sectionFilter, statusFilter, page]);

  useEffect(() => {
    api.get<Klass[]>("/api/academics/classes").then(setClasses).catch(() => {});
    api.get<{ fields: ImportField[] }>("/api/students/fields").then((r) => setFields(r.fields)).catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, classFilter, sectionFilter, statusFilter, page]);

  const selectedClass = classes.find((c) => String(c.id) === classFilter);
  const totalPages = list ? Math.max(1, Math.ceil(list.total / pageSize)) : 1;

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await api.delete(`/api/students/${deleting.id}`);
      setDeleting(null);
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not delete the student.");
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Student Database"
        description="Register students, import from Excel/CSV and keep records up to date."
        actions={
          <>
            <Button variant="outline" onClick={() => downloadFile("/api/students/export?format=csv", "piassess_students.csv")}>
              <Download size={15} /> Export CSV
            </Button>
            <Button variant="outline" onClick={() => downloadFile("/api/students/export?format=xlsx", "piassess_students.xlsx")}>
              <Download size={15} /> Export Excel
            </Button>
            <Button variant="secondary" onClick={() => setImportOpen(true)}>
              <Upload size={15} /> Import
            </Button>
            <Button
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus size={15} /> Add Student
            </Button>
          </>
        }
      />

      {/* filters */}
      <Card className="mb-4 flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-[220px] flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
          <Input className="pl-9" placeholder="Search by name, student ID or admission number…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        </div>
        <Select className="w-40" value={classFilter} onChange={(e) => { setClassFilter(e.target.value); setSectionFilter(""); setPage(1); }}>
          <option value="">All classes</option>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </Select>
        <Select className="w-32" value={sectionFilter} onChange={(e) => { setSectionFilter(e.target.value); setPage(1); }} disabled={!selectedClass}>
          <option value="">All sections</option>
          {selectedClass?.sections.map((s) => (
            <option key={s.id} value={s.id}>Section {s.name}</option>
          ))}
        </Select>
        <Select className="w-36" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="passed">Passed out</option>
          <option value="transferred">Transferred</option>
        </Select>
      </Card>

      <Card>
        {loading && !list ? (
          <div className="flex h-48 items-center justify-center"><Spinner /></div>
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !list || list.items.length === 0 ? (
          <EmptyState
            icon={<UsersRound size={36} />}
            title={search || classFilter ? "No students match these filters" : "No students yet"}
            description={search || classFilter ? "Try a different search or clear the filters." : "Add students one by one, or import a whole class from an Excel or CSV file."}
            action={
              !search && !classFilter ? (
                <Button size="sm" className="mt-2" onClick={() => setImportOpen(true)}>
                  <Upload size={14} /> Import from File
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <TH>Student ID</TH>
                  <TH>Name</TH>
                  <TH>Class</TH>
                  <TH>Roll</TH>
                  <TH>Father's Name</TH>
                  <TH>Contact</TH>
                  <TH>Status</TH>
                  <TH className="text-right">Actions</TH>
                </tr>
              </thead>
              <tbody>
                {list.items.map((s) => (
                  <tr key={s.id} className="hover:bg-cream/60">
                    <TD className="font-mono text-xs text-brand-700">{s.student_code}</TD>
                    <TD className="font-medium">
                      <button className="hover:underline" onClick={() => setProfile(s)}>{s.full_name}</button>
                    </TD>
                    <TD>{s.class_name}{s.section_name ? ` · ${s.section_name}` : ""}</TD>
                    <TD>{s.roll_no ?? "—"}</TD>
                    <TD className="text-stone-500">{s.father_name || "—"}</TD>
                    <TD className="text-stone-500">{s.phone || "—"}</TD>
                    <TD>
                      <Badge tone={s.status === "active" ? "green" : s.status === "inactive" ? "amber" : "neutral"}>
                        {STATUS_LABELS[s.status] ?? s.status}
                      </Badge>
                    </TD>
                    <TD className="text-right">
                      <div className="flex justify-end gap-1">
                        <button className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink" title="View profile" onClick={() => setProfile(s)}>
                          <Eye size={15} />
                        </button>
                        <button className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink" title="Edit" onClick={() => { setEditing(s); setFormOpen(true); }}>
                          <Pencil size={15} />
                        </button>
                        <button className="rounded-md p-1.5 text-stone-400 hover:bg-red-50 hover:text-red-600" title="Delete" onClick={() => setDeleting(s)}>
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </TD>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="flex items-center justify-between px-4 py-3 text-xs text-stone-500">
              <span>{list.total} student(s) · page {list.page} of {totalPages}</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
              </div>
            </div>
          </>
        )}
      </Card>

      <StudentFormDialog open={formOpen} onOpenChange={setFormOpen} classes={classes} student={editing} onSaved={load} />
      <StudentProfileDialog
        open={profile !== null}
        onOpenChange={(o) => !o && setProfile(null)}
        student={profile}
        onEdit={(s) => {
          setEditing(s);
          setFormOpen(true);
        }}
      />
      <ImportWizard open={importOpen} onOpenChange={setImportOpen} fields={fields} onImported={load} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete ${deleting?.full_name ?? "student"}?`}
        description={`This permanently removes ${deleting?.full_name} (${deleting?.student_code}) from the student database. This action cannot be undone.`}
        confirmLabel="Delete Permanently"
        onConfirm={confirmDelete}
        loading={deleteBusy}
      />
    </div>
  );
}
