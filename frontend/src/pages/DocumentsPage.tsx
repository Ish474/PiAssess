import { useCallback, useEffect, useState } from "react";
import { Download, FolderOpen, Archive, ArchiveRestore, Upload, Trash2 } from "lucide-react";
import { api, ApiError, downloadFile } from "../api/client";
import type { Doc, DocumentList } from "../api/types";
import { Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, Input, PageHeader, Select, Spinner, Table, TD, TH } from "../components/ui";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/dialog";
import { fmtDateTime, fmtSize } from "../lib/utils";

let CATEGORIES: string[] = [];

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentList | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadCategory, setUploadCategory] = useState("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<Doc | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (categoryFilter) params.set("category", categoryFilter);
      if (search.trim()) params.set("search", search.trim());
      params.set("include_archived", String(includeArchived));
      setDocs(await api.get<DocumentList>(`/api/documents?${params.toString()}`));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, search, includeArchived]);

  useEffect(() => {
    api.get<{ categories: string[] }>("/api/documents/categories").then((r) => {
      CATEGORIES = r.categories;
      setCategories(r.categories);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryFilter, search, includeArchived]);

  async function upload() {
    if (!uploadFile || !uploadCategory) return;
    setBusy(true);
    setUploadError("");
    try {
      const fd = new FormData();
      fd.append("file", uploadFile);
      fd.append("category", uploadCategory);
      fd.append("title", uploadTitle);
      await api.post("/api/documents", fd);
      setUploadOpen(false);
      setUploadFile(null);
      setUploadTitle("");
      setUploadCategory("");
      load();
    } catch (e) {
      setUploadError(e instanceof ApiError ? e.message : "The upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleArchive(d: Doc) {
    try {
      await api.post(`/api/documents/${d.id}/archive?archived=${!d.is_archived}`);
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not update the document.");
    }
  }

  return (
    <div>
      <PageHeader
        title="Document Library"
        description="Central store for question papers, OMR sheets, results and examination reports."
        actions={
          <Button onClick={() => setUploadOpen(true)}><Upload size={15} /> Upload Document</Button>
        }
      />

      <Card className="mb-4 flex flex-wrap items-center gap-2 p-3">
        <Select className="w-56" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </Select>
        <Input className="w-56" placeholder="Search by title…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <label className="flex items-center gap-2 text-xs text-stone-500">
          <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} />
          Show archived
        </label>
      </Card>

      <Card>
        {loading && !docs ? (
          <div className="flex h-48 items-center justify-center"><Spinner /></div>
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !docs || docs.items.length === 0 ? (
          <EmptyState
            icon={<FolderOpen size={36} />}
            title="The library is empty"
            description="Upload question papers, answer keys, OMR sheets or reports. Files are organised by category and only staff with sign-in access can download them."
            action={<Button size="sm" className="mt-2" onClick={() => setUploadOpen(true)}><Upload size={14} /> Upload Document</Button>}
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <TH>Title</TH>
                <TH>Category</TH>
                <TH>File</TH>
                <TH>Size</TH>
                <TH>Uploaded By</TH>
                <TH>Date</TH>
                <TH className="text-right">Actions</TH>
              </tr>
            </thead>
            <tbody>
              {docs.items.map((d) => (
                <tr key={d.id} className={`hover:bg-cream/60 ${d.is_archived ? "opacity-60" : ""}`}>
                  <TD className="font-medium">
                    {d.title} {d.is_archived && <Badge tone="neutral">Archived</Badge>}
                  </TD>
                  <TD><Badge tone="brand">{d.category}</Badge></TD>
                  <TD className="max-w-[200px] truncate text-stone-500" title={d.file_name}>{d.file_name}</TD>
                  <TD>{fmtSize(d.file_size)}</TD>
                  <TD className="text-stone-500">{d.uploaded_by}</TD>
                  <TD>{fmtDateTime(d.created_at)}</TD>
                  <TD className="text-right">
                    <div className="flex justify-end gap-1">
                      <button className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink" title="Download" onClick={() => downloadFile(`/api/documents/${d.id}/download`, d.file_name)}>
                        <Download size={15} />
                      </button>
                      <button className="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-ink" title={d.is_archived ? "Restore" : "Archive"} onClick={() => toggleArchive(d)}>
                        {d.is_archived ? <ArchiveRestore size={15} /> : <Archive size={15} />}
                      </button>
                      <button className="rounded-md p-1.5 text-stone-400 hover:bg-red-50 hover:text-red-600" title="Delete" onClick={() => setDeleting(d)}>
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </TD>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {/* upload dialog */}
      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Upload Document</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-stone-600">Category *</label>
              <Select value={uploadCategory} onChange={(e) => setUploadCategory(e.target.value)}>
                <option value="">Select category…</option>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-stone-600">Title (optional)</label>
              <Input value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} maxLength={200} placeholder="Defaults to the file name" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-stone-600">File * (PDF, DOCX, XLSX, CSV, PNG, JPG · max 100 MB)</label>
              <input
                type="file"
                className="w-full text-xs text-stone-600"
                onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg"
              />
            </div>
            {uploadError && <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{uploadError}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadOpen(false)}>Cancel</Button>
            <Button onClick={upload} loading={busy} disabled={!uploadFile || !uploadCategory}>Upload</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete "${deleting?.title ?? "document"}"?`}
        description="The file will be permanently removed from the library. This cannot be undone."
        confirmLabel="Delete Permanently"
        onConfirm={async () => {
          if (!deleting) return;
          setBusy(true);
          try {
            await api.delete(`/api/documents/${deleting.id}`);
            setDeleting(null);
            load();
          } catch (e) {
            alert(e instanceof Error ? e.message : "Could not delete the document.");
          } finally {
            setBusy(false);
          }
        }}
        loading={busy}
      />
    </div>
  );
}
