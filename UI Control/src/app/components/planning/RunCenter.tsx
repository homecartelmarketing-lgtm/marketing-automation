import { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  ListOrdered,
  Loader2,
  Square,
  Trash2,
  X,
  XCircle,
} from 'lucide-react';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { RunCenterRunning, formatElapsed } from './RunCenterRunning';
import type { PipelineExecutionState, QueueHistoryItem, QueueJob } from '../../types';

interface RunCenterProps {
  activeJob: QueueJob | null;
  pendingQueue: QueueJob[];
  history: QueueHistoryItem[];
  pipelineState: PipelineExecutionState;
  /** "A ➔ B ➔ C" summary of the running pipeline, used for the step list. */
  phaseSummary?: string;
  onStop: () => void | Promise<void>;
  onCancelJob: (jobId: string, fixtureName: string) => void;
  onClearQueue: () => void;
  onJumpToJob?: (format: string, subtabIndex: number) => void;
  onDismissError?: () => void;
}

type PanelTab = 'running' | 'queue' | 'history';

const FORMAT_BADGE: Record<string, string> = {
  story: 'bg-purple-50 text-purple-700 border-purple-200',
  feed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  reel: 'bg-rose-50 text-rose-700 border-rose-200',
  adcover: 'bg-amber-50 text-amber-700 border-amber-200',
  banner: 'bg-sky-50 text-sky-700 border-sky-200',
};

function FormatBadge({ tab }: { tab: string }) {
  const key = (tab || '').toLowerCase();
  return (
    <span
      className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
        FORMAT_BADGE[key] || 'bg-slate-50 text-slate-600 border-slate-200'
      }`}
    >
      {tab}
    </span>
  );
}

function formatDuration(seconds?: number) {
  if (!seconds) return '0s';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return mins === 0 ? `${secs}s` : `${mins}m ${secs}s`;
}

function formatFinished(ts?: number) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Run Center: a slim status bar at the bottom of the page (never overlaps content) that opens a
 * right-hand panel with the running job (steps + logs), the upcoming queue and recent history.
 */
export function RunCenter({
  activeJob,
  pendingQueue,
  history,
  pipelineState,
  phaseSummary,
  onStop,
  onCancelJob,
  onClearQueue,
  onJumpToJob,
  onDismissError,
}: RunCenterProps) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<PanelTab>('running');
  const [isStopping, setIsStopping] = useState(false);

  const isError = !activeJob && pipelineState.status === 'error';
  const isRunning = !!activeJob || pipelineState.status === 'running';
  const total = activeJob?.total_phases || pipelineState.total_phases || 5;
  const index = activeJob?.current_phase_index ?? pipelineState.current_phase_index ?? 0;
  const percent = Math.min(100, Math.round((Math.max(index, 0) / Math.max(total, 1)) * 100));
  const fixtureName = activeJob?.fixture_name || pipelineState.active_fixture || 'Pipeline';
  const phaseName = activeJob?.current_phase || pipelineState.current_phase || 'Starting...';
  const elapsed = activeJob?.elapsed_seconds ?? pipelineState.elapsed_seconds;

  const openPanel = (next: PanelTab) => {
    setTab(next);
    setOpen(true);
  };

  const handleStop = async () => {
    setIsStopping(true);
    try {
      await onStop();
    } finally {
      setIsStopping(false);
    }
  };

  const jump = () => {
    if (activeJob) {
      onJumpToJob?.(activeJob.format_tab, activeJob.subtab_index);
      setOpen(false);
    }
  };

  return (
    <>
      <div
        className={`sticky bottom-0 z-30 border-t shadow-[0_-4px_16px_-8px_rgba(15,23,42,0.15)] backdrop-blur ${
          isError ? 'border-rose-200 bg-rose-50/95' : 'border-slate-200 bg-card/95'
        }`}
      >
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2.5 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => openPanel('running')}
            className="flex min-w-0 flex-1 items-center gap-3 rounded-lg text-left transition-colors hover:bg-slate-50/80"
            aria-label="Open run details"
          >
            {isRunning ? (
              <span className="relative flex h-2.5 w-2.5 shrink-0">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500" />
              </span>
            ) : isError ? (
              <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500" />
            ) : (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
            )}

            {isRunning ? (
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-xs">
                  <span className="truncate font-semibold text-slate-900">
                    {activeJob?.pipeline_name ? `${activeJob.pipeline_name} › ` : ''}
                    {fixtureName}
                  </span>
                  <span className="hidden shrink-0 font-mono tabular-nums text-slate-500 sm:inline">
                    {formatElapsed(elapsed)}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <div className="h-1 w-24 shrink-0 overflow-hidden rounded-full bg-slate-100 sm:w-40">
                    <div className="h-full rounded-full bg-sky-500 transition-all" style={{ width: `${percent}%` }} />
                  </div>
                  <span className="truncate text-[11px] text-slate-500">
                    Step {Math.max(index, 0)}/{total} · {phaseName}
                  </span>
                </div>
              </div>
            ) : isError ? (
              <span className="truncate text-xs text-rose-800">
                <span className="font-semibold">Run failed</span>
                {pipelineState.error ? `: ${pipelineState.error}` : ''}
              </span>
            ) : (
              <span className="truncate text-xs text-slate-500">
                Queue idle — ready for new generations
                {history[0] ? ` · last: ${history[0].fixture_name} (${history[0].status})` : ''}
              </span>
            )}
            <ChevronRight className="hidden h-4 w-4 shrink-0 text-slate-400 sm:block" />
          </button>

          {isRunning && (
            <button
              type="button"
              onClick={handleStop}
              disabled={isStopping}
              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100 disabled:opacity-60"
              title="Stop the current job"
            >
              <Square className="h-3 w-3 fill-current" />
              <span className="hidden sm:inline">{isStopping ? 'Stopping...' : 'Stop'}</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => openPanel(pendingQueue.length > 0 ? 'queue' : 'history')}
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition-colors ${
              pendingQueue.length > 0
                ? 'border-purple-200 bg-purple-50 text-purple-700 hover:bg-purple-100'
                : 'border-slate-200 bg-card text-slate-600 hover:bg-slate-50'
            }`}
          >
            <ListOrdered className="h-3.5 w-3.5" />
            Queue ({pendingQueue.length})
          </button>
        </div>
      </div>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-full gap-0 bg-card p-0 sm:max-w-md">
          <SheetHeader className="border-b border-slate-100 pb-3 pr-12">
            <SheetTitle className="text-base text-slate-900">Run Center</SheetTitle>
            <SheetDescription className="text-xs">
              Live progress, upcoming queue and recent runs. Jobs run one at a time.
            </SheetDescription>
          </SheetHeader>

          <Tabs value={tab} onValueChange={v => setTab(v as PanelTab)} className="flex min-h-0 flex-1 flex-col gap-0">
            <TabsList className="mx-4 mt-3 grid w-auto grid-cols-3">
              <TabsTrigger value="running" className="text-xs">
                {isRunning && <Loader2 className="mr-1 h-3 w-3 animate-spin text-sky-500" />}
                Running
              </TabsTrigger>
              <TabsTrigger value="queue" className="text-xs">
                Queue ({pendingQueue.length})
              </TabsTrigger>
              <TabsTrigger value="history" className="text-xs">
                History
              </TabsTrigger>
            </TabsList>

            <TabsContent value="running" className="mt-4 min-h-0 flex-1 overflow-y-auto">
              <RunCenterRunning
                job={activeJob}
                pipelineState={pipelineState}
                phaseSummary={phaseSummary}
                onStop={handleStop}
                onJump={activeJob ? jump : undefined}
                onDismissError={onDismissError}
              />
            </TabsContent>

            <TabsContent value="queue" className="mt-4 min-h-0 flex-1 overflow-y-auto px-4 pb-4">
              {pendingQueue.length > 0 && (
                <div className="mb-3 flex justify-end">
                  <button
                    type="button"
                    onClick={onClearQueue}
                    className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium text-rose-600 transition-colors hover:bg-rose-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Clear queue
                  </button>
                </div>
              )}
              {pendingQueue.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-10 text-center text-xs text-slate-500">
                  <Clock className="h-5 w-5 text-slate-300" />
                  <span>Nothing waiting. Press Run on a card while another job is running to line it up.</span>
                </div>
              ) : (
                <ul className="space-y-2">
                  {pendingQueue.map((item, i) => (
                    <li
                      key={item.id}
                      className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-card p-2.5"
                    >
                      <div className="flex min-w-0 items-center gap-2.5">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-bold text-slate-600">
                          {i + 1}
                        </span>
                        <FormatBadge tab={item.format_tab} />
                        <button
                          type="button"
                          onClick={() => {
                            onJumpToJob?.(item.format_tab, item.subtab_index);
                            setOpen(false);
                          }}
                          className="min-w-0 truncate text-left text-xs"
                          title="Go to this pipeline"
                        >
                          <span className="font-semibold text-slate-800">{item.fixture_name}</span>
                          <span className="ml-1.5 text-slate-500">({item.pipeline_name})</span>
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => onCancelJob(item.id, item.fixture_name)}
                        className="shrink-0 rounded-lg p-1 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                        title="Remove from queue"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>

            <TabsContent value="history" className="mt-4 min-h-0 flex-1 overflow-y-auto px-4 pb-4">
              {history.length === 0 ? (
                <div className="py-10 text-center text-xs text-slate-500">No runs yet in this session.</div>
              ) : (
                <ul className="space-y-2">
                  {history.slice(0, 10).map(item => {
                    const ok = item.status === 'completed';
                    return (
                      <li key={item.id} className="rounded-xl border border-slate-200 bg-card p-2.5">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex min-w-0 items-center gap-2">
                            {ok ? (
                              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                            ) : (
                              <XCircle className="h-4 w-4 shrink-0 text-rose-500" />
                            )}
                            <FormatBadge tab={item.format_tab} />
                            <span className="truncate text-xs">
                              <span className="font-semibold text-slate-800">{item.fixture_name}</span>
                              <span className="ml-1.5 text-slate-500">({item.pipeline_name})</span>
                            </span>
                          </div>
                          <span className="shrink-0 text-[11px] tabular-nums text-slate-500">
                            {formatDuration(item.duration_seconds)} · {formatFinished(item.finished_at)}
                          </span>
                        </div>
                        {!ok && item.error && (
                          <p className="mt-1.5 break-words rounded-lg bg-rose-50 px-2 py-1 text-[11px] text-rose-800">
                            {item.error}
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>
    </>
  );
}
