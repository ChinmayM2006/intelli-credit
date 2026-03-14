import React from 'react';

const stageConfig = {
  onboarding:       { label: 'Onboarding',   icon: '📋', step: 1 },
  documents_uploaded: { label: 'Documents',    icon: '📄', step: 2 },
  research_done:    { label: 'Research',      icon: '🔍', step: 3 },
  scored:           { label: 'Scored',        icon: '📊', step: 4 },
  report_generated: { label: 'Report Ready',  icon: '📑', step: 5 },
};

const ALL_STAGES = ['onboarding', 'documents_uploaded', 'research_done', 'scored', 'report_generated'];

export default function StageProgress({ currentStage }) {
  const currentStep = stageConfig[currentStage]?.step || 1;

  return (
    <div className="flex items-center gap-0 w-full">
      {ALL_STAGES.map((stage, i) => {
        const cfg = stageConfig[stage];
        const isComplete = cfg.step < currentStep;
        const isCurrent = cfg.step === currentStep;

        return (
          <React.Fragment key={stage}>
            <div className={`flex flex-col items-center ${isCurrent ? 'scale-110' : ''} transition-transform`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-all ${
                isComplete ? 'bg-emerald-500 border-emerald-500 text-white' :
                isCurrent ? 'bg-brand-600 border-brand-600 text-white shadow-lg shadow-brand-200' :
                'bg-white border-slate-200 text-slate-400'
              }`}>
                {isComplete ? '✓' : cfg.icon}
              </div>
              <span className={`text-[10px] mt-1 font-medium ${
                isCurrent ? 'text-brand-600' : isComplete ? 'text-emerald-600' : 'text-slate-400'
              }`}>{cfg.label}</span>
            </div>
            {i < ALL_STAGES.length - 1 && (
              <div className={`flex-1 h-0.5 mx-1 mt-[-16px] ${
                cfg.step < currentStep ? 'bg-emerald-400' : 'bg-slate-200'
              }`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
