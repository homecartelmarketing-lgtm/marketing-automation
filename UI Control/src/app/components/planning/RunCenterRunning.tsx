import { AlertTriangle, ArrowRight, Check, Loader2, Square } from 'lucide-react';
import { Progress } from '../ui/progress';
import { LogStream } from './LogStream';
import type { PipelineExecutionState, QueueJob } from '../../types';

export function formatElapsed(seconds: number | undefined): string {
  const total = Math.max(0, Math.floor(seconds || 0));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

interface PhaseStepperProps {
  labels: string[];
  currentIndex: number;
  failed?: boolean;
}

/** Vertical list of phases: done (check), current (spinner / alert), pending (number). */
export function PhaseStepper({ labels, currentIndex, failed }: PhaseStepperProps) {
  return (
    <ol className="space-y-1.5">
      {labels.map((label, i) => {
        const step = i + 1;
        const done = step < currentIndex;
        const current = step === currentIndex;
        return (
          <li key={`${step}-${label}`} className="flex items-center gap-2.5 text-xs">
            <span
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold ${
                done
                  ? 'border-emerald-500 bg-emerald-500 text-white'
                  : current
                  ? failed
                    ? 'border-rose-500 bg-rose-50 text-rose-600'
                    : 'border-sky-500 bg-sky-50 text-sky-600'
                  : 'border-slate-200 bg-card text-slate-400'
              }`}
            >
              {done ? (
                <Check className="h-3 w-3" />
              ) : current ? (
                failed ? <AlertTriangle className="h-3 w-3" /> : <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                step
              )}
            </span>
            <span
              className={
                current ? 'font-semibold text-slate-900' : done ? 'text-slate-500' : 'text-slate-400'
              }
            >
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** Split a pipeline's "A ➔ B ➔ C" summary into step labels; fall back to "Phase N". */
export function phaseLabels(phaseSummary: string | undefined, total: number): string[] {
  const parts = (phaseSummary || '')
    .split('➔')
    .map(p => p.trim())
    .filter(Boolean);
  if (parts.length === total) return parts;
  return Array.from({ length: Math.max(total, 1) }, (_, i) => `Phase ${i + 1}`);
}

interface RunCenterRunningProps {
  job: QueueJob | null;
  pipelineState: PipelineExecutionState;
  phaseSummary?: string;
  onStop: () => void;
  onJump?: () => void;
  onDismissError?: () => void;
}

export function RunCenterRunning({
  job,
  pipelineState,
  phaseSummary,
  onStop,
  onJump,
  onDismissError,
}: RunCenterRunningProps) {
  const isError = pipelineState.status === 'error';
  const isRunning = !!job || pipelineState.status === 'running';

  if (!isRunning && !isError && pipelineState.logs.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-sm text-slate-500">
        <Check className="h-6 w-6 text-emerald-500" />
        <p className="font-medium text-slate-700">Nothing is running</p>
        <p className="text-xs">Press Run on any card to start a generation. Progress and logs appear here.</p>
      </div>
    );
  }

  const total = job?.total_phases || pipelineState.total_phases || 5;
  const index = job?.current_phase_index ?? pipelineState.current_phase_index ?? 0;
  const labels = phaseLabels(phaseSummary, total);
  const percent = Math.min(100, Math.round((Math.max(index, 0) / Math.max(total, 1)) * 100));

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 px-4 pb-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">
            {job?.fixture_name || pipelineState.active_fixture || 'Pipeline'}
          </p>
          <p className="truncate text-xs text-slate-500">{job?.pipeline_name || 'Last run'}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="font-mono text-xs tabular-nums text-slate-500">
            {formatElapsed(job?.elapsed_seconds ?? pipelineState.elapsed_seconds)}
          </span>
          {isRunning && (
            <button
              type="button"
              onClick={onStop}
              className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100"
            >
              <Square className="h-3 w-3 fill-current" />
              Stop
            </button>
          )}
        </div>
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between text-[11px] text-slate-500">
          <span className="truncate pr-2 font-medium text-slate-700">
            {job?.current_phase || pipelineState.current_phase || 'Starting...'}
          </span>
          <span className="shrink-0 tabular-nums">
            Step {Math.max(index, 0)}/{total}
          </span>
        </div>
        <Progress value={percent} className={`h-1.5 bg-slate-100 ${isError ? '[&>div]:bg-rose-500' : '[&>div]:bg-sky-500'}`} />
      </div>

      {isError && (
        <div className="flex items-start justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900">
          <div className="min-w-0">
            <span className="font-semibold">Run failed: </span>
            <span className="break-words">{pipelineState.error || 'See the log below.'}</span>
          </div>
          {onDismissError && (
            <button
              type="button"
              onClick={onDismissError}
              className="shrink-0 rounded-lg bg-rose-200/60 px-2 py-1 font-medium transition-colors hover:bg-rose-200"
            >
              Dismiss
            </button>
          )}
        </div>
      )}

      <PhaseStepper labels={labels} currentIndex={index} failed={isError} />

      {onJump && (
        <button
          type="button"
          onClick={onJump}
          className="inline-flex w-fit items-center gap-1 text-xs font-medium text-sky-700 hover:underline"
        >
          Go to this pipeline <ArrowRight className="h-3 w-3" />
        </button>
      )}

      <div className="flex min-h-0 flex-1 flex-col">
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Live log</p>
        <LogStream logs={pipelineState.logs} className="min-h-40 flex-1" />
      </div>
    </div>
  );
}
