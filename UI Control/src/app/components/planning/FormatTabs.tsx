export type TabType = 'feed' | 'story' | 'reel';

export interface FormatTabCount {
  completed: number | null;
  total?: number;
}

interface FormatTabsProps {
  activeTab: TabType;
  counts: Record<TabType, number | FormatTabCount>;
  onSelectTab: (tab: TabType) => void;
  runningTab?: TabType | null;
}

export function FormatTabs({ activeTab, counts, onSelectTab, runningTab }: FormatTabsProps) {
  const getCountDisplay = (tab: TabType) => {
    const val = counts[tab];
    if (typeof val === 'number') return { label: `${val}`, tooltip: `${val} items` };
    return {
      label: val.completed === null ? '—' : `${val.completed}`,
      tooltip: val.completed === null
        ? 'Waiting for verified Airtable completion counts'
        : `${val.completed} completed records${val.total ? ` out of ${val.total} target items` : ''}`,
    };
  };

  const feedDisplay = getCountDisplay('feed');
  const storyDisplay = getCountDisplay('story');
  const reelDisplay = getCountDisplay('reel');
  return (
    <div className="mb-4">
      <div className="flex gap-2 border-b border-gray-200">
        {/* Feed Tab (Yellow / Amber) */}
        <button
          onClick={() => onSelectTab('feed')}
          className={`flex items-center gap-2 px-6 py-3 font-medium transition border-b-2 cursor-pointer ${
            activeTab === 'feed'
              ? 'border-amber-500 text-amber-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          <span>Feed</span>
          <span
            title={feedDisplay.tooltip}
            className={`text-xs px-2 py-0.5 rounded-full font-medium tabular-nums ${
              activeTab === 'feed'
                ? 'bg-amber-100/80 text-amber-800'
                : 'bg-gray-100 text-gray-600'
            }`}
          >
            {feedDisplay.label}
          </span>
          {runningTab === 'feed' && (
            <span className="flex items-center gap-1.5 ml-1 px-2 py-0.5 bg-amber-100 text-amber-800 text-[10px] font-bold rounded-full animate-pulse border border-amber-300">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
              Running
            </span>
          )}
        </button>

        {/* Story Tab (Light Blue / Sky) */}
        <button
          onClick={() => onSelectTab('story')}
          className={`flex items-center gap-2 px-6 py-3 font-medium transition border-b-2 cursor-pointer ${
            activeTab === 'story'
              ? 'border-sky-500 text-sky-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          <span>Story</span>
          <span
            title={storyDisplay.tooltip}
            className={`text-xs px-2 py-0.5 rounded-full font-medium tabular-nums ${
              activeTab === 'story'
                ? 'bg-sky-100/80 text-sky-800'
                : 'bg-gray-100 text-gray-600'
            }`}
          >
            {storyDisplay.label}
          </span>
          {runningTab === 'story' && (
            <span className="flex items-center gap-1.5 ml-1 px-2 py-0.5 bg-sky-100 text-sky-800 text-[10px] font-bold rounded-full animate-pulse border border-sky-300">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500"></span>
              Running
            </span>
          )}
        </button>

        {/* Reel Tab (Green / Emerald) */}
        <button
          onClick={() => onSelectTab('reel')}
          className={`flex items-center gap-2 px-6 py-3 font-medium transition border-b-2 cursor-pointer ${
            activeTab === 'reel'
              ? 'border-emerald-600 text-emerald-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          <span>Reel</span>
          <span
            title={reelDisplay.tooltip}
            className={`text-xs px-2 py-0.5 rounded-full font-medium tabular-nums ${
              activeTab === 'reel'
                ? 'bg-emerald-100/80 text-emerald-800'
                : 'bg-gray-100 text-gray-600'
            }`}
          >
            {reelDisplay.label}
          </span>
          {runningTab === 'reel' && (
            <span className="flex items-center gap-1.5 ml-1 px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full animate-pulse border border-emerald-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              Running
            </span>
          )}
        </button>
      </div>
    </div>
  );
}
