"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FileRecord, Memory } from "@/lib/types";
import { Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

export default function FilesPage() {
  const [files, setFiles] = useState<FileRecord[] | null>(null);
  const [drafts, setDrafts] = useState<Memory[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<FileRecord[]>("/files").then(setFiles).catch((e: Error) => setError(e.message));
    api<Memory[]>("/memories?kind=file_ref").then(setDrafts).catch(() => undefined);
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!files) return <Loading />;

  return (
    <div>
      <PageTitle title="File Management" sub="File records tracked by the system (GET /files)" />
      {files.length === 0 ? (
        <Empty message="No file records in the files table yet." />
      ) : (
        <div className="space-y-2">
          {files.map((f) => (
            <Card key={f.id} className="flex flex-wrap items-center gap-3 p-3">
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-zinc-100">{f.name}</span>
              <span className="text-xs text-zinc-500">{f.kind}</span>
              <span className="text-xs text-zinc-500">{f.size_bytes != null ? `${f.size_bytes} bytes` : "size n/a"}</span>
              <span className="max-w-full truncate text-xs text-zinc-600">{f.path}</span>
              <span className="text-xs text-zinc-500">{fmtDate(f.created_at)}</span>
            </Card>
          ))}
        </div>
      )}

      <h2 className="mb-2 mt-8 text-sm font-semibold text-zinc-200">
        Documents stored as memories (kind: file_ref) — includes email drafts
      </h2>
      {drafts.length === 0 ? (
        <Empty message="No file-reference memories yet. Email drafts from the Communication Agent appear here." />
      ) : (
        <div className="space-y-2">
          {drafts.map((m) => (
            <Card key={m.id}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div className="text-sm font-medium text-zinc-100">{m.title || "Untitled document"}</div>
                <div className="text-xs text-zinc-500">{fmtDate(m.created_at)}</div>
              </div>
              <p className="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap text-sm text-zinc-400">{m.content}</p>
              {m.tags.length > 0 ? <div className="mt-1 text-xs text-zinc-500">tags: {m.tags.join(", ")}</div> : null}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
