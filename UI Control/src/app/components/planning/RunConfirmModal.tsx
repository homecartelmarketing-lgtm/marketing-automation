import { useState, useEffect } from 'react';
import { AlertCircle, Play, X, Sparkles, Minus, Plus, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { FixtureData } from './FixtureCard';

interface RunConfirmModalProps {
  fixture: FixtureData | null;
  pipelineTitle?: string;
  totalPhases?: number;
  phaseSummary?: string;
  phaseSummaryUpload?: string;
  supportsEmptyRoomUpload?: boolean;
  uploadEndpoint?: string;
  klingPromptEndpoint?: string;
  defaultKlingPrompt?: string;
  studioPin?: string;
  onConfirm: (
    customMoodboardId?: string,
    customPrompt?: string,
    maxItems?: number,
    extra?: { source: 'auto' | 'upload'; emptyRoomUrl?: string }
  ) => void;
  onClose: () => void;
  isLoading?: boolean;
}

const PRESET_PILLS = [1, 2, 3, 5, 10];

function authHeaders(pin?: string): Record<string, string> {
  const p =
    pin ||
    (typeof window !== 'undefined'
      ? localStorage.getItem('hc_studio_pin') || sessionStorage.getItem('hc_studio_pin') || ''
      : '');
  return p ? { Authorization: `Bearer ${p}`, 'X-Dashboard-PIN': p } : {};
}

export function RunConfirmModal({
  fixture,
  pipelineTitle = 'Run Story Pipeline',
  totalPhases = 6,
  phaseSummary = 'Akeneo Scrape ➔ Krea Interior ➔ Claude Prompt ➔ Banana Blend ➔ Headline ➔ Layout Stamping',
  phaseSummaryUpload,
  supportsEmptyRoomUpload = false,
  uploadEndpoint,
  klingPromptEndpoint,
  defaultKlingPrompt,
  studioPin,
  onConfirm,
  onClose,
  isLoading = false,
}: RunConfirmModalProps) {
  if (!fixture) return null;

  const [sourceMode, setSourceMode] = useState<'auto' | 'upload'>('auto');
  const [moodboardInput, setMoodboardInput] = useState<string>(fixture.moodboardId || '');
  const [promptInput, setPromptInput] = useState<string>(fixture.prompt || '');
  const [klingPromptInput, setKlingPromptInput] = useState<string>(
    fixture.klingPrompt || defaultKlingPrompt || ''
  );
  const [itemCount, setItemCount] = useState<number>(1);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);

  useEffect(() => {
    setSourceMode('auto');
    setMoodboardInput(fixture?.moodboardId || '');
    setPromptInput(fixture?.prompt || '');
    setKlingPromptInput(fixture?.klingPrompt || defaultKlingPrompt || '');
    setItemCount(1);
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
  }, [fixture?.moodboardId, fixture?.prompt, fixture?.klingPrompt, fixture?.id, defaultKlingPrompt]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const clampCount = (n: number) => Math.max(1, Math.min(10, n));

  const handleFileSelected = (file: File) => {
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      toast.error('Invalid image type. Please select JPEG, PNG, or WebP.');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      toast.error('Image exceeds 15 MB limit.');
      return;
    }
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleConfirmClick = async () => {
    if (sourceMode === 'upload') {
      if (!selectedFile) {
        toast.error('Please select an empty room photo');
        return;
      }
      if (!uploadEndpoint) {
        toast.error('Upload endpoint not configured');
        return;
      }
      setIsUploading(true);
      try {
        const pin =
          studioPin ||
          (typeof window !== 'undefined'
            ? localStorage.getItem('hc_studio_pin') || sessionStorage.getItem('hc_studio_pin') || ''
            : '');
        const form = new FormData();
        form.append('file', selectedFile);
        const res = await fetch(uploadEndpoint, {
          method: 'POST',
          headers: authHeaders(pin),
          body: form,
        });
        const data = await res.json();
        if (!res.ok || data.status !== 'success' || !data.empty_room_url) {
          throw new Error(data.error || `Upload failed (HTTP ${res.status})`);
        }

        const emptyRoomUrl = data.empty_room_url;

        // Save Kling prompt override if edited
        const defaultPrompt = fixture.klingPrompt || defaultKlingPrompt || '';
        if (
          klingPromptEndpoint &&
          klingPromptInput.trim() &&
          klingPromptInput.trim() !== defaultPrompt.trim()
        ) {
          try {
            await fetch(klingPromptEndpoint, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...authHeaders(pin),
              },
              body: JSON.stringify({ prompt: klingPromptInput.trim() }),
            });
          } catch (e) {
            console.warn('Failed to save Kling prompt override:', e);
          }
        }

        onConfirm(undefined, undefined, 1, { source: 'upload', emptyRoomUrl });
      } catch (err: any) {
        toast.error(`Upload error: ${err.message || err}`);
      } finally {
        setIsUploading(false);
      }
    } else {
      onConfirm(
        moodboardInput || fixture.moodboardId,
        promptInput || fixture.prompt,
        itemCount,
        { source: 'auto' }
      );
    }
  };

  const effectiveItemCount = sourceMode === 'upload' ? 1 : itemCount;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-card rounded-2xl border border-gray-200 shadow-2xl max-w-md w-full p-6 text-gray-900 relative max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          disabled={isLoading || isUploading}
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

        {/* Mode Toggle (if pipeline supports empty room upload) */}
        {supportsEmptyRoomUpload && (
          <div className="flex bg-gray-100 p-1 rounded-xl mb-4 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setSourceMode('auto')}
              className={`flex-1 py-1.5 px-3 rounded-lg transition-all ${
                sourceMode === 'auto'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              Auto (Krea)
            </button>
            <button
              type="button"
              onClick={() => setSourceMode('upload')}
              className={`flex-1 py-1.5 px-3 rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                sourceMode === 'upload'
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <Upload className="w-3.5 h-3.5" />
              Upload empty room
            </button>
          </div>
        )}

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

          {/* Upload Mode Fields */}
          {sourceMode === 'upload' ? (
            <>
              {/* Drop Zone */}
              <div className="flex flex-col gap-1.5 pt-2 pb-1 border-t border-gray-200/70">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600 font-medium text-xs flex items-center gap-1">
                    <Upload className="w-3.5 h-3.5 text-sky-600" />
                    Empty Room Photo (9:16):
                  </span>
                  {selectedFile && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedFile(null);
                        if (previewUrl) URL.revokeObjectURL(previewUrl);
                        setPreviewUrl(null);
                      }}
                      className="text-[11px] text-red-600 hover:text-red-800 underline font-medium"
                    >
                      Remove
                    </button>
                  )}
                </div>

                {!previewUrl ? (
                  <label
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDragging(false);
                      const f = e.dataTransfer.files?.[0];
                      if (f) handleFileSelected(f);
                    }}
                    className={`border-2 border-dashed rounded-xl p-4 flex flex-col items-center justify-center cursor-pointer transition-colors ${
                      isDragging
                        ? 'border-sky-500 bg-sky-50/50'
                        : 'border-gray-300 hover:border-gray-400 bg-gray-50/50'
                    }`}
                  >
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) handleFileSelected(f);
                      }}
                    />
                    <div className="w-10 h-10 rounded-full bg-sky-100 flex items-center justify-center text-sky-600 mb-2">
                      <Upload className="w-5 h-5" />
                    </div>
                    <p className="text-xs font-semibold text-gray-700">Click to upload or drag & drop</p>
                    <p className="text-[11px] text-gray-400 mt-0.5">JPEG, PNG, or WebP (max 15 MB)</p>
                  </label>
                ) : (
                  <div className="relative rounded-xl overflow-hidden border border-gray-200 bg-black/5 flex justify-center">
                    <img
                      src={previewUrl}
                      alt="Empty room preview"
                      className="max-h-56 aspect-[9/16] object-cover rounded-lg shadow-inner"
                    />
                    <div className="absolute bottom-2 left-2 right-2 bg-black/70 backdrop-blur-xs text-white text-[10px] px-2 py-1 rounded-md text-center truncate">
                      {selectedFile?.name}
                    </div>
                  </div>
                )}

                <span className="text-[10px] text-gray-400 leading-tight">
                  Shoot level, wide, no furniture. We crop to 9:16.
                </span>
              </div>

              {/* Kling Motion Prompt */}
              <div className="flex flex-col gap-1.5 pt-2 pb-1 border-t border-gray-200/70">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600 font-medium text-xs flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-sky-500" />
                    Kling Motion Prompt:
                  </span>
                  {(fixture.klingPrompt || defaultKlingPrompt) &&
                    klingPromptInput !== (fixture.klingPrompt || defaultKlingPrompt || '') && (
                      <button
                        type="button"
                        onClick={() =>
                          setKlingPromptInput(fixture.klingPrompt || defaultKlingPrompt || '')
                        }
                        className="text-[11px] text-sky-600 hover:text-sky-800 underline font-medium"
                      >
                        Reset default
                      </button>
                    )}
                </div>
                <textarea
                  value={klingPromptInput}
                  onChange={(e) => setKlingPromptInput(e.target.value)}
                  rows={4}
                  placeholder="Kling 3.0 Pro motion prompt..."
                  className="w-full text-xs bg-card border border-gray-300 rounded-lg px-2.5 py-1.5 text-gray-800 focus:outline-hidden focus:ring-2 focus:ring-sky-500 focus:border-sky-500 shadow-2xs resize-y"
                />
                <span className="text-[10px] text-gray-400 leading-tight">
                  Motion prompt for Kling 3.0 Pro (10s continuous camera push-in).
                </span>
              </div>
            </>
          ) : (
            <>
              {/* Auto Mode Krea Moodboard */}
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
                    className="w-full font-mono text-xs bg-card border border-gray-300 rounded-lg px-2.5 py-1.5 text-gray-800 focus:outline-hidden focus:ring-2 focus:ring-sky-500 focus:border-sky-500 shadow-2xs"
                  />
                  <span className="text-[10px] text-gray-400 leading-tight">
                    Pwedeng palitan o i-paste ang bagong Krea Moodboard UUID para sa execution.
                  </span>
                </div>
              )}

              {/* Auto Mode Krea Prompt */}
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
                    className="w-full text-xs bg-card border border-gray-300 rounded-lg px-2.5 py-1.5 text-gray-800 focus:outline-hidden focus:ring-2 focus:ring-sky-500 focus:border-sky-500 shadow-2xs resize-none"
                  />
                  <span className="text-[10px] text-gray-400 leading-tight">
                    Prompt na gagamitin sa pag-generate ng 9:16 interior sa Krea AI.
                  </span>
                </div>
              )}
            </>
          )}

          {/* Batch Size Stepper */}
          <div className="pt-2 border-t border-gray-200/70">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-500 font-medium text-sm">Batch Size:</span>
              {sourceMode === 'upload' ? (
                <span className="text-xs font-semibold text-gray-500 bg-gray-100 px-2.5 py-1 rounded-lg border border-gray-200">
                  1 upload = 1 reel
                </span>
              ) : (
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setItemCount((c) => clampCount(c - 1))}
                    disabled={itemCount <= 1}
                    className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-300 bg-card text-gray-600 hover:bg-gray-100 active:bg-gray-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <Minus className="w-3.5 h-3.5" />
                  </button>
                  <span className="w-9 text-center font-bold text-base text-gray-900 tabular-nums">
                    {itemCount}
                  </span>
                  <button
                    type="button"
                    onClick={() => setItemCount((c) => clampCount(c + 1))}
                    disabled={itemCount >= 10}
                    className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-300 bg-card text-gray-600 hover:bg-gray-100 active:bg-gray-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>

            {/* Preset Pills (Auto mode only) */}
            {sourceMode === 'auto' && (
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
            )}
          </div>

          <div className="flex justify-between text-sm">
            <span className="text-gray-500 font-medium">Current Progress:</span>
            <span className="font-semibold text-sky-700">
              {fixture.completed === null ? '—' : `${fixture.completed} / ${fixture.total}`} completed
            </span>
          </div>
          <div className="flex justify-between text-sm pt-1 border-t border-gray-200">
            <span className="text-gray-500 font-medium">Will Produce:</span>
            <span className="font-semibold text-emerald-700">
              {effectiveItemCount} Item{effectiveItemCount > 1 ? 's' : ''} (All {totalPhases} Phases)
            </span>
          </div>
        </div>

        {/* Info Alert */}
        <div className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3 mb-5">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>
            {sourceMode === 'upload' ? (
              <>
                This will execute <strong>1</strong> content item using your uploaded empty room (
                {phaseSummaryUpload || phaseSummary}).
              </>
            ) : (
              <>
                This will execute <strong>{itemCount}</strong> content item{itemCount > 1 ? 's' : ''}{' '}
                across the {totalPhases}-phase pipeline ({phaseSummary}). Completed progress will
                refresh from Airtable after the run.
              </>
            )}
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading || isUploading}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirmClick}
            disabled={isLoading || isUploading || (sourceMode === 'upload' && !selectedFile)}
            className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-700 active:bg-sky-800 rounded-lg shadow-xs hover:shadow transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading || isUploading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {isUploading ? 'Uploading...' : 'Starting...'}
              </>
            ) : (
              <>
                {sourceMode === 'upload' ? (
                  <Upload className="w-4 h-4" />
                ) : (
                  <Play className="w-4 h-4 fill-current" />
                )}
                {sourceMode === 'upload'
                  ? 'Upload & Run'
                  : `Confirm & Run${itemCount > 1 ? ` (${itemCount})` : ''}`}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
