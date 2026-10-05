import { useState } from 'react';
import { CalendarDays, Loader2, UploadCloud, X } from 'lucide-react';
import { toast } from 'sonner';
import { getPipelineByType } from '../../constants/pipelines';
import type { PipelineType } from '../../types';

interface CalendarJob {
  date: string;
  pipeline_type: string;
  fixture_id: string;
  run_endpoint: string;
  status_endpoint: string;
}

interface CalendarSkipped {
  date: string;
  idea: string;
  status: string;
  reason: string;
}

interface CalendarImportModalProps {
  open: boolean;
  studioPin: string;
  onClose: () => void;
}

const MONTHS = ['July', 'August', 'September', 'October'];

function pipelineName(t: string): string {
  return getPipelineByType(t as PipelineType)?.name ?? t;
}

function authHeaders(pin: string): Record<string, string> {
  return pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {};
}

export function CalendarImportModal({ open, studioPin, onClose }: CalendarImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [month, setMonth] = useState('October');
  const [jobs, setJobs] = useState<CalendarJob[]>([]);
  const [skipped, setSkipped] = useState<CalendarSkipped[]>([]);
  const [busy, setBusy] = useState<'preview' | 'enqueue' | null>(null);
  const [result, setResult] = useState<string | null>(null);

  if (!open) return null;

  const reset = () => {
    setJobs([]);
    setSkipped([]);
    setResult(null);
  };

  const handlePreview = async () => {
    if (!file) {
      toast.error('Choose an .xlsx calendar file first');
      return;
    }
    setBusy('preview');
    setResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('month', month);
      const res = await fetch('/api/calendar/preview', {
        method: 'POST',
        headers: authHeaders(studioPin),
        body: form,
      });
      const data = await res.json();
      if (!res.ok || data.status !== 'success') {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setJobs(data.jobs ?? []);
      setSkipped(data.skipped ?? []);
      if ((data.job_count ?? 0) === 0) {
        toast.info('No TO DO slots found — nothing to enqueue');
      }
    } catch (e) {
      toast.error(`Preview failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(null);
    }
  };

  const handleEnqueue = async () => {
    if (!file || jobs.length === 0) return;
    setBusy('enqueue');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('month', month);
      if (studioPin) form.append('pin', studioPin);
      const res = await fetch('/api/calendar/enqueue', {
        method: 'POST',
        headers: authHeaders(studioPin),
        body: form,
      });
      const data = await res.json();
      if (!res.ok || data.status !== 'success') {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setResult(`Enqueued ${data.enqueued} job(s), skipped ${data.skipped_count ?? 0}. They will run one at a time in the queue.`);
      toast.success(`Enqueued ${data.enqueued} calendar job(s)`);
      reset();
      setJobs([]);
      setSkipped([]);
    } catch (e) {
      toast.error(`Enqueue failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-lg rounded-xl bg-card shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <CalendarDays className="h-4 w-4 text-sky-600" />
            Import Content Calendar
          </h2>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 px-4 py-3">
          <p className="text-xs text-slate-500">
            Only slots marked <span className="font-semibold">TO DO</span> are enqueued. Posted / Scheduled slots are never re-run.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
              <UploadCloud className="h-3.5 w-3.5" />
              {file ? file.name : 'Choose .xlsx'}
              <input
                type="file"
                accept=".xlsx,.xlsm"
                className="hidden"
                onChange={e => {
                  setFile(e.target.files?.[0] ?? null);
                  reset();
                }}
              />
            </label>
            <select
              value={month}
              onChange={e => {
                setMonth(e.target.value);
                reset();
              }}
              className="rounded-lg border border-slate-200 bg-card px-2 py-1.5 text-xs font-semibold text-slate-700"
            >
              {MONTHS.map(m => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handlePreview}
              disabled={!file || busy !== null}
              className="rounded-lg bg-sky-600 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-sky-700 disabled:opacity-60"
            >
              {busy === 'preview' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Preview'}
            </button>
          </div>

          {jobs.length > 0 && (
            <div className="max-h-56 overflow-y-auto rounded-lg border border-slate-100">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-2 py-1.5 font-semibold">Date</th>
                    <th className="px-2 py-1.5 font-semibold">Pipeline</th>
                    <th className="px-2 py-1.5 font-semibold">Fixture</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j, i) => (
                    <tr key={`${j.date}-${j.pipeline_type}-${j.fixture_id}-${i}`} className="border-t border-slate-100">
                      <td className="px-2 py-1 font-mono text-slate-600">{j.date}</td>
                      <td className="px-2 py-1 text-slate-800">{pipelineName(j.pipeline_type)}</td>
                      <td className="px-2 py-1 text-slate-600">{j.fixture_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {(jobs.length > 0 || skipped.length > 0) && (
            <p className="text-xs text-slate-500">
              {jobs.length} TO DO job(s){skipped.length > 0 && ` · ${skipped.length} skipped (Posted / Scheduled / empty)`}
            </p>
          )}

          {result && <p className="rounded-lg bg-emerald-50 px-2.5 py-2 text-xs font-medium text-emerald-700">{result}</p>}

          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">
              Close
            </button>
            <button
              type="button"
              onClick={handleEnqueue}
              disabled={jobs.length === 0 || busy !== null}
              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
            >
              {busy === 'enqueue' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : `Enqueue ${jobs.length} job(s)`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
