import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createApplication } from '../api';

const INDUSTRIES = [
  'Manufacturing - Auto Components', 'Manufacturing - Textiles', 'Manufacturing - Chemicals',
  'Manufacturing - Pharma', 'Manufacturing - Steel', 'IT Services', 'FMCG', 'Infrastructure',
  'Real Estate', 'Agriculture & Allied', 'Renewable Energy', 'Trading', 'Logistics',
  'Healthcare', 'Education', 'Financial Services', 'Other',
];

const LOAN_TYPES = [
  { value: 'term_loan', label: 'Term Loan', desc: 'For capex, expansion, project finance' },
  { value: 'working_capital', label: 'Working Capital', desc: 'Cash credit, overdraft facilities' },
  { value: 'project_finance', label: 'Project Finance', desc: 'New project or greenfield setup' },
  { value: 'lc_bg', label: 'LC / BG', desc: 'Letter of Credit / Bank Guarantee' },
];

const STEPS = ['Company Details', 'Loan Requirements', 'Review & Submit'];

export default function NewApplication() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    company_name: '', cin: '', industry: '', incorporation_year: '',
    promoter_names: '', loan_amount_requested: '', loan_purpose: '',
    loan_type: 'term_loan', loan_tenure_requested: '',
  });

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        incorporation_year: form.incorporation_year ? parseInt(form.incorporation_year) : null,
        loan_amount_requested: form.loan_amount_requested ? parseFloat(form.loan_amount_requested) : 0,
        loan_tenure_requested: form.loan_tenure_requested ? parseInt(form.loan_tenure_requested) : 0,
      };
      const res = await createApplication(payload);
      navigate(`/application/${res.data.id}`);
    } catch (e) {
      alert('Error creating application: ' + (e.response?.data?.detail || e.message));
    }
    setSubmitting(false);
  };

  const canNext = () => {
    if (step === 0) return form.company_name.length > 0;
    if (step === 1) return form.loan_amount_requested > 0;
    return true;
  };

  return (
    <div className="animate-fade-in max-w-2xl mx-auto">
      {/* Step indicator */}
      <div className="flex items-center gap-0 mb-8">
        {STEPS.map((s, i) => (
          <React.Fragment key={i}>
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all ${
                i < step ? 'bg-emerald-500 border-emerald-500 text-white' :
                i === step ? 'bg-brand-600 border-brand-600 text-white' :
                'bg-white border-slate-200 text-slate-400'
              }`}>
                {i < step ? '✓' : i + 1}
              </div>
              <span className={`text-xs font-medium ${i === step ? 'text-brand-600' : 'text-slate-400'}`}>{s}</span>
            </div>
            {i < STEPS.length - 1 && <div className={`flex-1 h-0.5 mx-3 ${i < step ? 'bg-emerald-400' : 'bg-slate-200'}`} />}
          </React.Fragment>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        {/* Step 1: Company Details */}
        {step === 0 && (
          <div className="space-y-5 animate-slide-up">
            <h2 className="text-lg font-semibold text-slate-800">Company Information</h2>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Company Name *</label>
              <input value={form.company_name} onChange={e => set('company_name', e.target.value)}
                placeholder="e.g. Bharat Industries Pvt Ltd"
                className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">CIN Number</label>
                <input value={form.cin} onChange={e => set('cin', e.target.value)}
                  placeholder="U28100MH2015PTC268500"
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Incorporation Year</label>
                <input type="number" value={form.incorporation_year} onChange={e => set('incorporation_year', e.target.value)}
                  placeholder="2015"
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Industry</label>
              <select value={form.industry} onChange={e => set('industry', e.target.value)}
                className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none bg-white">
                <option value="">Select Industry</option>
                {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Promoter Names</label>
              <input value={form.promoter_names} onChange={e => set('promoter_names', e.target.value)}
                placeholder="Rajesh Kumar, Priya Sharma"
                className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
            </div>
          </div>
        )}

        {/* Step 2: Loan Requirements */}
        {step === 1 && (
          <div className="space-y-5 animate-slide-up">
            <h2 className="text-lg font-semibold text-slate-800">Loan Requirements</h2>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-2">Loan Type</label>
              <div className="grid grid-cols-2 gap-3">
                {LOAN_TYPES.map(lt => (
                  <button key={lt.value} onClick={() => set('loan_type', lt.value)}
                    className={`text-left p-3 rounded-lg border-2 transition-all ${
                      form.loan_type === lt.value
                        ? 'border-brand-500 bg-brand-50'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}>
                    <div className="text-sm font-medium text-slate-700">{lt.label}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{lt.desc}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Loan Amount (₹ Crores) *</label>
                <input type="number" value={form.loan_amount_requested}
                  onChange={e => set('loan_amount_requested', e.target.value)}
                  placeholder="50"
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Desired Tenure (years)</label>
                <input type="number" value={form.loan_tenure_requested}
                  onChange={e => set('loan_tenure_requested', e.target.value)}
                  placeholder="5"
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Loan Purpose</label>
              <textarea value={form.loan_purpose} onChange={e => set('loan_purpose', e.target.value)}
                placeholder="Capacity expansion and working capital requirements for FY25-26"
                rows={3}
                className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none resize-none" />
            </div>
          </div>
        )}

        {/* Step 3: Review */}
        {step === 2 && (
          <div className="space-y-5 animate-slide-up">
            <h2 className="text-lg font-semibold text-slate-800">Review & Submit</h2>
            <div className="bg-surface-50 rounded-lg p-4 space-y-3">
              {[
                ['Company', form.company_name],
                ['CIN', form.cin || '-'],
                ['Industry', form.industry || '-'],
                ['Promoters', form.promoter_names || '-'],
                ['Loan Type', LOAN_TYPES.find(l => l.value === form.loan_type)?.label],
                ['Amount', `₹${form.loan_amount_requested || 0} Crores`],
                ['Purpose', form.loan_purpose || '-'],
                ['Tenure', form.loan_tenure_requested ? `${form.loan_tenure_requested} years` : '-'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="text-slate-500">{k}</span>
                  <span className="text-slate-800 font-medium">{v}</span>
                </div>
              ))}
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
              After submission, you'll upload documents and run the AI analysis pipeline.
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-6 pt-5 border-t border-slate-100">
          <button onClick={() => setStep(s => Math.max(0, s - 1))}
            disabled={step === 0}
            className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-40">
            ← Back
          </button>
          {step < 2 ? (
            <button onClick={() => setStep(s => s + 1)}
              disabled={!canNext()}
              className="px-5 py-2 text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 rounded-lg transition-colors disabled:opacity-40 shadow-sm">
              Next →
            </button>
          ) : (
            <button onClick={handleSubmit} disabled={submitting}
              className="px-5 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors disabled:opacity-60 shadow-sm flex items-center gap-2">
              {submitting ? (
                <><div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" /> Creating...</>
              ) : (
                <>Create Application</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
