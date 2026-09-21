import { Check, Play, Loader2, Square, Pencil, Table, Clock, X, Plus } from 'lucide-react';
import { TabType } from './FormatTabs';

export interface FixtureData {
  id: string;
  name: string;
  completed: number | null;
  total: number;
  tableId?: string;
  moodboardId?: string;
  prompt?: string;
  statusCounts?: {
    P: number;
    S?: number;
    C: number;
    D: number;
    FM: number;
  };
}

interface FixtureCardProps {
  fixture: FixtureData;
  activeTab?: TabType;
  isRunning?: boolean;
  isQueued?: boolean;
  queuePosition?: number;
  currentPhase?: string;
  onRun?: (fixture: FixtureData) => void;
  onStop?: (fixture: FixtureData) => void;
  onCancelQueue?: (fixture: FixtureData) => void;
  onEditMoodboard?: (fixture: FixtureData) => void;
  onEditPrompt?: (fixture: FixtureData) => void;
  onViewRows?: (fixture: FixtureData, statusFilter?: string) => void;
  canRun?: boolean;
  isAnyPipelineRunning?: boolean;
  hideProgressBar?: boolean;
}

export function FixtureCard({
  fixture,
  activeTab = 'feed',
  isRunning = false,
  isQueued = false,
  queuePosition = 1,
  currentPhase,
  onRun,
  onStop,
  onCancelQueue,
  onEditMoodboard,
  onEditPrompt,
  onViewRows,
  canRun = true,
  isAnyPipelineRunning = false,
  hideProgressBar = false,
}: FixtureCardProps) {
  const percentage = fixture.completed === null ? 0 : Math.round((fixture.completed / fixture.total) * 100);
  const isComplete = fixture.completed === fixture.total;

  const getThemeClasses = () => {
    switch (activeTab) {
      case 'feed':
        return {
          pill: 'bg-emerald-50 text-emerald-700 border-emerald-200',
          bar: 'bg-emerald-500',
          btn: 'text-emerald-700 bg-emerald-50 hover:bg-emerald-100 active:bg-emerald-200 border-emerald-200 shadow-2xs hover:shadow-xs',
        };
      case 'story':
        return {
          pill: 'bg-purple-50 text-purple-700 border-purple-200',
          bar: 'bg-purple-500',
          btn: 'text-purple-700 bg-purple-50 hover:bg-purple-100 active:bg-purple-200 border-purple-200 shadow-2xs hover:shadow-xs',
        };
      case 'reel':
        return {
          pill: 'bg-rose-50 text-rose-700 border-rose-200',
          bar: 'bg-rose-500',
          btn: 'text-rose-700 bg-rose-50 hover:bg-rose-100 active:bg-rose-200 border-rose-200 shadow-2xs hover:shadow-xs',
        };
      default:
        return {
          pill: 'bg-gray-50 text-gray-700 border-gray-200',
          bar: 'bg-gray-500',
          btn: 'text-gray-700 bg-gray-50 hover:bg-gray-100 active:bg-gray-200 border-gray-200 shadow-2xs hover:shadow-xs',
        };
    }
  };

  const theme = getThemeClasses();

  const getPillBadge = () => {
    if (isRunning) {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200 animate-pulse">
          <Loader2 className="w-3 h-3 animate-spin" />
          <span>Generating</span>
        </span>
      );
    }
    if (isQueued) {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">
          <Clock className="w-3 h-3 text-amber-600" />
          <span>Queued (#{queuePosition})</span>
        </span>
      );
    }
    if (isComplete) {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
          <Check className="w-3 h-3 text-emerald-600" />
          <span>Complete</span>
        </span>
      );
    }
    if (fixture.completed === null) {
      return <span className="text-xs font-medium px-2 py-0.5 rounded-full border border-gray-200 text-gray-500">—</span>;
    }
    return (
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${theme.pill}`}>
        {fixture.completed} / {fixture.total}
      </span>
    );
  };

  return (
    <div
      className={`bg-white rounded-xl border p-4 transition-all duration-200 flex flex-col justify-between ${
        isRunning
          ? 'border-sky-300 ring-2 ring-sky-100 shadow-md'
          : isComplete
          ? 'border-emerald-200 shadow-xs'
          : 'border-gray-200 hover:border-gray-300 shadow-2xs hover:shadow-xs'
      }`}
    >
      <div>
        {/* Top Row: Fixture Name & Status Pill */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex-1 min-w-0">
            <h4 className="font-semibold text-gray-900 text-sm truncate" title={fixture.name}>
              {fixture.name}
            </h4>
            {fixture.tableId && (
              <p className="font-mono text-[11px] text-gray-400 truncate" title={`Airtable: ${fixture.tableId}`}>
                {fixture.tableId}
              </p>
            )}
          </div>
          {getPillBadge()}
        </div>

        {/* Moodboard ID Row (Editable) */}
        {fixture.moodboardId !== undefined && (
          <div className="my-1.5 p-1.5 rounded-md bg-gray-50/80 border border-gray-100 text-[11px] flex items-center justify-between gap-1 group/mb">
            <div className="flex items-center gap-1 min-w-0 flex-1">
              <span className="text-gray-400 shrink-0 font-medium">MB:</span>
              <span
                className="font-mono text-[10px] text-gray-700 truncate"
                title={fixture.moodboardId || 'Not configured'}
              >
                {fixture.moodboardId ? fixture.moodboardId : <span className="text-gray-400 italic">None</span>}
              </span>
            </div>
            {onEditMoodboard && (
              <button
                type="button"
                onClick={() => onEditMoodboard(fixture)}
                className="opacity-60 group-hover/mb:opacity-100 hover:text-purple-600 transition-opacity p-0.5 rounded hover:bg-gray-200/60 shrink-0"
                title="Edit Moodboard ID (.env)"
              >
                <Pencil className="w-3 h-3" />
              </button>
            )}
          </div>
        )}

        {/* Prompt Row (Editable) */}
        {fixture.prompt !== undefined && (
          <div className="my-1.5 p-1.5 rounded-md bg-purple-50/50 border border-purple-100/60 text-[11px] flex items-center justify-between gap-1 group/pr">
            <div className="flex items-center gap-1 min-w-0 flex-1">
              <span className="text-purple-400 shrink-0 font-medium">Prompt:</span>
              <span
                className="text-[10px] text-purple-900 truncate italic"
                title={fixture.prompt || 'Default prompt'}
              >
                {fixture.prompt ? `"${fixture.prompt}"` : <span className="text-gray-400 italic">Default</span>}
              </span>
            </div>
            {onEditPrompt && (
              <button
                type="button"
                onClick={() => onEditPrompt(fixture)}
                className="opacity-60 group-hover/pr:opacity-100 hover:text-purple-600 transition-opacity p-0.5 rounded hover:bg-purple-100/60 shrink-0"
                title="Edit Prompt (.env)"
              >
                <Pencil className="w-3 h-3" />
              </button>
            )}
          </div>
        )}

        {/* Live Running Phase Banner */}
        {isRunning && currentPhase && (
          <div className="my-2 p-2 rounded-lg bg-sky-50/80 border border-sky-100 text-[11px] text-sky-900 font-medium leading-tight flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-ping shrink-0" />
            <span className="truncate">{currentPhase}</span>
          </div>
        )}

        {/* Status Breakdown Badges (P, S, C, D, FM) */}
        {fixture.statusCounts && (
          <div className="mt-2.5 pt-2 border-t border-gray-100 flex flex-wrap items-center gap-1.5">
            {/* P - Posted */}
            <button
              type="button"
              onClick={() => onViewRows?.(fixture, 'p')}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-sky-50 text-sky-700 border border-sky-200/80 hover:bg-sky-100 hover:ring-1 hover:ring-sky-400 transition-all cursor-pointer shadow-2xs"
              title={`P: ${fixture.statusCounts.P} Posted (Click to inspect rows)`}
            >
              <span className="font-bold text-sky-800">P:</span>
              <span className="font-semibold tabular-nums">{fixture.statusCounts.P}</span>
            </button>

            {/* S - Scheduled */}
            <button
              type="button"
              onClick={() => onViewRows?.(fixture, 's')}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200/80 hover:bg-purple-100 hover:ring-1 hover:ring-purple-400 transition-all cursor-pointer shadow-2xs"
              title={`S: ${fixture.statusCounts.S ?? 0} Scheduled (Click to inspect rows)`}
            >
              <span className="font-bold text-purple-800">S:</span>
              <span className="font-semibold tabular-nums">{fixture.statusCounts.S ?? 0}</span>
            </button>

            {/* C - Completed (not posted) */}
            <button
              type="button"
              onClick={() => onViewRows?.(fixture, 'c')}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/80 hover:bg-emerald-100 hover:ring-1 hover:ring-emerald-400 transition-all cursor-pointer shadow-2xs"
              title={`C: ${fixture.statusCounts.C} Completed (Click to inspect rows)`}
            >
              <span className="font-bold text-emerald-800">C:</span>
              <span className="font-semibold tabular-nums">{fixture.statusCounts.C}</span>
            </button>

            {/* D - Discard */}
            <button
              type="button"
              onClick={() => onViewRows?.(fixture, 'd')}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200/80 hover:bg-rose-100 hover:ring-1 hover:ring-rose-400 transition-all cursor-pointer shadow-2xs"
              title={`D: ${fixture.statusCounts.D} Discard (Click to inspect rows)`}
            >
              <span className="font-bold text-rose-800">D:</span>
              <span className="font-semibold tabular-nums">{fixture.statusCounts.D}</span>
            </button>

            {/* FM - Minor revision / For Manual */}
            <button
              type="button"
              onClick={() => onViewRows?.(fixture, 'fm')}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200/80 hover:bg-amber-100 hover:ring-1 hover:ring-amber-400 transition-all cursor-pointer shadow-2xs"
              title={`FM: ${fixture.statusCounts.FM} Minor revision / For Manual (Click to inspect rows)`}
            >
              <span className="font-bold text-amber-800">FM:</span>
              <span className="font-semibold tabular-nums">{fixture.statusCounts.FM}</span>
            </button>
          </div>
        )}

        {/* Ultra-Slim Minimalist Progress Bar */}
        {!hideProgressBar && (fixture.completed !== null || isRunning) && (
          <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden mt-2">
            <div
              className={`h-1.5 rounded-full transition-all duration-500 ${
                isRunning
                  ? 'bg-sky-500 animate-pulse'
                  : isComplete
                  ? 'bg-emerald-500'
                  : theme.bar
              }`}
              style={{ width: `${Math.max(percentage, isRunning ? 15 : 0)}%` }}
            />
          </div>
        )}
      </div>

      {/* Action Footer */}
      {(onRun || isRunning || isQueued) && (
        <div className="pt-2 border-t border-gray-100 flex items-center justify-between gap-2">
          {isRunning ? (
            <>
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-sky-700">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-sky-600" />
                <span>Running...</span>
              </span>

              {onStop && (
                <button
                  type="button"
                  onClick={() => onStop(fixture)}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 active:bg-rose-200 border border-rose-200 shadow-2xs hover:shadow-xs transition-all"
                  title="Stop the current running pipeline"
                >
                  <Square className="w-3 h-3 fill-current text-rose-600" />
                  <span>Stop</span>
                </button>
              )}
            </>
          ) : isQueued ? (
            <>
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full animate-pulse">
                <Clock className="w-3 h-3 text-amber-600" />
                <span>Queued (#{queuePosition})</span>
              </span>

              <div className="flex items-center gap-1.5">
                {onViewRows && (
                  <button
                    type="button"
                    onClick={() => onViewRows(fixture, 'all')}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 hover:text-purple-700 border border-gray-200 transition-all shadow-2xs"
                    title="Inspect rows and view Foreign Key IDs"
                  >
                    <Table className="w-3.5 h-3.5 text-gray-500" />
                    <span>Rows</span>
                  </button>
                )}

                {onCancelQueue && (
                  <button
                    type="button"
                    onClick={() => onCancelQueue(fixture)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition-all shadow-2xs"
                    title="Remove from generation queue"
                  >
                    <X className="w-3 h-3 text-rose-600" />
                    <span>Cancel</span>
                  </button>
                )}
              </div>
            </>
          ) : (
            <>
              {!hideProgressBar ? (
                <span className="text-[11px] text-gray-500 font-medium">
                  {fixture.completed === null ? 'Counts loading' : isComplete ? 'Target Reached' : `${percentage}% done`}
                </span>
              ) : (
                <span className="text-[11px] text-gray-400 font-medium" />
              )}

              <div className="flex items-center gap-1.5">
                {onViewRows && (
                  <button
                    type="button"
                    onClick={() => onViewRows(fixture, 'all')}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 hover:text-purple-700 border border-gray-200 transition-all shadow-2xs"
                    title="Inspect rows and view Foreign Key IDs"
                  >
                    <Table className="w-3.5 h-3.5 text-gray-500" />
                    <span>Rows</span>
                  </button>
                )}

                {onRun && (
                  <button
                    type="button"
                    onClick={() => onRun(fixture)}
                    title={isAnyPipelineRunning ? "Add this fixture to the generation queue" : "Run pipeline for this fixture"}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold border transition-all shadow-2xs hover:shadow-xs ${theme.btn}`}
                  >
                    {isAnyPipelineRunning ? (
                      <>
                        <Plus className="w-3 h-3" />
                        <span>Queue</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3 h-3 fill-current" />
                        <span>Run</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
