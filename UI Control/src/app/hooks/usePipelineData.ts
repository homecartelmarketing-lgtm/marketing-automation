import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { PIPELINES, getPipelineByType } from '../constants/pipelines';
import { PipelineType, StatusCountMap, StatusCounts } from '../types';

export interface UsePipelineDataResult {
  progressState: Record<string, number>;
  setProgressState: React.Dispatch<React.SetStateAction<Record<string, number>>>;
  moodboardOverrides: Record<string, Record<string, string>>;
  promptOverrides: Record<string, Record<string, string>>;
  statusCounts: Record<string, StatusCountMap>;
  tableIdOverrides: Record<string, Record<string, string>>;
  isLoadingCounts: boolean;
  tunnelInfo: { active: boolean; public_url: string };
  setTunnelInfo: React.Dispatch<React.SetStateAction<{ active: boolean; public_url: string }>>;
  getMoodboard: (pipelineType: PipelineType, fixtureId: string) => string;
  getPrompt: (pipelineType: PipelineType, fixtureId: string) => string | undefined;
  getStatusCounts: (pipelineType: PipelineType, fixtureId: string) => StatusCounts | undefined;
  getTableId: (pipelineType: PipelineType, fixtureId: string) => string | undefined;
  updateMoodboard: (pipelineType: PipelineType, fixtureId: string, moodboardId: string) => void;
  updatePrompt: (pipelineType: PipelineType, fixtureId: string, prompt: string) => void;
  fetchLiveCounts: (refresh?: boolean, showToast?: boolean) => Promise<void>;
}

export function usePipelineData(): UsePipelineDataResult {
  const [progressState, setProgressState] = useState<Record<string, number>>({});
  const [isLoadingCounts, setIsLoadingCounts] = useState<boolean>(false);
  const [tunnelInfo, setTunnelInfo] = useState<{ active: boolean; public_url: string }>({
    active: false,
    public_url: '',
  });

  const [moodboardOverrides, setMoodboardOverrides] = useState<Record<string, Record<string, string>>>({
    'one-at-a-time-lights-reel': {
      'living-room': 'fb2487fb-2895-4d2c-9758-805aaf1bac69',
    },
  });

  const [promptOverrides, setPromptOverrides] = useState<Record<string, Record<string, string>>>({
    'one-at-a-time-lights-reel': {
      'living-room': 'Generate me a modern bedroom',
    },
  });

  const [statusCounts, setStatusCounts] = useState<Record<string, StatusCountMap>>({});
  const [tableIdOverrides, setTableIdOverrides] = useState<Record<string, Record<string, string>>>({});

  const getMoodboard = useCallback(
    (pipelineType: PipelineType, fixtureId: string): string => {
      if (!pipelineType) return '';
      const override = moodboardOverrides[pipelineType]?.[fixtureId];
      if (override) return override;
      const pipeCfg = getPipelineByType(pipelineType);
      const fixture = pipeCfg?.fixtures.find(f => f.id === fixtureId);
      return fixture?.moodboardId || '';
    },
    [moodboardOverrides]
  );

  const getPrompt = useCallback(
    (pipelineType: PipelineType, fixtureId: string): string | undefined => {
      if (!pipelineType) return undefined;
      const override = promptOverrides[pipelineType]?.[fixtureId];
      if (override !== undefined) return override;
      const pipeCfg = getPipelineByType(pipelineType);
      const fixture = pipeCfg?.fixtures.find(f => f.id === fixtureId);
      return fixture?.prompt;
    },
    [promptOverrides]
  );

  const getStatusCounts = useCallback(
    (pipelineType: PipelineType, fixtureId: string): StatusCounts | undefined => {
      if (!pipelineType) return undefined;
      return statusCounts[pipelineType]?.[fixtureId];
    },
    [statusCounts]
  );

  const getTableId = useCallback(
    (pipelineType: PipelineType, fixtureId: string): string | undefined => {
      if (!pipelineType) return undefined;
      const override = tableIdOverrides[pipelineType]?.[fixtureId];
      if (override) return override;
      const pipeCfg = getPipelineByType(pipelineType);
      const fixture = pipeCfg?.fixtures.find(f => f.id === fixtureId);
      return fixture?.tableId;
    },
    [tableIdOverrides]
  );

  const updateMoodboard = useCallback(
    (pipelineType: PipelineType, fixtureId: string, moodboardId: string) => {
      if (!pipelineType) return;
      setMoodboardOverrides(prev => ({
        ...prev,
        [pipelineType]: {
          ...(prev[pipelineType] || {}),
          [fixtureId]: moodboardId,
        },
      }));
    },
    []
  );

  const updatePrompt = useCallback(
    (pipelineType: PipelineType, fixtureId: string, prompt: string) => {
      if (!pipelineType) return;
      setPromptOverrides(prev => ({
        ...prev,
        [pipelineType]: {
          ...(prev[pipelineType] || {}),
          [fixtureId]: prompt,
        },
      }));
    },
    []
  );

  const fetchLiveCounts = useCallback(
    async (refresh = false, showToast = false) => {
      setIsLoadingCounts(true);
      try {
        const tunnelPromise = fetch('/api/tunnel/status')
          .then(res => (res.ok ? res.json() : null))
          .then(data => {
            if (data) {
              setTunnelInfo({ active: Boolean(data.active), public_url: data.public_url || '' });
            }
          })
          .catch(() => null);

        const fetchPipe = async (pipe: (typeof PIPELINES)[number]) => {
          try {
            const res = await fetch(`${pipe.countsEndpoint}?refresh=${refresh ? 'true' : 'false'}`);
            if (!res.ok) return null;
            const data = await res.json();
            return { pipe, data };
          } catch {
            return null;
          }
        };

        // Chunk pipelines into batches of 5 to respect Airtable's 5 req/s limit
        // and avoid saturating server worker threads
        const chunkSize = 5;
        const results: Array<{ pipe: (typeof PIPELINES)[number]; data: any } | null> = [];
        for (let i = 0; i < PIPELINES.length; i += chunkSize) {
          const chunk = PIPELINES.slice(i, i + chunkSize);
          const chunkResults = await Promise.all(chunk.map(fetchPipe));
          results.push(...chunkResults);
          if (i + chunkSize < PIPELINES.length) {
            await new Promise(r => setTimeout(r, 150));
          }
        }

        await tunnelPromise;

        const newProgress: Record<string, number> = {};
        const newMbOverrides: Record<string, Record<string, string>> = {};
        const newPrOverrides: Record<string, Record<string, string>> = {};
        const newStatusCounts: Record<string, StatusCountMap> = {};
        const newTableOverrides: Record<string, Record<string, string>> = {};

        results.forEach(result => {
          if (!result || !result.data?.counts) return;
          const { pipe, data } = result;
          const pipeType = pipe.type;

          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: StatusCountMap = {};
          const tblUpdates: Record<string, string> = {};

          Object.entries(data.counts).forEach(([fixtureId, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') {
              newProgress[`${pipe.format}-${pipe.subtabIndex}-${fixtureId}`] = fix.status_counts.C;
            }
            if (fix.moodboard_id) mbUpdates[fixtureId] = fix.moodboard_id;
            if (fix.prompt) prUpdates[fixtureId] = fix.prompt;
            if (fix.status_counts) statusUpdates[fixtureId] = fix.status_counts;
            if (fix.table_id) tblUpdates[fixtureId] = fix.table_id;
          });

          if (Object.keys(mbUpdates).length > 0) newMbOverrides[pipeType] = mbUpdates;
          if (Object.keys(prUpdates).length > 0) newPrOverrides[pipeType] = prUpdates;
          if (Object.keys(statusUpdates).length > 0) newStatusCounts[pipeType] = statusUpdates;
          if (Object.keys(tblUpdates).length > 0) newTableOverrides[pipeType] = tblUpdates;
        });

        if (Object.keys(newProgress).length > 0) {
          setProgressState(prev => ({ ...prev, ...newProgress }));
        }
        if (Object.keys(newMbOverrides).length > 0) {
          setMoodboardOverrides(prev => {
            const next = { ...prev };
            Object.entries(newMbOverrides).forEach(([pType, mbs]) => {
              next[pType] = { ...(next[pType] || {}), ...mbs };
            });
            return next;
          });
        }
        if (Object.keys(newPrOverrides).length > 0) {
          setPromptOverrides(prev => {
            const next = { ...prev };
            Object.entries(newPrOverrides).forEach(([pType, prs]) => {
              next[pType] = { ...(next[pType] || {}), ...prs };
            });
            return next;
          });
        }
        if (Object.keys(newStatusCounts).length > 0) {
          setStatusCounts(prev => {
            const next = { ...prev };
            Object.entries(newStatusCounts).forEach(([pType, scs]) => {
              next[pType] = { ...(next[pType] || {}), ...scs };
            });
            return next;
          });
        }
        if (Object.keys(newTableOverrides).length > 0) {
          setTableIdOverrides(prev => {
            const next = { ...prev };
            Object.entries(newTableOverrides).forEach(([pType, tbls]) => {
              next[pType] = { ...(next[pType] || {}), ...tbls };
            });
            return next;
          });
        }

        if (showToast) {
          toast.success('Airtable completion counts refreshed');
        }
      } catch (err) {
        console.warn('Failed to fetch counts:', err);
      } finally {
        setIsLoadingCounts(false);
      }
    },
    []
  );

  return {
    progressState,
    setProgressState,
    moodboardOverrides,
    promptOverrides,
    statusCounts,
    tableIdOverrides,
    isLoadingCounts,
    tunnelInfo,
    setTunnelInfo,
    getMoodboard,
    getPrompt,
    getStatusCounts,
    getTableId,
    updateMoodboard,
    updatePrompt,
    fetchLiveCounts,
  };
}
