import React from 'react';
import { Key, X } from 'lucide-react';
import { toast } from 'sonner';

interface StudioPinModalProps {
  isOpen: boolean;
  studioPin: string;
  pinInput: string;
  onPinInputChange: (val: string) => void;
  onClose: () => void;
  onSavePin: (val: string) => void;
  onClearPin: () => void;
}

export function StudioPinModal({
  isOpen,
  studioPin,
  pinInput,
  onPinInputChange,
  onClose,
  onSavePin,
  onClearPin,
}: StudioPinModalProps) {
  if (!isOpen) return null;

  const handleSave = () => {
    const val = pinInput.trim();
    onSavePin(val);
    onClose();
    toast.success('Studio PIN saved!');
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-5 border border-gray-100 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
              <Key className="w-4 h-4" />
            </div>
            <h3 className="text-sm font-semibold text-gray-900">Studio Security PIN</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1 rounded-md"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Enter your Studio PIN to authorize paid AI generation pipelines and protect API credits.
        </p>
        <input
          type="password"
          value={pinInput}
          onChange={(e) => onPinInputChange(e.target.value)}
          placeholder="Enter PIN (e.g. 1234)"
          autoFocus
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 mb-4 font-mono"
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleSave();
            }
          }}
        />
        <div className="flex justify-end gap-2">
          {studioPin && (
            <button
              type="button"
              onClick={() => {
                onClearPin();
                onClose();
                toast.info('Studio PIN cleared');
              }}
              className="px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded-lg transition-all"
            >
              Clear PIN
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 rounded-lg transition-all"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="px-3.5 py-1.5 text-xs bg-sky-600 text-white font-medium rounded-lg hover:bg-sky-700 transition-all shadow-xs"
          >
            Save PIN
          </button>
        </div>
      </div>
    </div>
  );
}
