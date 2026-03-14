import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { listApplications } from '../api';

const MetricCard = ({ icon, label, value, color, sub }) => (
  <div className="bg-white rounded-xl border border-slate-200 p-5 card-hover">
    <div className="flex items-center justify-between mb-3">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
        {icon}
      </div>
    </div>
    <div className="text-2xl font-bold text-slate-800">{value}</div>
    <div className="text-xs text-slate-500 mt-1">{label}</div>
    {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
  </div>
);

const stageBadge = (stage) => {
  const map = {
    onboarding: 'bg-slate-100 text-slate-600',
    documents_uploaded: 'bg-blue-100 text-blue-700',
    research_done: 'bg-violet-100 text-violet-700',
    scored: 'bg-emerald-100 text-emerald-700',
    report_generated: 'bg-amber-100 text-amber-700',
  };
  return map[stage] || 'bg-slate-100 text-slate-600';
};

export default function Dashboard() {
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchAll = async () => {
    setLoading(true);
    try {
      const appRes = await listApplications();
      setApps(appRes.data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  const scored = apps.filter(a => a.risk_score);
  const pending = apps.filter(a => !a.risk_score);

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">AI-Powered Credit Decisioning Engine for Indian Corporate Lending</p>
        </div>
        <div className="flex gap-3">
          <Link to="/new"
            className="px-4 py-2 text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 rounded-lg transition-colors shadow-sm">
            + New Application
          </Link>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-4">
        <MetricCard icon={<span className="text-lg">📋</span>} label="Total Applications" value={apps.length}
          color="bg-brand-50" sub="All time" />
        <MetricCard icon={<span className="text-lg">⏳</span>} label="Pending Analysis" value={pending.length}
          color="bg-amber-50" sub="Awaiting scoring" />
        <MetricCard icon={<span className="text-lg">✅</span>} label="Scored" value={scored.length}
          color="bg-emerald-50" sub="Analysis complete" />
      </div>

      {/* Applications table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">Recent Applications</h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-slate-400">
            <div className="animate-spin w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full mx-auto mb-2" />
            Loading...
          </div>
        ) : apps.length === 0 ? (
          <div className="p-12 text-center">
            <div className="text-4xl mb-3">📭</div>
            <div className="text-slate-500 text-sm">No applications yet</div>
            <div className="text-slate-400 text-xs mt-1">Create a new application or load the demo to get started</div>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50 text-left">
                <th className="px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Company</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Industry</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Loan Amount</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Stage</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Score</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {apps.map(app => (
                <tr key={app.id} className="hover:bg-slate-50 transition-colors cursor-pointer"
                    onClick={() => navigate(`/application/${app.id}`)}>
                  <td className="px-5 py-4">
                    <div className="font-medium text-sm text-slate-800">{app.company_name}</div>
                    <div className="text-xs text-slate-400">{app.id}</div>
                  </td>
                  <td className="px-5 py-4 text-sm text-slate-600">{app.industry || '-'}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">
                    {app.loan_amount_requested ? `₹${app.loan_amount_requested}Cr` : '-'}
                  </td>
                  <td className="px-5 py-4">
                    <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${stageBadge(app.stage)}`}>
                      {app.stage?.replace(/_/g, ' ') || 'new'}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    {app.risk_score ? (
                      <span className="text-sm font-semibold text-emerald-600">
                        {app.risk_score.ml_prediction?.rating || '--'}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">-</span>
                    )}
                  </td>
                  <td className="px-5 py-4">
                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Architecture footer */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Architecture Highlights</h3>
        <div className="grid grid-cols-3 gap-4 text-xs text-slate-600">
          <div className="flex items-start gap-2">
            <span className="text-emerald-500 mt-0.5">●</span>
            <div><span className="font-medium">Risk Engine</span><br/>16-feature PD model + Altman Z-Score + 4-method loan structuring</div>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-violet-500 mt-0.5">●</span>
            <div><span className="font-medium">India-Focused</span><br/>GSTR-3B/2B ITC matching, Nayak Committee WC method, CRISIL rating scale</div>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-500 mt-0.5">●</span>
            <div><span className="font-medium">Human-in-Loop</span><br/>Auto-classification with manual override, primary insights integration</div>
          </div>
        </div>
      </div>
    </div>
  );
}
