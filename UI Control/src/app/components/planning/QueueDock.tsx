import React, { useState } from 'react';
import {
  Loader2,
  Square,
  Clock,
  CheckCircle2,
  XCircle,
  X,
  ChevronUp,
  ChevronDown,
  Trash2,
  ListOrdered,
  Sparkles,
} from 'lucide-react';

export interface QueueJob {
  id: string;
  pipeline_type: string;
  pipeline_name: string;
  fixture_id: string;
  fixture_name: string;
  format_tab: string;
  subtab_index: number;
  table_id: string;
  enqueued_at?: number;
  started_at?: number;
  current_phase?: string;
  current_phase_index?: number;
  total_phases?: number;
  elapsed_seconds?: number;
  status?: string;
  max_items?: number;
  error?: string;
}

export interface QueueHistoryItem {
  id: string;
  pipeline_name: string;
  fixture_name: string;
  format_tab: string;
  status: string;
  duration_seconds: number;
  finished_at: number;
  error?: string;
}

interface QueueDockProps {
  activeJob: QueueJob | null;
  queue: QueueJob[];
  history: QueueHistoryItem[];
  onCancelQueueItem: (jobId: string, fixtureName: string) => void;
  onClearQueue: () => void;
  onStopActiveJob: () => void;
}

export function QueueDock({
  activeJob,
  queue,
  history,
  onCancelQueueItem,
  onClearQueue,
  onStopActiveJob,
}: QueueDockProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const formatBadgeColor = (tab: string) => {
    const t = (tab || '').toLowerCase();
    if (t === 'reel') return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
    if (t === 'story') return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
    return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '0s';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins === 0) return `${secs}s`;
    return `${mins}m ${secs}s`;
  };

  const handleStop = async () => {
    setIsStopping(true);
    try {
      await onStopActiveJob();
    } finally {
      setIsStopping(false);
    }
  };

  const hasItems = !!activeJob || queue.length > 0;

  return (
    <div className="fixed bottom-4 inset-x-0 mx-auto max-w-4xl z-40 px-4 pointer-events-none">
      <div className="relative pointer-events-auto">
        {/* Expandable Flyout Drawer */}
        {isOpen && (
          <div className="absolute bottom-full mb-3 inset-x-0 bg-gray-950/95 backdrop-blur-xl border border-gray-800 rounded-2xl shadow-2xl p-4 text-white animate-in slide-in-from-bottom-2 duration-200">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <ListOrdered className="w-4 h-4 text-sky-400" />
                <span className="font-semibold text-sm">Sequential Generation Queue</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 border border-gray-700">
                  {queue.length} upcoming
                </span>
              </div>
              <div className="flex items-center gap-2">
                {queue.length > 0 && (
                  <button
                    type="button"
                    onClick={onClearQueue}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Clear Queue</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Queue List */}
            <div className="py-3 max-h-60 overflow-y-auto space-y-2 pr-1">
              {queue.length === 0 ? (
                <div className="py-6 text-center text-xs text-gray-400 flex flex-col items-center gap-2">
                  <Clock className="w-5 h-5 text-gray-500" />
                  <span>No upcoming items in the queue. Click &quot;Run&quot; or &quot;+ Queue&quot; on any card to schedule.</span>
                </div>
              ) : (
                queue.map((item, idx) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between gap-3 p-2.5 rounded-xl bg-gray-900/80 border border-gray-800/80 hover:border-gray-700 transition-colors"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="flex items-center justify-center w-5 h-5 rounded-full bg-gray-800 text-[11px] font-bold text-gray-300">
                        {idx + 1}
                      </span>
                      <span
                        className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md border ${formatBadgeColor(
                          item.format_tab
                        )}`}
                      >
                        {item.format_tab}
                      </span>
                      <div className="truncate">
                        <span className="font-semibold text-xs text-gray-200">{item.fixture_name}</span>
                        <span className="text-[11px] text-gray-400 ml-1.5 truncate">
                          ({item.pipeline_name})
                        </span>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => onCancelQueueItem(item.id, item.fixture_name)}
                      className="p-1 rounded-lg text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors shrink-0"
                      title="Remove from queue"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* History Footer */}
            {history.length > 0 && (
              <div className="pt-2 border-t border-gray-800/80">
                <div className="text-[11px] font-semibold text-gray-400 mb-2 flex items-center gap-1.5">
                  <Sparkles className="w-3 h-3 text-amber-400" />
                  <span>Recent Executions</span>
                </div>
                <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                  {history.slice(0, 4).map((hist) => (
                    <div
                      key={hist.id}
                      className="flex items-center justify-between text-xs py-1 px-2 rounded-lg bg-gray-900/40 text-gray-300"
                    >
                      <div className="flex items-center gap-2 truncate">
                        {hist.status === 'completed' ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                        )}
                        <span className="truncate">{hist.fixture_name}</span>
                        <span className="text-[10px] text-gray-500 truncate">({hist.pipeline_name})</span>
                      </div>
                      <span className="text-[11px] text-gray-400 shrink-0 ml-2">
                        {formatDuration(hist.duration_seconds)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Main Floating Dock Bar */}
        <div className="bg-gray-950/90 backdrop-blur-xl border border-gray-800 rounded-2xl shadow-2xl px-4 py-3 text-white flex items-center justify-between gap-4">
          {/* Left: Active Running Status or Idle */}
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {activeJob ? (
              <>
                <div className="relative flex items-center justify-center shrink-0">
                  <span className="absolute w-3 h-3 rounded-full bg-sky-400 animate-ping opacity-75" />
                  <Loader2 className="w-4 h-4 text-sky-400 animate-spin" />
                </div>

                <span
                  className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md border shrink-0 ${formatBadgeColor(
                    activeJob.format_tab
                  )}`}
                >
                  {activeJob.format_tab}
                </span>

                <div className="truncate min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-gray-100 truncate">
                      {activeJob.fixture_name}
                    </span>
                    <span className="text-[11px] text-sky-400 font-mono shrink-0">
                      {formatDuration(activeJob.elapsed_seconds)}
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-400 truncate">
                    {activeJob.current_phase || 'Generating content...'}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleStop}
                  disabled={isStopping}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 transition-all shrink-0 ml-1"
                  title="Stop the current running job and proceed to next in queue"
                >
                  <Square className="w-3 h-3 fill-current" />
                  <span>{isStopping ? 'Stopping...' : 'Stop'}</span>
                </button>
              </>
            ) : (
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Queue is idle — ready for new content generations.</span>
              </div>
            )}
          </div>

          {/* Right: Expandable Queue Counter Button */}
          <button
            type="button"
            onClick={() => setIsOpen((prev) => !prev)}
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all shrink-0 ${
              queue.length > 0
                ? 'bg-purple-600/20 text-purple-300 border-purple-500/40 hover:bg-purple-600/30 shadow-xs'
                : 'bg-gray-900 text-gray-300 border-gray-800 hover:bg-gray-850 hover:text-white'
            }`}
          >
            <ListOrdered className="w-3.5 h-3.5 text-purple-400" />
            <span>Queue ({queue.length})</span>
            {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
    </div>
  );
}
