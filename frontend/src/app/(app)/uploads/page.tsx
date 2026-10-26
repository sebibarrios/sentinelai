"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { FileUp } from "lucide-react";
import { toast } from "sonner";

import { Pagination } from "@/components/pagination";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import {
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCan } from "@/hooks/use-auth";
import { useUploadLog, useUploads } from "@/hooks/use-security";
import { ApiError } from "@/lib/api";
import type { Upload } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";

const ACCEPT = [".csv", ".json", ".ndjson", ".jsonl"];
const MAX_MB = 10;

function formatSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function UploadsPage() {
  const canUpload = useCan("analyst");
  const [page, setPage] = useState(1);
  const uploads = useUploads(page);

  return (
    <>
      <PageHeader
        title="Log uploads"
        description="Upload authentication and network logs. Detection rules run as soon as a file is parsed."
      />
      {canUpload && <UploadCard />}
      <section className="mt-6 rounded-lg border bg-panel" aria-labelledby="history-heading">
        <h2 id="history-heading" className="px-5 pb-2 pt-5 font-medium">
          Upload history
        </h2>
        {uploads.error ? (
          <div className="p-4">
            <ErrorState error={uploads.error} onRetry={() => uploads.refetch()} />
          </div>
        ) : uploads.isPending ? (
          <div className="flex flex-col gap-2 p-4" aria-busy>
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : uploads.data.items.length === 0 ? (
          <EmptyState
            title="No uploads yet"
            description="Try one of the sample files in the repository's sample-data folder."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead className="w-28 text-right">Events</TableHead>
                <TableHead className="hidden w-28 text-right sm:table-cell">Rejected</TableHead>
                <TableHead className="w-24 text-right">Alerts</TableHead>
                <TableHead className="hidden w-44 md:table-cell">Uploaded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {uploads.data.items.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>
                    <span className="block max-w-[28ch] truncate font-medium" title={u.original_filename}>
                      {u.original_filename}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {u.format.toUpperCase()}, {formatSize(u.size_bytes)}, by {u.uploaded_by.full_name}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">{u.rows_parsed.toLocaleString()}</TableCell>
                  <TableCell
                    className={cn(
                      "hidden text-right sm:table-cell",
                      u.rows_rejected ? "text-sev-medium" : "text-muted-foreground",
                    )}
                  >
                    {u.rows_rejected.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    {u.alerts_created > 0 ? (
                      <Link href={`/alerts`} className="font-medium text-primary hover:underline">
                        {u.alerts_created}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">0</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground md:table-cell">
                    {formatDateTime(u.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {uploads.data && (
          <Pagination page={page} pageSize={10} total={uploads.data.total} onPage={setPage} />
        )}
      </section>
    </>
  );
}

function UploadCard() {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [result, setResult] = useState<Upload | null>(null);
  const upload = useUploadLog();

  function submit(file: File | undefined) {
    if (!file) return;
    setResult(null);
    upload.reset();
    // Client-side checks are for fast feedback only; the server re-validates everything.
    const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
    if (!ACCEPT.includes(ext)) {
      setLocalError("Choose a .csv, .json, or .ndjson file.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setLocalError(`The file is larger than ${MAX_MB} MB.`);
      return;
    }
    setLocalError(null);
    upload.mutate(file, {
      onSuccess: (u) => {
        setResult(u);
        toast.success(
          `Uploaded ${u.original_filename}: ${u.alerts_created} new alert${u.alerts_created === 1 ? "" : "s"}`,
        );
      },
    });
  }

  const serverError = upload.error instanceof ApiError ? upload.error : null;
  const error = localError ?? (upload.error ? (serverError?.message ?? "Upload failed.") : null);

  return (
    <section className="flex flex-col gap-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          submit(e.dataTransfer.files[0]);
        }}
        className={cn(
          "flex flex-col items-center gap-3 rounded-lg border border-dashed bg-panel px-6 py-10 text-center transition-colors",
          dragging ? "border-primary bg-primary/5" : "border-border",
        )}
      >
        <FileUp className="size-8 text-muted-foreground" aria-hidden />
        <div>
          <p className="font-medium">Drop a log file here</p>
          <p className="mt-1 text-sm text-muted-foreground">
            CSV with a header row, a JSON array, or newline-delimited JSON. Up to {MAX_MB} MB.
          </p>
        </div>
        <input
          ref={input}
          type="file"
          accept={ACCEPT.join(",")}
          className="sr-only"
          id="log-file"
          onChange={(e) => {
            submit(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <Button onClick={() => input.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? "Uploading and analyzing…" : "Choose file"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Required columns: timestamp, category (auth or network), action, outcome, src_ip.
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-sev-critical/40 bg-sev-critical/5 p-4">
          <p className="font-medium text-sev-critical">{error}</p>
          {serverError?.details && serverError.details.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1 text-sm text-muted-foreground">
              {serverError.details.slice(0, 5).map((d, i) => (
                <li key={i}>
                  {d.field}: {d.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result && <UploadResult upload={result} />}
    </section>
  );
}

function UploadResult({ upload }: { upload: Upload }) {
  return (
    <div className="rounded-lg border bg-panel p-5" role="status">
      <p className="font-medium">
        {upload.original_filename} processed in {upload.processing_ms ?? 0} ms
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        <div>
          <dt className="text-sm text-muted-foreground">Rows read</dt>
          <dd className="text-lg font-semibold">{upload.rows_total.toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">Events stored</dt>
          <dd className="text-lg font-semibold">{upload.rows_parsed.toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">Rows rejected</dt>
          <dd className={cn("text-lg font-semibold", upload.rows_rejected > 0 && "text-sev-medium")}>
            {upload.rows_rejected.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">New alerts</dt>
          <dd className="text-lg font-semibold">{upload.alerts_created}</dd>
        </div>
      </dl>
      {upload.rejection_samples.length > 0 && (
        <div className="mt-4 border-t pt-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            Rejected rows{upload.rows_rejected > upload.rejection_samples.length ? " (first 20)" : ""}
          </h3>
          <ul className="flex flex-col gap-1 text-sm">
            {upload.rejection_samples.map((s) => (
              <li key={s.line}>
                <span className="text-muted-foreground">Line {s.line}:</span> {s.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      {upload.alerts_created > 0 && (
        <Button asChild size="sm" className="mt-4">
          <Link href="/alerts">Review alerts</Link>
        </Button>
      )}
    </div>
  );
}
