import { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';
import type { QueueJob, QueueHistoryItem } from '../types';
import { FixtureData } from '../components/planning/FixtureCard';
import { PipelineType } from '../types';

export interface UseQueueResult {
  activeQueueJob: QueueJob | null;
  pendingQueue: QueueJob[];
  queueHistory: QueueHistoryItem[];
  getQueueInfo: (fixtureId: string, activePipelineType?: PipelineType) => { isQueued: boolean; position: number };
  handleCancelQueueFixture: (fixture: FixtureData, studioPin: string) => Promise<void>;
  handleCancelQueueItem: (jobId: string, fixtureName: string, studioPin: string) => Promise<void>;
  handleClearQueue: (studioPin: string) => Promise<void>;
  handleStopActiveJob: (studioPin: string, fallbackStop?: () => Promise<void>) => Promise<void>;
  setPendingQueue: React.Dispatch<React.SetStateAction<QueueJob[]>>;
}

export interface FinishedQueueJob {
  job: QueueJob;
  history?: QueueHistoryItem;
}

export function useQueue(
  onJobTransition?: (
    activeJob: QueueJob | null,
    wasActive: boolean,
    finished?: FinishedQueueJob
  ) => void,
  onQueueLost?: () => void
): UseQueueResult {
  const [activeQueueJob, setActiveQueueJob] = useState<QueueJob | null>(null);
  const [pendingQueue, setPendingQueue] = useState<QueueJob[]>([]);
  const [queueHistory, setQueueHistory] = useState<QueueHistoryItem[]>([]);
  const activeQueueJobRef = useRef<QueueJob | null>(null);
  const signatureRef = useRef<string>('');
  const onJobTransitionRef = useRef(onJobTransition);
  onJobTransitionRef.current = onJobTransition;
  const onQueueLostRef = useRef(onQueueLost);
  onQueueLostRef.current = onQueueLost;
  const idleStreakRef = useRef<number>(0);

  useEffect(() => {
    const pollQueue = async () => {
      try {
        const res = await fetch('/api/queue/status');
        if (!res.ok) return;
        const data = await res.json();
        const active: QueueJob | null = data.active_job || null;
        const queue: QueueJob[] = data.queue || [];
        const history: QueueHistoryItem[] = data.history || [];

        const prevActive = activeQueueJobRef.current;
        activeQueueJobRef.current = active;

        // Report once when the queue has been empty for ~6s (4 polls) so the UI can drop a
        // run it still shows as "running" that the server no longer knows about.
        idleStreakRef.current = !active && queue.length === 0 ? idleStreakRef.current + 1 : 0;
        if (idleStreakRef.current === 4) onQueueLostRef.current?.();

        // Skip identical polls so idle ticks do not re-render the whole Studio.
        const logs = (active as { logs?: string[] } | null)?.logs;
        const signature = JSON.stringify([
          active?.id,
          active?.current_phase,
          active?.current_phase_index,
          active?.total_phases,
          active?.elapsed_seconds,
          active?.error,
          logs?.length,
          logs?.[logs.length - 1],
          queue.map(j => j.id),
          history.map(h => `${h.id}:${h.status}`),
        ]);
        if (signature === signatureRef.current) return;
        signatureRef.current = signature;

        setActiveQueueJob(active);
        setPendingQueue(queue);
        setQueueHistory(history);

        // A job is finished when it disappears or is replaced by a different one.
        const finishedJob = prevActive && (!active || active.id !== prevActive.id) ? prevActive : null;
        const finished: FinishedQueueJob | undefined = finishedJob
          ? { job: finishedJob, history: history.find(h => h.id === finishedJob.id) }
          : undefined;

        onJobTransitionRef.current?.(active, !!prevActive, finished);
      } catch {
        // silent fail
      }
    };

    pollQueue();
    const interval = setInterval(pollQueue, 1500);
    return () => clearInterval(interval);
  }, []);

  const getQueueInfo = useCallback(
    (fixtureId: string, activePipelineType?: PipelineType) => {
      if (!activePipelineType) return { isQueued: false, position: 0 };
      const idx = pendingQueue.findIndex(
        j => j.pipeline_type === activePipelineType && j.fixture_id === fixtureId
      );
      if (idx >= 0) {
        return { isQueued: true, position: idx + 1 };
      }
      return { isQueued: false, position: 0 };
    },
    [pendingQueue]
  );

  const handleCancelQueueFixture = useCallback(async (fixture: FixtureData, studioPin: string) => {
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch('/api/queue/cancel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ fixture_id: fixture.id, pin }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(data.message || `Removed ${fixture.name} from queue`);
        setPendingQueue(prev => prev.filter(j => j.fixture_id !== fixture.id));
      } else {
        toast.error(data.error || 'Failed to cancel queued item');
      }
    } catch (err) {
      toast.error(`Error: ${err}`);
    }
  }, []);

  const handleCancelQueueItem = useCallback(async (jobId: string, fixtureName: string, studioPin: string) => {
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch('/api/queue/cancel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ job_id: jobId, pin }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(data.message || `Removed ${fixtureName} from queue`);
        setPendingQueue(prev => prev.filter(j => j.id !== jobId));
      } else {
        toast.error(data.error || 'Failed to cancel queued item');
      }
    } catch (err) {
      toast.error(`Error: ${err}`);
    }
  }, []);

  const handleClearQueue = useCallback(async (studioPin: string) => {
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch('/api/queue/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ pin }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(data.message || 'Generation queue cleared');
        setPendingQueue([]);
      } else {
        toast.error(data.error || 'Failed to clear queue');
      }
    } catch (err) {
      toast.error(`Error: ${err}`);
    }
  }, []);

  const handleStopActiveJob = useCallback(
    async (studioPin: string, fallbackStop?: () => Promise<void>) => {
      const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
      try {
        const res = await fetch('/api/queue/stop-current', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
          },
          body: JSON.stringify({ pin }),
        });
        const data = await res.json();
        if (res.ok) {
          toast.info(data.message || 'Stop request sent');
        } else if (fallbackStop) {
          await fallbackStop();
        }
      } catch {
        if (fallbackStop) {
          await fallbackStop();
        }
      }
    },
    []
  );

  return {
    activeQueueJob,
    pendingQueue,
    queueHistory,
    getQueueInfo,
    handleCancelQueueFixture,
    handleCancelQueueItem,
    handleClearQueue,
    handleStopActiveJob,
    setPendingQueue,
  };
}
