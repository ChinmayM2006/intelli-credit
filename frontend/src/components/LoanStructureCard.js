import React from 'react';

export default function LoanStructureCard({ structure }) {
  if (!structure) return null;

  const s = structure;
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 animate-fade-in">
      <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
        <span className="w-7 h-7 bg-brand-100 rounded-lg flex items-center justify-center">
          <svg className="w-4 h-4 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </span>
        Recommended Loan Structure
      </h3>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-brand-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-brand-700">₹{typeof s.recommended_amount_cr === 'number' ? s.recommended_amount_cr.toFixed(1) : '--'}Cr</div>
          <div className="text-xs text-brand-500 mt-1">Recommended Amount</div>
        </div>
        <div className="bg-emerald-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-emerald-700">{s.interest_rate_pct?.toFixed(2) || '--'}%</div>
          <div className="text-xs text-emerald-500 mt-1">Interest Rate</div>
        </div>
        <div className="bg-violet-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-violet-700">{s.tenure_years ?? s.recommended_tenure_years ?? '--'} yr</div>
          <div className="text-xs text-violet-500 mt-1">Tenure</div>
        </div>
      </div>

      {s.methods && typeof s.methods === 'object' && (
        <div className="mb-4">
          <h4 className="text-xs font-medium text-slate-500 mb-2">Method Breakdown</h4>
          <div className="space-y-1.5">
            {Object.entries(s.methods).map(([name, info]) => {
              const isBinding = name === s.constraining_method;
              const amt = typeof info === 'object' ? info.eligible_amount : 0;
              return (
                <div key={name} className="flex items-center justify-between text-xs">
                  <span className="text-slate-600">{name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                  <span className={`font-medium ${isBinding ? 'text-brand-600' : 'text-slate-400'}`}>
                    ₹{amt?.toFixed(1)}Cr {isBinding && '← binding'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {(s.constraining_factor || s.constraining_method) && (
        <div className="text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2">
          <span className="font-medium">Constraining factor:</span> {s.constraining_factor || s.constraining_method?.replace(/_/g, ' ')}
        </div>
      )}
    </div>
  );
}
