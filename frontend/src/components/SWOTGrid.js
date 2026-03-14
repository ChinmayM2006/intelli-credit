import React from 'react';

const colors = {
  strengths:     { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', icon: '💪', title: 'Strengths' },
  weaknesses:    { bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700',   icon: '⚠️', title: 'Weaknesses' },
  opportunities: { bg: 'bg-blue-50',    border: 'border-blue-200',    text: 'text-blue-700',    icon: '🚀', title: 'Opportunities' },
  threats:       { bg: 'bg-red-50',     border: 'border-red-200',     text: 'text-red-700',     icon: '🛡️', title: 'Threats' },
};

function SWOTQuadrant({ type, items }) {
  const c = colors[type];
  return (
    <div className={`${c.bg} ${c.border} border rounded-xl p-4 animate-fade-in`}>
      <h4 className={`${c.text} font-semibold text-sm mb-3 flex items-center gap-2`}>
        <span>{c.icon}</span> {c.title}
      </h4>
      <ul className="space-y-2">
        {(items || []).map((item, i) => {
          const point = typeof item === 'object' && item !== null ? (item.point || JSON.stringify(item)) : String(item);
          const detail = typeof item === 'object' && item !== null ? item.detail : null;
          return (
            <li key={i} className={`text-xs ${c.text} flex items-start gap-2`}>
              <span className="mt-1 w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" />
              <span>
                <span className="font-semibold">{point}</span>
                {detail && <span className="opacity-75 block mt-0.5">{detail}</span>}
              </span>
            </li>
          );
        })}
        {(!items || items.length === 0) && (
          <li className="text-xs text-slate-400 italic">No data available</li>
        )}
      </ul>
    </div>
  );
}

export default function SWOTGrid({ swot }) {
  if (!swot) return null;
  return (
    <div className="grid grid-cols-2 gap-3">
      <SWOTQuadrant type="strengths" items={swot.strengths} />
      <SWOTQuadrant type="weaknesses" items={swot.weaknesses} />
      <SWOTQuadrant type="opportunities" items={swot.opportunities} />
      <SWOTQuadrant type="threats" items={swot.threats} />
    </div>
  );
}
