import { useEffect, useRef } from 'react';
import { Loader2 } from 'lucide-react';

interface LogStreamProps {
  logs: string[];
  className?: string;
}

function lineColor(log: string): string {
  if (log.includes('[ERROR]') || log.includes('[EXCEPTION]') || log.includes('Traceback')) return 'text-rose-400 font-semibold';
  if (log.includes('[DONE]') || log.includes('[COMPLETE]') || log.includes('[SUCCESS]')) return 'text-emerald-400 font-semibold';
  if (log.includes('Phase ') || log.includes('[PHASE') || log.includes('ROW ')) return 'text-sky-300 font-bold';
  if (log.includes('[INFO]') || log.includes('[START]') || log.includes('[WARN')) return 'text-amber-300';
  return 'text-slate-300';
}

/** Terminal-style log list that follows new lines only while the reader is near the bottom. */
export function LogStream({ logs, className = '' }: LogStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [logs]);

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className={`overflow-y-auto rounded-xl bg-slate-900 p-3 font-mono text-[11px] leading-relaxed ${className}`}
    >
      {logs.length === 0 ? (
        <div className="flex items-center gap-2 italic text-slate-500">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Waiting for pipeline output...
        </div>
      ) : (
        logs.map((log, index) => (
          <div key={index} className={`whitespace-pre-wrap break-all ${lineColor(log)}`}>
            {log}
          </div>
        ))
      )}
    </div>
  );
}
