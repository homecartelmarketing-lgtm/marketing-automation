import { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronUp, Terminal, Square, Trash2, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';

export interface PipelineExecutionState {
  status: 'idle' | 'running' | 'completed' | 'error' | 'stopped';
  active_fixture: string | null;
  active_table_id: string | null;
  current_phase: string;
  current_phase_index: number;
  total_phases: number;
  elapsed_seconds: number;
  logs: string[];
  error?: string | null;
}

interface LiveLogViewerProps {
  pipelineState: PipelineExecutionState;
  onStop: () => void;
  onClearLogs?: () => void;
  fixtureName?: string;
}

export function LiveLogViewer({
  pipelineState,
  onStop,
  onClearLogs,
  fixtureName,
}: LiveLogViewerProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs as new lines arrive
  useEffect(() => {
    if (scrollRef.current && isExpanded) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [pipelineState.logs, isExpanded]);

  if (pipelineState.status === 'idle' && pipelineState.logs.length === 0) {
    return null;
  }

  const formatElapsed = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusBadge = () => {
    switch (pipelineState.status) {
      case 'running':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-500/20 text-sky-400 border border-sky-500/30">
            <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
            RUNNING ({formatElapsed(pipelineState.elapsed_seconds)})
          </span>
        );
      case 'completed':
      case 'success':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            COMPLETED
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <AlertTriangle className="w-3.5 h-3.5" />
            FAILED
          </span>
        );
      case 'stopped':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">
            STOPPED
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="mt-6 bg-gray-900 border border-gray-800 rounded-2xl shadow-xl overflow-hidden text-gray-100 transition-all">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 bg-gray-950/80 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-gray-800 text-sky-400">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white">
                Live Execution Console
              </span>
              {fixtureName && (
                <span className="text-xs text-gray-400 font-mono">
                  [{fixtureName}]
                </span>
              )}
              {getStatusBadge()}
            </div>
            {pipelineState.current_phase && (
              <p className="text-xs text-sky-300 font-medium mt-0.5">
                {pipelineState.current_phase}
              </p>
            )}
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-2">
          {pipelineState.status === 'running' && (
            <button
              type="button"
              onClick={onStop}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:text-white bg-rose-950/50 hover:bg-rose-900 border border-rose-800/60 rounded-lg transition-colors"
            >
              <Square className="w-3 h-3 fill-current" />
              Stop Pipeline
            </button>
          )}

          {onClearLogs && pipelineState.status !== 'running' && (
            <button
              type="button"
              onClick={onClearLogs}
              title="Clear terminal logs"
              className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded-lg transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded-lg transition-colors"
          >
            {isExpanded ? (
              <>
                <span>Collapse</span>
                <ChevronUp className="w-4 h-4" />
              </>
            ) : (
              <>
                <span>Expand</span>
                <ChevronDown className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Expandable Terminal Body */}
      {isExpanded && (
        <div
          ref={scrollRef}
          className="p-4 h-64 overflow-y-auto font-mono text-xs leading-relaxed space-y-1 bg-black/40 selection:bg-sky-900 selection:text-white"
        >
          {pipelineState.logs.length === 0 ? (
            <div className="text-gray-500 italic flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Awaiting pipeline output...
            </div>
          ) : (
            pipelineState.logs.map((log, index) => {
              const isError = log.includes('[ERROR]') || log.includes('[EXCEPTION]');
              const isDone = log.includes('[DONE]') || log.includes('[COMPLETE]');
              const isPhase = log.includes('Phase ') || log.includes('ROW ');
              const isInfo = log.includes('[INFO]') || log.includes('[START]');

              let textColor = 'text-gray-300';
              if (isError) textColor = 'text-rose-400 font-semibold';
              else if (isDone) textColor = 'text-emerald-400 font-semibold';
              else if (isPhase) textColor = 'text-sky-300 font-bold';
              else if (isInfo) textColor = 'text-amber-300';

              return (
                <div key={index} className={`whitespace-pre-wrap break-all ${textColor}`}>
                  {log}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
