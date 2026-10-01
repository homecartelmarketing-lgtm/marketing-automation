import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { PipelineExecutionState, PipelineType, TabType } from '../types';
import { FixtureData } from '../components/planning/FixtureCard';
import { getPipelineByType, getPipelineConfig } from '../constants/pipelines';

export interface UsePipelineRunnerParams {
  studioPin: string;
  onRequirePin: () => void;
}

export interface UsePipelineRunnerResult {
  pipelineState: PipelineExecutionState;
  setPipelineState: React.Dispatch<React.SetStateAction<PipelineExecutionState>>;
  runningPipelineType: PipelineType;
  setRunningPipelineType: React.Dispatch<React.SetStateAction<PipelineType>>;
  confirmModalFixture: FixtureData | null;
  setConfirmModalFixture: React.Dispatch<React.SetStateAction<FixtureData | null>>;
  isStartingRun: boolean;
  handleOpenRunModal: (fixture: FixtureData, moodboardId?: string, prompt?: string) => void;
  handleConfirmRun: (
    activeTab: TabType,
    activeSubTab: number,
    customMoodboardId?: string,
    customPrompt?: string,
    maxItems?: number
  ) => Promise<void>;
  handleStopPipeline: () => Promise<void>;
}

export function usePipelineRunner({
  studioPin,
  onRequirePin,
}: UsePipelineRunnerParams): UsePipelineRunnerResult {
  const [pipelineState, setPipelineState] = useState<PipelineExecutionState>({
    status: 'idle',
    active_fixture: null,
    active_table_id: null,
    current_phase: '',
    current_phase_index: 0,
    total_phases: 6,
    elapsed_seconds: 0,
    logs: [],
  });

  const [runningPipelineType, setRunningPipelineType] = useState<PipelineType>(null);
  const [confirmModalFixture, setConfirmModalFixture] = useState<FixtureData | null>(null);
  const [isStartingRun, setIsStartingRun] = useState<boolean>(false);

  // NOTE: run status, logs, errors and completion are driven solely by the queue
  // poller (useQueue -> App.handleQueueJobTransition). A second poller on the
  // pipeline's own status endpoint used to fight it and caused flicker.

  const handleOpenRunModal = useCallback((fixture: FixtureData, moodboardId?: string, prompt?: string) => {
    setConfirmModalFixture({
      ...fixture,
      moodboardId: moodboardId || fixture.moodboardId,
      prompt: prompt !== undefined ? prompt : fixture.prompt,
    });
  }, []);

  const handleConfirmRun = useCallback(
    async (
      activeTab: TabType,
      activeSubTab: number,
      customMoodboardId?: string,
      customPrompt?: string,
      maxItems = 1
    ) => {
      if (!confirmModalFixture) return;
      const config = getPipelineConfig(activeTab, activeSubTab);
      if (!config) return;

      setIsStartingRun(true);
      const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
      try {
        const res = await fetch('/api/queue/enqueue', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
          },
          body: JSON.stringify({
            pipeline_type: config.type,
            pipeline_name: config.name,
            fixture_id: confirmModalFixture.id,
            fixture_name: confirmModalFixture.name,
            format_tab: activeTab,
            subtab_index: activeSubTab,
            table_id: confirmModalFixture.tableId ?? '',
            moodboard_id: customMoodboardId,
            prompt: customPrompt,
            max_items: maxItems,
            run_endpoint: config.runEndpoint,
            status_endpoint: config.statusEndpoint,
            stop_endpoint: config.stopEndpoint,
            pin: pin,
          }),
        });

        let data: any = {};
        const ct = res.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          data = await res.json();
        } else {
          const rawText = await res.text();
          throw new Error(
            `Server returned HTTP ${res.status}: ${rawText.slice(0, 100).replace(/<[^>]*>/g, '').trim()}`
          );
        }

        if (res.status === 401 || data.needs_pin) {
          onRequirePin();
          toast.error('Studio PIN required to trigger pipeline');
          return;
        }

        if (res.ok) {
          if (data.status === 'queued') {
            toast.success(`Added ${confirmModalFixture.name} to Generation Queue (#${data.queue_position} in line)`);
          } else {
            toast.info(`Started ${config.name} pipeline for ${confirmModalFixture.name} (${maxItems} item${maxItems > 1 ? 's' : ''})`);
            setRunningPipelineType(config.type);
            setPipelineState({
              status: 'running',
              active_fixture: confirmModalFixture.id,
              active_table_id: confirmModalFixture.tableId ?? null,
              current_phase: `Phase 1/${config.totalPhases}: Initializing Pipeline...`,
              current_phase_index: 0,
              total_phases: config.totalPhases,
              elapsed_seconds: 0,
              logs: [`[STUDIO] Dispatching ${config.name} for ${confirmModalFixture.name}...`],
            });
          }
          setConfirmModalFixture(null);
        } else {
          toast.error(data.error || 'Failed to trigger pipeline');
        }
      } catch (err: any) {
        toast.error(`Execution error: ${err.message || err}`);
      } finally {
        setIsStartingRun(false);
      }
    },
    [confirmModalFixture, studioPin, onRequirePin]
  );

  const handleStopPipeline = useCallback(async () => {
    const config = getPipelineByType(runningPipelineType);
    const stopEndpoint = config?.stopEndpoint || '/api/cta/stop';
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';

    try {
      const res = await fetch(stopEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ pin }),
      });
      if (res.ok) {
        toast.warning('Pipeline execution stopped by user');
        setRunningPipelineType(null);
        setPipelineState(prev => ({
          ...prev,
          status: 'stopped',
          logs: [...prev.logs, '[USER] Pipeline stopped by user.'],
        }));
      } else if (res.status === 401) {
        onRequirePin();
        toast.error('Invalid PIN to stop pipeline');
      }
    } catch {
      toast.error('Failed to stop pipeline');
    }
  }, [runningPipelineType, studioPin, onRequirePin]);

  return {
    pipelineState,
    setPipelineState,
    runningPipelineType,
    setRunningPipelineType,
    confirmModalFixture,
    setConfirmModalFixture,
    isStartingRun,
    handleOpenRunModal,
    handleConfirmRun,
    handleStopPipeline,
  };
}
