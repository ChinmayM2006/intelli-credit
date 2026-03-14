import React from 'react';

export default function ScoreGauge({ score, maxScore = 100, label, size = 120, color }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(score / maxScore, 1);
  const offset = circumference * (1 - pct);

  const getColor = () => {
    if (color) return color;
    if (pct >= 0.75) return '#10b981';
    if (pct >= 0.5) return '#3b82f6';
    if (pct >= 0.25) return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth="8" />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={getColor()}
          strokeWidth="8" strokeLinecap="round" strokeDasharray={circumference}
          strokeDashoffset={offset} className="score-ring" />
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <span className="text-2xl font-bold text-slate-800">{Math.round(score)}</span>
        <span className="text-xs text-slate-500">/ {maxScore}</span>
      </div>
      {label && <span className="mt-1 text-xs font-medium text-slate-600">{label}</span>}
    </div>
  );
}
