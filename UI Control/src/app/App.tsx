import { useState, useEffect, useMemo, useCallback } from 'react';
import { toast } from 'sonner';
import { Toaster } from './components/ui/sonner';
import { ThemeToggle } from './components/ThemeToggle';
import { RefreshCw, Key, Globe, Check } from 'lucide-react';
import { FormatTabs, TabType } from './components/planning/FormatTabs';
import { SubTabRail } from './components/planning/SubTabRail';
import { FixtureProgressGrid } from './components/planning/FixtureProgressGrid';
import { FixtureData } from './components/planning/FixtureCard';
import { RunConfirmModal } from './components/planning/RunConfirmModal';
import { RowInspectorModal } from './components/planning/RowInspectorModal';
import { RunCenter } from './components/planning/RunCenter';
import { EditMoodboardModal, EditPromptModal, StudioPinModal } from './components/modals';
import { CONTENT_CONFIG, getFixturesForSubtab } from './constants/fixtures';
import { getPipelineConfig, getPipelineByType, getPipelineHeaderTitle } from './constants/pipelines';
import { usePipelineData, useQueue, usePipelineRunner } from './hooks';
import type { FinishedQueueJob } from './hooks/useQueue';
import type { PipelineType, QueueJob, QueueHistoryItem } from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('story');
  const [activeSubTab, setActiveSubTab] = useState<number>(0);

  // Studio PIN management
  const [studioPin, setStudioPin] = useState<string>(() => localStorage.getItem('hc_studio_pin') || '');
  const [showPinModal, setShowPinModal] = useState<boolean>(false);
  const [pinInput, setPinInput] = useState<string>('');

  // Row Inspector Modal state
  const [inspectFixture, setInspectFixture] = useState<FixtureData | null>(null);
  const [inspectStatusFilter, setInspectStatusFilter] = useState<string>('all');

  // Direct Edit Moodboard / Prompt Modal states
  const [editMoodboardFixture, setEditMoodboardFixture] = useState<FixtureData | null>(null);
  const [editMoodboardInput, setEditMoodboardInput] = useState<string>('');
  const [isSavingMoodboard, setIsSavingMoodboard] = useState<boolean>(false);

  const [editPromptFixture, setEditPromptFixture] = useState<FixtureData | null>(null);
  const [editPromptInput, setEditPromptInput] = useState<string>('');
  const [isSavingPrompt, setIsSavingPrompt] = useState<boolean>(false);

  // 1. Data hook: Consolidated moodboards, prompts, status counts & live sync
  const {
    progressState,
    setProgressState,
    isLoadingCounts,
    tunnelInfo,
    getMoodboard,
    getPrompt,
    getStatusCounts,
    getTableId,
    updateMoodboard,
    updatePrompt,
    fetchLiveCounts,
  } = usePipelineData();

  // Initial fetch on mount
  useEffect(() => {
    fetchLiveCounts();
  }, [fetchLiveCounts]);

  // 2. Runner hook: enqueue / stop controls (status comes from the queue poller below)
  const handleRequirePin = useCallback(() => setShowPinModal(true), []);

  const {
    pipelineState,
    setPipelineState,
    runningPipelineType,
    setRunningPipelineType,
    confirmModalFixture,
    setConfirmModalFixture,
    isStartingRun,
    handleOpenRunModal: runnerOpenRunModal,
    handleConfirmRun: runnerConfirmRun,
    handleStopPipeline,
  } = usePipelineRunner({
    studioPin,
    onRequirePin: handleRequirePin,
  });

  // Called once when a queued job finishes (completed / error / stopped)
  const handleRunFinished = useCallback(
    (job: QueueJob, history?: QueueHistoryItem) => {
      const outcome = history?.status ?? 'completed';
      if (outcome === 'error') {
        toast.error(`Pipeline encountered an error: ${history?.error || 'Check console logs'}`);
      } else if (outcome === 'completed' || outcome === 'success' || outcome === 'done') {
        setProgressState(prev => {
          const key = `${job.format_tab}-${job.subtab_index}-${job.fixture_id}`;
          return { ...prev, [key]: (prev[key] ?? 0) + 1 };
        });
        toast.success(
          `${job.pipeline_name || 'Pipeline'} pipeline finished for ${job.fixture_id}! Refreshing Airtable counts.`,
          { duration: 5000 }
        );
      }
      // Re-sync with Airtable to ensure exact consistency
      setTimeout(() => fetchLiveCounts(), 2000);
    },
    [fetchLiveCounts, setProgressState]
  );

  // Safety net: UI says "running" but the server queue has been empty for several polls
  const handleQueueLost = useCallback(() => {
    setPipelineState(prev => {
      if (prev.status !== 'running') return prev;
      toast.warning('The server no longer has this run (restart or lost job). Check Airtable, then run again if needed.');
      return { ...prev, status: 'idle', logs: [...prev.logs, '[STUDIO] Run no longer tracked by the server queue.'] };
    });
    setRunningPipelineType(null);
  }, [setPipelineState, setRunningPipelineType]);

  // 3. Queue hook: FIFO queue management and live transition sync
  const handleQueueJobTransition = useCallback(
    (activeJob: QueueJob | null, wasActive: boolean, finished?: FinishedQueueJob) => {
      if (finished) {
        handleRunFinished(finished.job, finished.history);
      }

      if (activeJob) {
        setRunningPipelineType(activeJob.pipeline_type as PipelineType);
        setPipelineState(prev => {
          const logs = (activeJob as QueueJob & { logs?: string[] }).logs || [];
          const next = {
            status: 'running' as const,
            active_fixture: activeJob.fixture_id,
            active_table_id: activeJob.table_id,
            current_phase: activeJob.current_phase || 'Processing...',
            current_phase_index: activeJob.current_phase_index || 0,
            total_phases: activeJob.total_phases || 5,
            elapsed_seconds: activeJob.elapsed_seconds || 0,
            logs,
            error: activeJob.error || null,
          };
          const unchanged =
            prev.status === next.status &&
            prev.active_fixture === next.active_fixture &&
            prev.current_phase === next.current_phase &&
            prev.current_phase_index === next.current_phase_index &&
            prev.total_phases === next.total_phases &&
            prev.elapsed_seconds === next.elapsed_seconds &&
            (prev.error ?? null) === next.error &&
            prev.logs.length === logs.length &&
            prev.logs[prev.logs.length - 1] === logs[logs.length - 1];
          return unchanged ? prev : next;
        });
      } else if (wasActive) {
        setRunningPipelineType(null);
        const outcome = finished?.history?.status;
        setPipelineState(prev => ({
          ...prev,
          status: outcome === 'error' ? 'error' : outcome === 'stopped' ? 'stopped' : 'completed',
          error: outcome === 'error' ? finished?.history?.error || prev.error || 'Pipeline failed' : prev.error,
        }));
      }
    },
    [handleRunFinished, setPipelineState, setRunningPipelineType]
  );

  const {
    activeQueueJob,
    pendingQueue,
    queueHistory,
    getQueueInfo,
    handleCancelQueueFixture,
    handleCancelQueueItem,
    handleClearQueue,
    handleStopActiveJob,
  } = useQueue(handleQueueJobTransition, handleQueueLost);

  // Active configurations
  const activePipelineConfig = useMemo(
    () => getPipelineConfig(activeTab, activeSubTab),
    [activeTab, activeSubTab]
  );
  const activePipelineType = activePipelineConfig?.type ?? null;
  const isAdCoverActive = activeTab === 'adcover';
  const isInteractivePipelineActive = true;
  const activeFormat = CONTENT_CONFIG[activeTab];

  // Running Pipeline metadata
  const runningPipelineConfig = useMemo(
    () => getPipelineByType(runningPipelineType),
    [runningPipelineType]
  );
  const runningTab = runningPipelineConfig?.format || null;
  const runningSubTab = runningPipelineConfig?.subtabIndex ?? null;
  const isCurrentTabPipelineRunning =
    pipelineState.status === 'running' &&
    runningPipelineType !== null &&
    runningPipelineConfig?.format === activeTab &&
    runningPipelineConfig?.subtabIndex === activeSubTab;

  const activeRunningFixtureId = isCurrentTabPipelineRunning ? pipelineState.active_fixture : null;

  // Build current fixtures with live counts, moodboard, and prompt overrides
  const baseFixtures = useMemo(
    () => getFixturesForSubtab(activeTab, activeSubTab),
    [activeTab, activeSubTab]
  );

  const currentFixtures: FixtureData[] = useMemo(() => {
    return baseFixtures.map(base => {
      const key = `${activeTab}-${activeSubTab}-${base.id}`;
      const dynMoodboard = getMoodboard(activePipelineType, base.id) || base.moodboardId;
      const dynPrompt = getPrompt(activePipelineType, base.id) ?? base.prompt;
      const dynTableId = getTableId(activePipelineType, base.id) || base.tableId;

      return {
        ...base,
        tableId: dynTableId,
        moodboardId: dynMoodboard,
        prompt: dynPrompt,
        completed: progressState[key] ?? null,
        statusCounts: getStatusCounts(activePipelineType, base.id),
      };
    });
  }, [
    baseFixtures,
    activeTab,
    activeSubTab,
    activePipelineType,
    getMoodboard,
    getPrompt,
    getTableId,
    getStatusCounts,
    progressState,
  ]);

  // Computed subtab live totals
  const activeSubtabHasCounts = currentFixtures.every(f => f.completed !== null);
  const activeSubtabCompleted = activeSubtabHasCounts
    ? currentFixtures.reduce((acc, f) => acc + (f.completed ?? 0), 0)
    : null;
  const activeSubtabTotal = currentFixtures.reduce((acc, f) => acc + (f.total ?? 100), 0);
  const activeSubtabPercentage =
    activeSubtabCompleted !== null && activeSubtabTotal > 0
      ? Math.round((activeSubtabCompleted / activeSubtabTotal) * 100)
      : null;

  // Aggregated 5-badge status rollup across all fixtures in active subtab
  const aggregatedStatusCounts = useMemo(() => {
    return currentFixtures.reduce(
      (acc, f) => {
        if (f.statusCounts) {
          acc.P += f.statusCounts.P || 0;
          acc.S += f.statusCounts.S || 0;
          acc.C += f.statusCounts.C || 0;
          acc.D += f.statusCounts.D || 0;
          acc.FM += f.statusCounts.FM || 0;
          acc.hasCounts = true;
        }
        return acc;
      },
      { P: 0, S: 0, C: 0, D: 0, FM: 0, hasCounts: false }
    );
  }, [currentFixtures]);

  // Subtab count rollup for rail badges
  const activeFormatSubtabCounts = useMemo(() => {
    return (CONTENT_CONFIG[activeTab]?.items || []).map((_, subtabIdx) => {
      const fixtures = getFixturesForSubtab(activeTab, subtabIdx);
      const hasAllCounts = fixtures.every(f => {
        const key = `${activeTab}-${subtabIdx}-${f.id}`;
        return typeof progressState[key] === 'number';
      });
      if (!hasAllCounts) return null;
      return fixtures.reduce((acc, f) => {
        const key = `${activeTab}-${subtabIdx}-${f.id}`;
        return acc + (progressState[key] ?? 0);
      }, 0);
    });
  }, [activeTab, progressState]);

  // Tab count rollups for format tabs (Feed / Story / Reel / Ad Covers)
  const tabCounts = useMemo(() => {
    const calcTab = (tab: TabType) => {
      const items = CONTENT_CONFIG[tab]?.items || [];
      let totalCompleted = 0;
      let totalTarget = 0;
      let hasAny = false;
      items.forEach((_, subtabIdx) => {
        const fixtures = getFixturesForSubtab(tab, subtabIdx);
        fixtures.forEach(f => {
          const key = `${tab}-${subtabIdx}-${f.id}`;
          if (typeof progressState[key] === 'number') {
            totalCompleted += progressState[key];
            hasAny = true;
          }
          totalTarget += f.total ?? 100;
        });
      });
      return {
        completed: hasAny ? totalCompleted : null,
        total: totalTarget,
      };
    };

    return {
      feed: calcTab('feed'),
      story: calcTab('story'),
      reel: calcTab('reel'),
      adcover: calcTab('adcover'),
      banner: calcTab('banner'),
    };
  }, [progressState]);

  // Modal Handlers
  const handleOpenRowInspector = (fixture: FixtureData, statusFilter = 'all') => {
    setInspectFixture(fixture);
    setInspectStatusFilter(statusFilter);
  };

  const handleOpenRunModal = (fixture: FixtureData) => {
    const dynMoodboard = getMoodboard(activePipelineType, fixture.id) || fixture.moodboardId;
    const dynPrompt = getPrompt(activePipelineType, fixture.id) ?? fixture.prompt;
    runnerOpenRunModal(fixture, dynMoodboard, dynPrompt);
  };

  const handleConfirmRun = async (
    customMoodboardId?: string,
    customPrompt?: string,
    maxItems = 1
  ) => {
    if (confirmModalFixture && activePipelineType) {
      if (customMoodboardId) updateMoodboard(activePipelineType, confirmModalFixture.id, customMoodboardId);
      if (customPrompt) updatePrompt(activePipelineType, confirmModalFixture.id, customPrompt);
    }
    await runnerConfirmRun(activeTab, activeSubTab, customMoodboardId, customPrompt, maxItems);
  };

  const handleOpenEditMoodboard = (fixture: FixtureData) => {
    const currentMb = getMoodboard(activePipelineType, fixture.id) || fixture.moodboardId || '';
    setEditMoodboardFixture(fixture);
    setEditMoodboardInput(currentMb);
  };

  const handleSaveMoodboard = async () => {
    if (!editMoodboardFixture || !activePipelineConfig?.moodboardEndpoint) return;
    setIsSavingMoodboard(true);
    const newMb = editMoodboardInput.trim();
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';

    try {
      const res = await fetch(activePipelineConfig.moodboardEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({
          fixture_id: editMoodboardFixture.id,
          moodboard_id: newMb,
          pin,
        }),
      });
      const data = await res.json();
      if (res.status === 401 || data.needs_pin) {
        setShowPinModal(true);
        toast.error('Studio PIN required to update Moodboard ID');
        return;
      }
      if (res.ok) {
        updateMoodboard(activePipelineConfig.type, editMoodboardFixture.id, newMb);
        toast.success(`Updated Krea Moodboard ID for ${editMoodboardFixture.name} in .env`);
        setEditMoodboardFixture(null);
      } else {
        toast.error(data.error || 'Failed to update Moodboard ID');
      }
    } catch (err) {
      toast.error(`Error saving moodboard: ${err}`);
    } finally {
      setIsSavingMoodboard(false);
    }
  };

  const handleOpenEditPrompt = (fixture: FixtureData) => {
    const currentPr = getPrompt(activePipelineType, fixture.id) ?? fixture.prompt ?? '';
    setEditPromptFixture(fixture);
    setEditPromptInput(currentPr);
  };

  const handleSavePrompt = async () => {
    if (!editPromptFixture || !activePipelineConfig?.promptEndpoint) return;
    setIsSavingPrompt(true);
    const newPr = editPromptInput.trim();
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';

    try {
      const res = await fetch(activePipelineConfig.promptEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { Authorization: `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({
          fixture_id: editPromptFixture.id,
          prompt: newPr,
          pin,
        }),
      });
      const data = await res.json();
      if (res.status === 401 || data.needs_pin) {
        setShowPinModal(true);
        toast.error('Studio PIN required to update Prompt');
        return;
      }
      if (res.ok) {
        updatePrompt(activePipelineConfig.type, editPromptFixture.id, newPr);
        toast.success(`Updated Krea Prompt for ${editPromptFixture.name} in .env`);
        setEditPromptFixture(null);
      } else {
        toast.error(data.error || 'Failed to update Prompt');
      }
    } catch (err) {
      toast.error(`Error saving prompt: ${err}`);
    } finally {
      setIsSavingPrompt(false);
    }
  };

  const isMoodboardEditable = Boolean(activePipelineConfig?.hasMoodboard);
  const isPromptEditable = Boolean(activePipelineConfig?.hasPrompt);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between">
      <Toaster position="top-right" richColors />

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex-1">
        {/* Top Header & Branding */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-gray-200">
          <div />

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <button
              type="button"
              onClick={() => fetchLiveCounts(true, true)}
              disabled={isLoadingCounts || pipelineState.status === 'running'}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-card border border-slate-300 rounded-lg hover:bg-slate-50 active:bg-slate-100 transition shadow-xs disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingCounts ? 'animate-spin text-sky-600' : ''}`} />
              <span>Sync Airtable</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setPinInput(studioPin);
                setShowPinModal(true);
              }}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition shadow-xs cursor-pointer ${
                studioPin
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300 hover:bg-emerald-100'
                  : 'bg-card text-slate-700 border-slate-300 hover:bg-slate-50'
              }`}
            >
              <Key className="w-3.5 h-3.5" />
              <span>{studioPin ? 'PIN Active' : 'Set PIN'}</span>
            </button>
            {tunnelInfo.active && (
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(tunnelInfo.public_url);
                  toast.success('Cloudflare public link copied to clipboard!');
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-300 rounded-lg transition shadow-xs cursor-pointer"
              >
                <Globe className="w-3.5 h-3.5 text-amber-600" />
                <span>Public Live</span>
              </button>
            )}
          </div>
        </div>

        {/* Format Selector Tabs (Feed / Story / Reel / Ad Covers) */}
        <FormatTabs
          activeTab={activeTab}
          counts={tabCounts}
          onSelectTab={tab => {
            setActiveTab(tab);
            setActiveSubTab(0);
          }}
          runningTab={runningTab}
        />

        {/* Minimalist Sub-Tab Rail */}
        {!isAdCoverActive && (
          <SubTabRail
            activeTab={activeTab}
            items={activeFormat.items}
            activeSubTab={activeSubTab}
            onSelectSubTab={idx => setActiveSubTab(idx)}
            runningSubTab={activeTab === runningTab ? runningSubTab : null}
            counts={activeFormatSubtabCounts}
          />
        )}

        {/* Section Header with Subtle Inline Refresh & 5-Badge Rollup */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-6 mb-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-sm font-semibold text-gray-800">
              {getPipelineHeaderTitle(activeTab, activeSubTab)}
            </h2>

            {/* Subtab Live Completed Progress Badge Pill */}
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs"
              title={
                activeSubtabCompleted === null
                  ? 'Airtable completed counts are loading'
                  : `${activeSubtabCompleted} completed records out of ${activeSubtabTotal} target capacity`
              }
            >
              <Check className="w-3 h-3 text-emerald-600" />
              <span>
                {activeSubtabCompleted === null
                  ? '— Completed'
                  : `${activeSubtabCompleted} / ${activeSubtabTotal} Completed`}
              </span>
              {activeSubtabPercentage !== null && (
                <span className="text-emerald-600/70 font-normal">({activeSubtabPercentage}%)</span>
              )}
            </span>

            {/* Aggregated 5-Badge Status Rollup (P, S, C, D, FM) */}
            {aggregatedStatusCounts.hasCounts && (
              <div className="flex items-center gap-1">
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200/80 shadow-2xs"
                  title={`Total Posted / Processing: ${aggregatedStatusCounts.P}`}
                >
                  <span className="font-bold text-sky-800">P:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.P}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200/80 shadow-2xs"
                  title={`Total Scheduled: ${aggregatedStatusCounts.S}`}
                >
                  <span className="font-bold text-purple-800">S:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.S}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs"
                  title={`Total Completed: ${aggregatedStatusCounts.C}`}
                >
                  <span className="font-bold text-emerald-800">C:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.C}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200/80 shadow-2xs"
                  title={`Total Discarded: ${aggregatedStatusCounts.D}`}
                >
                  <span className="font-bold text-rose-800">D:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.D}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200/80 shadow-2xs"
                  title={`Total For Manual / Revision: ${aggregatedStatusCounts.FM}`}
                >
                  <span className="font-bold text-amber-800">FM:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.FM}</span>
                </span>
              </div>
            )}
          </div>
          <span className="text-[11px] text-gray-400 font-medium hidden sm:inline">
            Auto-synced on completion
          </span>
        </div>

        {/* Pipeline Error Alert Banner */}
        {pipelineState.status === 'error' && pipelineState.error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center justify-between text-xs text-rose-900 shadow-xs animate-in fade-in duration-150">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0"></span>
              <div>
                <span className="font-semibold">Pipeline Error: </span>
                <span className="text-rose-800">{pipelineState.error}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setPipelineState(prev => ({ ...prev, status: 'idle', error: undefined }))}
              className="px-2.5 py-1 bg-rose-200/60 hover:bg-rose-200 text-rose-900 rounded-lg font-medium transition-all text-[11px] cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Lighting Fixtures Progress Grid */}
        <FixtureProgressGrid
          fixtures={currentFixtures}
          activeTab={activeTab}
          activeRunningFixtureId={
            activeQueueJob && activeQueueJob.pipeline_type === activePipelineType
              ? activeQueueJob.fixture_id
              : activeRunningFixtureId
          }
          currentPhase={
            activeQueueJob && activeQueueJob.pipeline_type === activePipelineType
              ? activeQueueJob.current_phase
              : isCurrentTabPipelineRunning
              ? pipelineState.current_phase
              : undefined
          }
          onRunFixture={isInteractivePipelineActive ? handleOpenRunModal : undefined}
          onStopFixture={() => handleStopActiveJob(studioPin, handleStopPipeline)}
          onCancelQueueFixture={f => handleCancelQueueFixture(f, studioPin)}
          getQueueInfo={fId => getQueueInfo(fId, activePipelineType)}
          isAnyPipelineRunning={!!activeQueueJob || pipelineState.status === 'running'}
          canRun={true}
          onEditMoodboard={isMoodboardEditable ? handleOpenEditMoodboard : undefined}
          onEditPrompt={isPromptEditable ? handleOpenEditPrompt : undefined}
          onViewRows={handleOpenRowInspector}
          hideProgressBar={activePipelineType === 'cta' || activePipelineType === 'tips-edu'}
        />
      </div>

      {/* Confirmation Modal */}
      <RunConfirmModal
        fixture={confirmModalFixture}
        pipelineTitle={activePipelineConfig ? `Run ${activePipelineConfig.name} Pipeline` : 'Run Pipeline'}
        totalPhases={activePipelineConfig?.totalPhases ?? 5}
        phaseSummary={activePipelineConfig?.phaseSummary}
        onConfirm={handleConfirmRun}
        onClose={() => setConfirmModalFixture(null)}
        isLoading={isStartingRun}
      />

      {/* Airtable Row Inspector Modal */}
      <RowInspectorModal
        fixture={inspectFixture}
        initialStatusFilter={inspectStatusFilter}
        onClose={() => setInspectFixture(null)}
        baseId="appDM0jUDsaiThtR3"
      />

      {/* Edit Krea Moodboard Modal */}
      <EditMoodboardModal
        fixture={editMoodboardFixture}
        pipelineName={activePipelineConfig?.name}
        moodboardInput={editMoodboardInput}
        onInputChange={setEditMoodboardInput}
        onSave={handleSaveMoodboard}
        onClose={() => setEditMoodboardFixture(null)}
        isSaving={isSavingMoodboard}
      />

      {/* Edit Krea Prompt Modal */}
      <EditPromptModal
        fixture={editPromptFixture}
        pipelineName={activePipelineConfig?.name}
        promptInput={editPromptInput}
        onInputChange={setEditPromptInput}
        onSave={handleSavePrompt}
        onClose={() => setEditPromptFixture(null)}
        isSaving={isSavingPrompt}
      />

      {/* Studio PIN Configuration Modal */}
      <StudioPinModal
        isOpen={showPinModal}
        studioPin={studioPin}
        pinInput={pinInput}
        onPinInputChange={setPinInput}
        onSavePin={() => {
          localStorage.setItem('hc_studio_pin', pinInput.trim());
          setStudioPin(pinInput.trim());
          setShowPinModal(false);
          toast.success(pinInput.trim() ? 'Studio PIN configured' : 'Studio PIN cleared');
        }}
        onClearPin={() => {
          localStorage.removeItem('hc_studio_pin');
          setStudioPin('');
          setPinInput('');
          setShowPinModal(false);
          toast.info('Studio PIN cleared');
        }}
        onClose={() => setShowPinModal(false)}
      />

      {/* Run Center: bottom status bar + right-hand panel (running job, queue, history) */}
      <RunCenter
        activeJob={activeQueueJob}
        pendingQueue={pendingQueue}
        history={queueHistory}
        pipelineState={pipelineState}
        phaseSummary={(activeQueueJob ? getPipelineByType(activeQueueJob.pipeline_type as PipelineType) : runningPipelineConfig)?.phaseSummary}
        onStop={() => handleStopActiveJob(studioPin, handleStopPipeline)}
        onCancelJob={(jobId, fixName) => handleCancelQueueItem(jobId, fixName, studioPin)}
        onClearQueue={() => handleClearQueue(studioPin)}
        onJumpToJob={(format, subtabIdx) => {
          setActiveTab(format as TabType);
          setActiveSubTab(subtabIdx);
        }}
        onDismissError={() => setPipelineState(prev => ({ ...prev, status: 'idle', error: undefined }))}
      />
    </div>
  );
}
