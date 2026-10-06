import React from 'react';
import { X } from 'lucide-react';
import { FixtureData } from '../../types';

interface EditMoodboardModalProps {
  fixture: FixtureData | null;
  pipelineName?: string;
  moodboardInput: string;
  isSaving: boolean;
  onInputChange: (val: string) => void;
  onClose: () => void;
  onSave: () => void;
  // Room-sectioned editing (multi-room single-card pipelines, e.g. House Tour).
  // When provided, 4 labeled inputs render instead of the single field.
  rooms?: { key: string; label: string; value: string }[] | null;
  onRoomChange?: (key: string, val: string) => void;
}

export function EditMoodboardModal({
  fixture,
  pipelineName = 'Story',
  moodboardInput,
  isSaving,
  onInputChange,
  onClose,
  onSave,
  rooms = null,
  onRoomChange,
}: EditMoodboardModalProps) {
  if (!fixture) return null;

  const roomsValid = !rooms || rooms.every(r => r.value.trim());
  const canSave = !isSaving && (rooms ? roomsValid : Boolean(moodboardInput.trim()));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-card rounded-2xl border border-gray-200 shadow-2xl max-w-md w-full p-6 text-gray-900 relative max-h-[85vh] overflow-y-auto">
        <button
          onClick={onClose}
          disabled={isSaving}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="mb-4 pr-6">
          <h3 className="text-lg font-bold text-gray-900">Change Krea Moodboard ID</h3>
          <p className="text-xs text-gray-500">{fixture.name} ({pipelineName})</p>
        </div>

        <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 mb-5 space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 font-medium">Fixture:</span>
            <span className="font-semibold text-gray-900">{fixture.name}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 font-medium">Airtable Table ID:</span>
            <span className="font-mono text-xs bg-gray-200 px-2 py-0.5 rounded text-gray-800">
              {fixture.tableId || 'Not linked'}
            </span>
          </div>
          <div className="space-y-1 pt-1">
            <label className="text-xs font-semibold text-gray-700 block">
              Krea Moodboard ID (UUID):
            </label>
            {rooms ? (
              <div className="space-y-2">
                {rooms.map(room => (
                  <div key={room.key} className="space-y-0.5">
                    <span className="text-[11px] font-medium text-gray-500">{room.label}</span>
                    <input
                      type="text"
                      value={room.value}
                      onChange={(e) => onRoomChange?.(room.key, e.target.value)}
                      placeholder="e.g. 0844ad92-c34a-4dc8-9d70-d09498dc098c"
                      className="w-full text-xs font-mono bg-card border border-gray-300 rounded-lg px-3 py-2 text-gray-900 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                ))}
              </div>
            ) : (
            <input
              type="text"
              value={moodboardInput}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder="e.g. 0844ad92-c34a-4dc8-9d70-d09498dc098c"
              className="w-full text-xs font-mono bg-card border border-gray-300 rounded-lg px-3 py-2 text-gray-900 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={!canSave}
            className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 rounded-lg shadow-xs hover:shadow transition-all disabled:opacity-50"
          >
            {isSaving ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Saving...
              </>
            ) : (
              <>Save Moodboard ID</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
