import { useState, useEffect } from 'react';
import { AlertCircle, Play, X, Sparkles, Minus, Plus } from 'lucide-react';
import { FixtureData } from './FixtureCard';

interface RunConfirmModalProps {
  fixture: FixtureData | null;
  pipelineTitle?: string;
  totalPhases?: number;
  phaseSummary?: string;
  onConfirm: (customMoodboardId?: string, customPrompt?: string, maxItems?: number) => void;
  onClose: () => void;
  isLoading?: boolean;
}

const PRESET_PILLS = [1, 2, 3, 5, 10];

export function RunConfirmModal({
  fixture,
  pipelineTitle = 'Run Story Pipeline',
  totalPhases = 6,
  phaseSummary = 'Akeneo Scrape ➔ Krea Interior ➔ Claude Prompt ➔ Banana Blend ➔ Headline ➔ Layout Stamping',
  onConfirm,
  onClose,
  isLoading = false,
}: RunConfirmModalProps) {
  if (!fixture) return null;

  const [moodboardInput, setMoodboardInput] = useState<string>(fixture.moodboardId || '');
  const [promptInput, setPromptInput] = useState<string>(fixture.prompt || '');
  const [itemCount, setItemCount] = useState<number>(1);

  useEffect(() => {
    setMoodboardInput(fixture?.moodboardId || '');
    setPromptInput(fixture?.prompt || '');
    setItemCount(1);
  }, [fixture?.moodboardId, fixture?.prompt, fixture?.id]);

  const clampCount = (n: number) => Math.max(1, Math.min(10, n));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl max-w-md w-full p-6 text-gray-900 relative max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          disabled={isLoading}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600">
            <Play className="w-5 h-5 fill-current" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">{pipelineTitle}</h3>
            <p className="text-xs text-gray-500">Trigger content item execution</p>
          </div>
        </div>

        {/* Target Details Card */}
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 mb-5 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 font-medium">Fixture Name:</span>
            <span className="font-semibold text-gray-900">{fixture.name}</span>
          </div>
          {fixture.tableId && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-500 font-medium">Airtable Table ID:</span>
              <span className="font-mono text-xs bg-gray-200 px-2 py-0.5 rounded text-gray-800">
                {fixture.tableId}
              </span>
            </div>
          )}

          {fixture.moodboardId !== undefined && (
            <div className="flex flex-col gap-1.5 pt-2 pb-1 border-t border-gray-200/70">
              <div className="flex items-center justify-between">
                <span className="text-gray-600 font-medium text-xs flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-indigo-500" />
                  Krea Moodboard ID:
                </span>
                {fixture.moodboardId && moodboardInput !== fixture.moodboardId && (
                  <button
                    type="button"
                    onClick={() => setMoodboardInput(fixture.moodboardId || '')}
                    className="text-[11px] text-indigo-600 hover:text-indigo-800 underline font-medium"
                  >
                    Reset default
                  </button>
                )}
              </div>
              <input
                type="text"
                value={moodboardInput}
                onChange={(e) => setMoodboardInput(e.target.value.trim())}
                placeholder="e.g. 0844ad92-c34a-4dc8-9d70-d09498dc098c"
                className="w-full font-mono text-xs bg-white border border-gray-300 rounded-lg px-2.5 py-1.5 text-gray-800 focus:outline-hidden focus:ring-2 focus:ring-sky-500 focus:border-sky-500 shadow-2xs"
              />
              <span className="text-[10px] text-gray-400 leading-tight">
                Pwedeng palitan o i-paste ang bagong Krea Moodboard UUID para sa execution.
              </span>
            </div>
          )}

          {fixture.prompt !== undefined && (
            <div className="flex flex-col gap-1.5 pt-2 pb-1 border-t border-gray-200/70">
              <div className="flex items-center justify-between">
                <span className="text-gray-600 font-medium text-xs flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-amber-500" />
                  Krea Interior Prompt:
                </span>
                {fixture.prompt && promptInput !== fixture.prompt && (
                  <button
                    type="button"
                    onClick={() => setPromptInput(fixture.prompt || '')}
                    className="text-[11px] text-amber-600 hover:text-amber-800 underline font-medium"
                  >
                    Reset default
                  </button>
                )}
              </div>
              <textarea
                value={promptInput}
                onChange={(e) => setPromptInput(e.target.value)}
                rows={2}
                placeholder="e.g. Generate me a modern living room"
                className="w-full text-xs bg-white border border-gray-300 rounded-lg px-2.5 py-1.5 text-gray-800 focus:outline-hidden focus:ring-2 focus:ring-sky-500 focus:border-sky-500 shadow-2xs resize-none"
              />
              <span className="text-[10px] text-gray-400 leading-tight">
                Prompt na gagamitin sa pag-generate ng 9:16 interior sa Krea AI.
              </span>
            </div>
          )}

          {/* Batch Size Stepper */}
          <div className="pt-2 border-t border-gray-200/70">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-500 font-medium text-sm">Batch Size:</span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setItemCount(c => clampCount(c - 1))}
                  disabled={itemCount <= 1}
                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-600 hover:bg-gray-100 active:bg-gray-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
                <span className="w-9 text-center font-bold text-base text-gray-900 tabular-nums">{itemCount}</span>
                <button
                  type="button"
                  onClick={() => setItemCount(c => clampCount(c + 1))}
                  disabled={itemCount >= 10}
                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-600 hover:bg-gray-100 active:bg-gray-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            {/* Preset Pills */}
            <div className="flex items-center gap-1.5">
              {PRESET_PILLS.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setItemCount(n)}
                  className={`px-2.5 py-1 rounded-full text-xs font-semibold transition-all ${
                    itemCount === n
                      ? 'bg-sky-600 text-white shadow-sm'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-gray-200'
                  }`}
                >
                  {n}
                </button>
              ))}
              <span className="text-[10px] text-gray-400 ml-1">max 10</span>
            </div>
          </div>

          <div className="flex justify-between text-sm">
            <span className="text-gray-500 font-medium">Current Progress:</span>
            <span className="font-semibold text-sky-700">
              {fixture.completed === null ? '—' : `${fixture.completed} / ${fixture.total}`} completed
            </span>
          </div>
          <div className="flex justify-between text-sm pt-1 border-t border-gray-200">
            <span className="text-gray-500 font-medium">Will Produce:</span>
            <span className="font-semibold text-emerald-700">{itemCount} Item{itemCount > 1 ? 's' : ''} (All {totalPhases} Phases)</span>
          </div>
        </div>

        {/* Info Alert */}
        <div className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3 mb-5">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>
            This will execute <strong>{itemCount}</strong> content item{itemCount > 1 ? 's' : ''} across the {totalPhases}-phase pipeline ({phaseSummary}). Completed progress will refresh from Airtable after the run.
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(moodboardInput || fixture.moodboardId, promptInput || fixture.prompt, itemCount)}
            disabled={isLoading}
            className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-700 active:bg-sky-800 rounded-lg shadow-xs hover:shadow transition-all disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                Confirm & Run{itemCount > 1 ? ` (${itemCount})` : ''}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
