import React from 'react';
import { X } from 'lucide-react';
import { FixtureData } from '../../types';

interface EditPromptModalProps {
  fixture: FixtureData | null;
  pipelineName?: string;
  promptInput: string;
  isSaving: boolean;
  onInputChange: (val: string) => void;
  onClose: () => void;
  onSave: () => void;
}

export function EditPromptModal({
  fixture,
  pipelineName = 'Story',
  promptInput,
  isSaving,
  onInputChange,
  onClose,
  onSave,
}: EditPromptModalProps) {
  if (!fixture) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl max-w-lg w-full p-6 text-gray-900 relative">
        <button
          onClick={onClose}
          disabled={isSaving}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="mb-4 pr-6">
          <h3 className="text-lg font-bold text-gray-900">Edit Krea Interior Generation Prompt</h3>
          <p className="text-xs text-gray-500">{fixture.name} ({pipelineName})</p>
        </div>

        <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 mb-5 space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 font-medium">Fixture:</span>
            <span className="font-semibold text-gray-900">{fixture.name}</span>
          </div>
          <div className="space-y-1 pt-1">
            <label className="text-xs font-semibold text-gray-700 block">
              Krea Interior Prompt:
            </label>
            <textarea
              rows={3}
              value={promptInput}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder="e.g. Generate me a modern living room"
              className="w-full text-xs bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 focus:outline-hidden focus:ring-2 focus:ring-amber-500 focus:border-amber-500 resize-none"
            />
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
            disabled={isSaving || !promptInput.trim()}
            className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-amber-600 hover:bg-amber-700 active:bg-amber-800 rounded-lg shadow-xs hover:shadow transition-all disabled:opacity-50"
          >
            {isSaving ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Saving...
              </>
            ) : (
              <>Save Prompt</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
