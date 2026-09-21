import { FixtureCard, FixtureData } from './FixtureCard';
import { TabType } from './FormatTabs';

interface FixtureProgressGridProps {
  fixtures: FixtureData[];
  activeTab?: TabType;
  activeRunningFixtureId?: string | null;
  currentPhase?: string;
  onRunFixture?: (fixture: FixtureData) => void;
  onStopFixture?: (fixture: FixtureData) => void;
  onCancelQueueFixture?: (fixture: FixtureData) => void;
  onEditMoodboard?: (fixture: FixtureData) => void;
  onEditPrompt?: (fixture: FixtureData) => void;
  onViewRows?: (fixture: FixtureData, statusFilter?: string) => void;
  getQueueInfo?: (fixtureId: string) => { isQueued: boolean; position: number } | undefined;
  isAnyPipelineRunning?: boolean;
  canRun?: boolean;
  hideProgressBar?: boolean;
}

export function FixtureProgressGrid({
  fixtures,
  activeTab = 'feed',
  activeRunningFixtureId,
  currentPhase,
  onRunFixture,
  onStopFixture,
  onCancelQueueFixture,
  onEditMoodboard,
  onEditPrompt,
  onViewRows,
  getQueueInfo,
  isAnyPipelineRunning = false,
  canRun = true,
  hideProgressBar = false,
}: FixtureProgressGridProps) {
  // Use responsive grid adapting for 4 or 5 fixture cards
  const gridColsClass =
    fixtures.length >= 5
      ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5'
      : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';

  return (
    <div className={`grid ${gridColsClass} gap-4`}>
      {fixtures.map(fixture => {
        const isRunning = activeRunningFixtureId === fixture.id;
        const qInfo = getQueueInfo ? getQueueInfo(fixture.id) : undefined;
        return (
          <FixtureCard
            key={fixture.id}
            fixture={fixture}
            activeTab={activeTab}
            isRunning={isRunning}
            isQueued={qInfo?.isQueued || false}
            queuePosition={qInfo?.position || 1}
            currentPhase={isRunning ? currentPhase : undefined}
            onRun={onRunFixture}
            onStop={onStopFixture}
            onCancelQueue={onCancelQueueFixture}
            onEditMoodboard={onEditMoodboard}
            onEditPrompt={onEditPrompt}
            onViewRows={onViewRows}
            canRun={canRun}
            isAnyPipelineRunning={isAnyPipelineRunning}
            hideProgressBar={hideProgressBar || !!fixture.statusCounts}
          />
        );
      })}
    </div>
  );
}
