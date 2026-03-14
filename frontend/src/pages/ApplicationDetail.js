import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  getApplication, uploadDocument, runPipeline, generateReport,
  downloadReportURL, confirmClassification, addPrimaryInsight, getUploadProgress,
} from '../api';
import SWOTGrid from '../components/SWOTGrid';
import LoanStructureCard from '../components/LoanStructureCard';

/* ─── Helpers ──────────────────────────────────────────────────────────── */

const Badge = ({ children, color = 'slate' }) => (
  <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold bg-${color}-100 text-${color}-700`}>
    {children}
  </span>
);

const Section = ({ title, icon, children, defaultOpen = true, collapsible = true }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden animate-fade-in">
      <button onClick={() => collapsible && setOpen(o => !o)}
        className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
        <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <span>{icon}</span> {title}
        </h3>
        {collapsible && (
          <svg className={`w-4 h-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>
      {open && <div className="px-5 pb-5 border-t border-slate-100 pt-4">{children}</div>}
    </div>
  );
};

const ScoreBar = ({ label, score, max = 100 }) => {
  const pct = Math.min((score / max) * 100, 100);
  const color = pct >= 75 ? 'bg-emerald-500' : pct >= 50 ? 'bg-blue-500' : pct >= 25 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-600 w-24 flex-shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-1000`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-slate-700 w-12 text-right">{score}/{max}</span>
    </div>
  );
};

const cleanResearchText = (value) => {
  const input = String(value || '');
  if (!input.trim()) return '';
  return input
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/#{1,6}\s*/g, ' ')
    .replace(/\*\*|__|\*|_/g, ' ')
    .replace(/`/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .trim();
};

/* ─── Main Component ───────────────────────────────────────────────── */

const DOC_TYPES = [
  'alm', 'shareholding', 'borrowing_profile', 'annual_report', 'portfolio',
  'gst', 'financial_statement', 'itr', 'bank_statement', 'board_minutes',
  'rating_report', 'sanction_letter', 'legal_notice',
];

export default function ApplicationDetail() {
  const { id } = useParams();
  const [app, setApp] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgressPct, setUploadProgressPct] = useState(0);
  const [uploadProgressText, setUploadProgressText] = useState('');
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineStages, setPipelineStages] = useState([]);
  const [reportGenerating, setReportGenerating] = useState(false);
  const [showExplain, setShowExplain] = useState(false);
  const [parseMode, setParseMode] = useState('balanced');
  const [expandedDoc, setExpandedDoc] = useState(null);
  const [docTypeOverrides, setDocTypeOverrides] = useState({});
  const [insightForm, setInsightForm] = useState({ content: '', note_type: 'site_visit', officer_name: '' });

  const fetchApp = useCallback(async () => {
    try {
      const res = await getApplication(id);
      setApp(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [id]);

  useEffect(() => { fetchApp(); }, [fetchApp]);

  /* ── Actions ── */

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setUploading(true);
    setUploadProgressPct(0);
    setUploadProgressText('Preparing files...');
    try {
      for (let index = 0; index < files.length; index += 1) {
        const file = files[index];
        const uploadId = `up_${Date.now()}_${index}_${Math.random().toString(36).slice(2, 8)}`;
        setUploadProgressText(`Parsing & classifying: ${file.name}`);

        let polling = true;
        const pollTimer = setInterval(async () => {
          if (!polling) return;
          try {
            const res = await getUploadProgress(id, uploadId);
            const pct = Number(res?.data?.progress_pct || 0);
            const msg = res?.data?.message || `Parsing & classifying: ${file.name}`;
            const overall = ((index + (pct / 100)) / files.length) * 100;
            setUploadProgressPct(Math.round(Math.max(0, Math.min(100, overall))));
            setUploadProgressText(msg);
          } catch (_err) {
          }
        }, 450);

        try {
          await uploadDocument(id, file, { parseMode, uploadId });
        } finally {
          polling = false;
          clearInterval(pollTimer);
        }

        setUploadProgressPct(Math.round(((index + 1) / files.length) * 100));
      }
      setUploadProgressText('Finalizing extraction results...');
      await fetchApp();
    } catch (e) { alert('Upload error: ' + (e.response?.data?.detail || e.message)); }
    setUploading(false);
    setUploadProgressText('');
    setUploadProgressPct(0);
    e.target.value = '';
  };

  const handleRunPipeline = async () => {
    setPipelineRunning(true);
    setPipelineStages([]);
    try {
      const res = await runPipeline(id);
      setPipelineStages(res.data.stages || []);
      setApp(res.data.application);
    } catch (e) {
      alert('Pipeline error: ' + (e.response?.data?.detail || e.message));
    }
    setPipelineRunning(false);
  };

  const handleGenerateReport = async () => {
    setReportGenerating(true);
    try {
      await generateReport(id);
      await fetchApp();
    } catch (e) { alert('Report error: ' + (e.response?.data?.detail || e.message)); }
    setReportGenerating(false);
  };

  const handleConfirmDoc = async (docId, docType) => {
    const finalType = docTypeOverrides[docId] || docType;
    try {
      await confirmClassification(id, docId, finalType);
      setDocTypeOverrides(prev => { const n = {...prev}; delete n[docId]; return n; });
      await fetchApp();
    } catch (e) { console.error(e); }
  };

  const handleAddInsight = async () => {
    if (!insightForm.content) return;
    try {
      await addPrimaryInsight(id, insightForm);
      setInsightForm({ content: '', note_type: 'site_visit', officer_name: '' });
      await fetchApp();
    } catch (e) { console.error(e); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin w-8 h-8 border-3 border-brand-500 border-t-transparent rounded-full" />
    </div>
  );

  if (!app) return (
    <div className="text-center py-16">
      <div className="text-4xl mb-3">❌</div>
      <div className="text-slate-600">Application not found</div>
    </div>
  );

  const rs = app.risk_score;
  const recommendation = rs?.recommendation;
  const fiveCs = rs?.five_cs;
  const mlPred = rs?.ml_prediction;
  const altmanZ = rs?.altman_z;
  const displayLoanStructure = rs?.loan_structure ? {
    ...rs.loan_structure,
    recommended_amount_cr: recommendation?.suggested_loan_amount ?? rs.loan_structure.recommended_amount_cr,
    interest_rate_pct: recommendation?.interest_rate_pct ?? rs.loan_structure.interest_rate_pct,
    tenure_years: recommendation?.recommended_tenure_years ?? rs.loan_structure.tenure_years,
  } : null;
  const scoreCardCount = [!!mlPred, !!altmanZ, !!recommendation].filter(Boolean).length;

  return (
    <div className="animate-fade-in space-y-5">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-slate-800">{app.company_name}</h1>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-slate-400">ID: {app.id}</span>
              {app.cin && <span className="text-xs text-slate-400">CIN: {app.cin}</span>}
              {app.industry && <Badge color="brand">{app.industry}</Badge>}
            </div>
          </div>
          <div className="flex gap-2">
            {rs && (
              <button onClick={handleGenerateReport} disabled={reportGenerating}
                className="px-4 py-2 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors border border-emerald-200 flex items-center gap-2">
                {reportGenerating ? 'Generating...' : '📄 Generate CAM Report'}
              </button>
            )}
            {app.cam_path && (
              <a href={downloadReportURL(id)} target="_blank" rel="noreferrer"
                className="px-4 py-2 text-xs font-medium text-violet-700 bg-violet-50 hover:bg-violet-100 rounded-lg border border-violet-200">
                ⬇ Download PDF
              </a>
            )}
          </div>
        </div>

        {/* Pipeline Status */}
        {(pipelineRunning || pipelineStages.length > 0) && (
          <div className="mt-4 bg-slate-50 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center gap-6">
              {['research', 'scoring', 'swot', 'triangulation'].map((stage, i) => {
                const stageData = pipelineStages.find(s => s.stage === stage);
                const isDone = stageData?.status === 'done';
                const isError = stageData?.status === 'error';
                const isActive = pipelineRunning && !stageData;
                const stageLabels = { research: 'Web Research', scoring: 'Credit Scoring', swot: 'SWOT Analysis', triangulation: 'Triangulation' };
                return (
                  <div key={stage} className="flex-1 text-center">
                    <div className={`w-8 h-8 mx-auto rounded-full flex items-center justify-center text-sm font-bold mb-1 ${
                      isDone ? 'bg-emerald-500 text-white' :
                      isError ? 'bg-red-500 text-white' :
                      isActive && pipelineStages.length === i ? 'bg-brand-500 text-white animate-pulse' :
                      'bg-slate-200 text-slate-400'
                    }`}>
                      {isDone ? '✓' : isError ? '✕' : i + 1}
                    </div>
                    <div className="text-sm font-semibold text-slate-700">{stageLabels[stage]}</div>
                    {isError && stageData.error && (
                      <div className="text-xs text-red-500 mt-0.5 truncate">{stageData.error.slice(0, 60)}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Loan Info Bar */}
      <div className="grid grid-cols-4 gap-3">
        {[
          ['Requested Amount', app.loan_amount_requested ? `₹${app.loan_amount_requested}Cr` : '-', 'bg-brand-50 text-brand-700'],
          ['Loan Type', (app.loan_type || '-').replace(/_/g, ' '), 'bg-violet-50 text-violet-700'],
          ['Tenure Requested', app.loan_tenure_requested ? `${app.loan_tenure_requested} yr` : '-', 'bg-slate-50 text-slate-700'],
          ['Purpose', app.loan_purpose || '-', 'bg-amber-50 text-amber-700'],
        ].map(([label, val, cls]) => (
          <div key={label} className={`rounded-lg p-3 ${cls}`}>
            <div className="text-[10px] font-medium opacity-60">{label}</div>
            <div className="text-sm font-semibold mt-0.5 truncate">{val}</div>
          </div>
        ))}
      </div>

      {/* Documents & Insights Row */}
      <div className="grid grid-cols-2 gap-5">
        {/* Documents Upload */}
        <Section title="Documents" icon="📄">
          <div className="space-y-3">
            <div className="bg-slate-50 rounded-lg border border-slate-200 p-2.5">
              <div className="text-[10px] font-semibold text-slate-600 mb-2">Extraction Mode</div>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { value: 'fast', icon: '⚡', label: 'Fast', hint: 'Quickest pass, lower deep OCR coverage' },
                  { value: 'balanced', icon: '⚖️', label: 'Balanced', hint: 'Best default: speed + good coverage' },
                  { value: 'max_coverage', icon: '🔍', label: 'Max Coverage', hint: 'Deeper OCR on visuals/pages, slower' },
                ].map(mode => (
                  <button
                    key={mode.value}
                    type="button"
                    onClick={() => setParseMode(mode.value)}
                    className={`text-left rounded-md border px-2.5 py-2 transition-colors ${
                      parseMode === mode.value
                        ? 'border-brand-400 bg-brand-50'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                    title={mode.hint}
                  >
                    <div className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                      <span>{mode.icon}</span>
                      <span>{mode.label}</span>
                    </div>
                    <div className="text-[9px] text-slate-400 mt-0.5 truncate">{mode.hint}</div>
                  </button>
                ))}
              </div>
            </div>

            <label className={`flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-4 cursor-pointer transition-colors ${
              uploading ? 'border-brand-300 bg-brand-50' : 'border-slate-200 hover:border-brand-400 hover:bg-brand-50/50'
            }`}>
              <input type="file" multiple accept=".pdf,.xlsx,.xls,.csv,.json" onChange={handleFileUpload} className="hidden" />
              {uploading ? (
                <div className="w-full max-w-md space-y-2">
                  <div className="flex items-center justify-center gap-2 text-brand-600">
                    <div className="animate-spin w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full" />
                    <span className="text-sm">{uploadProgressText || 'Parsing & classifying...'}</span>
                  </div>
                  <div className="h-2 bg-brand-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand-500 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgressPct}%` }}
                    />
                  </div>
                  <div className="text-center text-[10px] text-brand-600 font-medium">{uploadProgressPct}%</div>
                </div>
              ) : (
                <>
                  <svg className="w-6 h-6 text-slate-300 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <span className="text-xs text-slate-500">Drop files or <span className="text-brand-600 font-medium">browse</span></span>
                  <span className="text-[10px] text-slate-400 mt-1">PDF, Excel, CSV — auto-classified by AI</span>
                </>
              )}
            </label>

            {/* Document List — Enhanced */}
            {(app.documents || []).length > 0 && (
              <div className="space-y-2">
                {app.documents.map(doc => {
                  const isExpanded = expandedDoc === doc.file_id;
                  const overrideType = docTypeOverrides[doc.file_id];
                  const confPct = doc.classification_confidence ? (doc.classification_confidence * 100).toFixed(0) : null;
                  const confColor = confPct >= 80 ? 'emerald' : confPct >= 50 ? 'amber' : 'red';
                  return (
                    <div key={doc.file_id} className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden">
                      {/* Document Header */}
                      <div className="flex items-center justify-between p-3">
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-slate-700 truncate">{doc.filename}</div>
                          <div className="flex items-center gap-2 mt-1.5">
                            {doc.confirmed ? (
                              <Badge color="emerald">✓ {doc.doc_type?.replace(/_/g, ' ')}</Badge>
                            ) : (
                              <select
                                value={overrideType || doc.doc_type}
                                onChange={e => setDocTypeOverrides(prev => ({...prev, [doc.file_id]: e.target.value}))}
                                className="text-[10px] px-1.5 py-0.5 border border-amber-300 bg-amber-50 text-amber-700 rounded font-medium outline-none cursor-pointer"
                              >
                                {DOC_TYPES.map(t => (
                                  <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                                ))}
                              </select>
                            )}
                            {confPct && !doc.confirmed && (
                              <span className={`text-[10px] font-medium text-${confColor}-600`}>
                                {confPct}% confidence
                              </span>
                            )}
                          </div>
                          {doc.classification_evidence && !doc.confirmed && (
                            <div className="text-[10px] text-slate-400 mt-1 truncate">
                              Evidence: {doc.classification_evidence}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 ml-2">
                          {!doc.confirmed && (
                            <button onClick={() => handleConfirmDoc(doc.file_id, doc.doc_type)}
                              className="text-[10px] px-2.5 py-1 bg-emerald-50 text-emerald-600 border border-emerald-200 rounded-md hover:bg-emerald-100 font-medium">
                              ✓ Confirm
                            </button>
                          )}
                          <button onClick={() => setExpandedDoc(isExpanded ? null : doc.file_id)}
                            className="text-[10px] px-2 py-1 bg-slate-100 text-slate-500 border border-slate-200 rounded-md hover:bg-slate-200">
                            {isExpanded ? '▲' : '▼'} Data
                          </button>
                        </div>
                      </div>
                      {/* Expanded Extraction View */}
                      {isExpanded && (
                        <div className="border-t border-slate-200 bg-white p-3 space-y-2">
                          {doc.parsed_summary && (
                            <div className="text-[10px] text-slate-500 bg-slate-50 rounded p-2">
                              <span className="font-semibold text-slate-600">Summary:</span> {doc.parsed_summary}
                            </div>
                          )}
                          {doc.extracted_fields && Object.keys(doc.extracted_fields).length > 0 ? (
                            <div>
                              <div className="text-[10px] font-semibold text-slate-600 mb-1">Extracted Fields</div>
                              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                                {Object.entries(doc.extracted_fields).map(([k, v]) => (
                                  <div key={k} className="flex justify-between text-[10px] py-0.5 border-b border-slate-50">
                                    <span className="text-slate-400">{k.replace(/_/g, ' ')}</span>
                                    <span className="text-slate-700 font-medium text-right ml-2 truncate max-w-[120px]">
                                      {typeof v === 'object' ? JSON.stringify(v).slice(0, 50) : String(v).slice(0, 50)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <div className="text-[10px] text-slate-400 italic">No structured fields extracted yet</div>
                          )}
                          {doc.risks_identified && doc.risks_identified.length > 0 && (
                            <div>
                              <div className="text-[10px] font-semibold text-red-500 mb-1">Risks Identified</div>
                              <div className="flex flex-wrap gap-1">
                                {doc.risks_identified.map((r, i) => (
                                  <span key={i} className="text-[10px] px-1.5 py-0.5 bg-red-50 text-red-600 rounded border border-red-100">
                                    {typeof r === 'object' ? r.risk || r.description || JSON.stringify(r) : r}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Section>

        {/* Primary Insights */}
        <Section title="Primary Insights" icon="📝" defaultOpen={true} collapsible={false}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-2">
                <select value={insightForm.note_type} onChange={e => setInsightForm(f => ({ ...f, note_type: e.target.value }))}
                  className="w-full px-2 py-1.5 border border-slate-200 rounded text-xs bg-white outline-none">
                  <option value="site_visit">Site Visit</option>
                  <option value="management_meeting">Management Meeting</option>
                  <option value="reference_check">Reference Check</option>
                  <option value="other">Other</option>
                </select>
                <textarea value={insightForm.content} onChange={e => setInsightForm(f => ({ ...f, content: e.target.value }))}
                  placeholder="Add observations..."
                  rows={2} className="w-full px-2 py-1.5 border border-slate-200 rounded text-xs outline-none resize-none" />
                <input value={insightForm.officer_name} onChange={e => setInsightForm(f => ({ ...f, officer_name: e.target.value }))}
                  placeholder="Officer name" className="w-full px-2 py-1.5 border border-slate-200 rounded text-xs outline-none" />
                <button onClick={handleAddInsight}
                  className="w-full py-1.5 text-xs font-medium text-brand-600 bg-brand-50 rounded hover:bg-brand-100 border border-brand-200">
                  + Add Insight
                </button>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {(app.primary_insights || []).map((ins, i) => (
                  <div key={i} className="bg-slate-50 rounded p-2.5 border border-slate-100">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge>{ins.note_type?.replace(/_/g, ' ')}</Badge>
                      {ins.officer_name && <span className="text-[10px] text-slate-400">by {ins.officer_name}</span>}
                    </div>
                    <p className="text-xs text-slate-600">{ins.content}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Section>
      </div>

      {/* Pipeline Action (below all inputs) */}
      <div className="flex justify-center">
        <button onClick={handleRunPipeline} disabled={pipelineRunning || uploading}
          className="px-4 py-2 text-xs font-medium text-white bg-brand-600 hover:bg-brand-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2 shadow-sm">
          {pipelineRunning ? (
            <><div className="animate-spin w-3 h-3 border-2 border-white border-t-transparent rounded-full" /> Running...</>
          ) : '⚡ Run Full Pipeline'}
        </button>
      </div>

      {/* Results */}
      <div className="space-y-5">
          {/* Explain Decision Action */}
          {rs && (
            <div className="flex justify-center">
              <button onClick={() => setShowExplain(v => !v)}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 rounded-lg transition-colors border border-slate-200 flex items-center gap-2">
                {showExplain ? '🧠 Hide Explain' : '🧠 Explain Decision'}
              </button>
            </div>
          )}

          {/* Explainability Walkthrough */}
          {rs && showExplain && (
            <Section title="Model Walkthrough" icon="🧠" defaultOpen={true}>
              <div className="space-y-4 text-xs">
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-3">
                  <h4 className="font-semibold text-slate-700 mb-1">1) Data Inputs</h4>
                  <div className="text-slate-600 space-y-1">
                    <div>Documents analyzed: <span className="font-medium">{(app.documents || []).length}</span></div>
                    <div>Primary insights used: <span className="font-medium">{(app.primary_insights || []).length}</span></div>
                    <div>Secondary research present: <span className="font-medium">{app.research && Object.keys(app.research).length > 0 ? 'Yes' : 'No'}</span></div>
                    <div>Data confidence: <span className="font-medium">{rs.explainability?.confidence || 'N/A'}</span></div>
                  </div>
                </div>

                <div className="bg-slate-50 rounded-lg border border-slate-200 p-3">
                  <h4 className="font-semibold text-slate-700 mb-1">2) Five Cs Weighted Score</h4>
                  <div className="space-y-1 text-slate-600">
                    {Object.entries(fiveCs || {}).map(([name, data]) => (
                      <div key={name} className="flex items-center justify-between">
                        <span>{name.charAt(0).toUpperCase() + name.slice(1)} ({(data.weight * 100).toFixed(0)}%)</span>
                        <span className="font-medium">{data.score} × {data.weight} = {(data.score * data.weight).toFixed(1)}</span>
                      </div>
                    ))}
                    <div className="pt-1 border-t border-slate-200 flex items-center justify-between">
                      <span>Raw Weighted Score</span>
                      <span className="font-semibold">{rs.raw_score?.toFixed(1) ?? 'N/A'}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Primary Insight Adjustment</span>
                      <span className="font-medium">{rs.insight_adjustment?.total_adjustment ?? 0}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Final Score</span>
                      <span className="font-semibold text-brand-700">{rs.overall_score?.toFixed(1) ?? 'N/A'}</span>
                    </div>
                  </div>
                </div>

                {mlPred && (
                  <div className="bg-slate-50 rounded-lg border border-slate-200 p-3">
                    <h4 className="font-semibold text-slate-700 mb-1">3) ML Default Probability Layer</h4>
                    <div className="text-slate-600 space-y-1">
                      <div>Method: <span className="font-medium">{mlPred.method || 'N/A'}</span></div>
                      <div>Probability of default (PD): <span className="font-medium">{(mlPred.probability_of_default * 100).toFixed(2)}%</span></div>
                      <div>Internal rating: <span className="font-medium">{mlPred.rating || 'N/A'}</span></div>
                      {Array.isArray(mlPred.adjustments) && mlPred.adjustments.length > 0 && (
                        <div className="pt-1">
                          <div className="text-slate-500 mb-1">Feature adjustments:</div>
                          <div className="space-y-1">
                            {mlPred.adjustments.slice(0, 8).map((adj, i) => (
                              <div key={i} className="text-[11px] text-slate-500">• {adj.detail} ({adj.impact > 0 ? '+' : ''}{adj.impact})</div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {altmanZ && (
                  <div className="bg-slate-50 rounded-lg border border-slate-200 p-3">
                    <h4 className="font-semibold text-slate-700 mb-1">4) Altman Z'' Check</h4>
                    <div className="text-slate-600">
                      Z-Score: <span className="font-medium">{altmanZ.z_score?.toFixed(3) ?? 'N/A'}</span> | Zone: <span className="font-medium">{altmanZ.zone || 'N/A'}</span>
                    </div>
                  </div>
                )}

                {displayLoanStructure && (
                  <div className="bg-slate-50 rounded-lg border border-slate-200 p-3">
                    <h4 className="font-semibold text-slate-700 mb-1">5) Loan Structuring Engine</h4>
                    <div className="text-slate-600 space-y-1">
                      <div>Requested: <span className="font-medium">₹{displayLoanStructure.requested_amount_cr?.toFixed(2) || app.loan_amount_requested}Cr</span></div>
                      <div>Recommended: <span className="font-medium">₹{displayLoanStructure.recommended_amount_cr?.toFixed(2) || 0}Cr</span></div>
                      <div>Constraining method: <span className="font-medium">{displayLoanStructure.constraining_method?.replace(/_/g, ' ') || 'N/A'}</span></div>
                      <div>Rate breakdown: <span className="font-medium">{displayLoanStructure.rate_breakdown?.explanation || 'N/A'}</span></div>
                    </div>
                  </div>
                )}

                <div className="bg-brand-50 rounded-lg border border-brand-200 p-3">
                  <h4 className="font-semibold text-brand-700 mb-1">6) Final Decision Rule</h4>
                  <div className="text-brand-700/90 space-y-1">
                    <div>Score ≥ 75: APPROVE</div>
                    <div>60–74.9: APPROVE WITH CONDITIONS</div>
                    <div>45–59.9: APPROVE REDUCED</div>
                    <div>30–44.9: REFER TO COMMITTEE</div>
                    <div>&lt; 30: REJECT</div>
                    <div className="pt-1 border-t border-brand-200 mt-1">Current output: <span className="font-semibold">{recommendation?.decision?.replace(/_/g, ' ') || 'N/A'}</span></div>
                  </div>
                </div>
              </div>
            </Section>
          )}

          {/* Risk Score */}
          {rs && (
            <Section title="Credit Risk Assessment" icon="🏦">
              <div className="space-y-4">
                {/* Score overview */}
                <div className={`${
                  scoreCardCount === 1
                    ? 'max-w-md mx-auto'
                    : scoreCardCount === 2
                      ? 'grid grid-cols-2 gap-3 max-w-4xl mx-auto'
                      : 'grid grid-cols-3 gap-3'
                }`}>
                  {mlPred && (
                    <div className="bg-gradient-to-br from-brand-50 to-brand-100 rounded-xl p-4 text-center border border-brand-200">
                      <div className="text-3xl font-bold text-brand-700">{mlPred.rating}</div>
                      <div className="text-sm text-brand-600 mt-1">Credit Rating</div>
                      <div className="text-xs text-brand-500 mt-0.5">PD: {mlPred.pd_percent?.toFixed(2)}%</div>
                    </div>
                  )}
                  {altmanZ && (
                    <div className={`rounded-xl p-4 text-center border ${
                      altmanZ.zone === 'SAFE' ? 'bg-emerald-50 border-emerald-200' :
                      altmanZ.zone === 'GREY' ? 'bg-amber-50 border-amber-200' :
                      'bg-red-50 border-red-200'
                    }`}>
                      <div className={`text-3xl font-bold ${
                        altmanZ.zone === 'SAFE' ? 'text-emerald-700' :
                        altmanZ.zone === 'GREY' ? 'text-amber-700' : 'text-red-700'
                      }`}>{altmanZ.z_score?.toFixed(2)}</div>
                      <div className="text-sm opacity-70 mt-1">Altman Z''-Score</div>
                      <div className="text-xs opacity-60 mt-0.5">{altmanZ.zone} Zone</div>
                    </div>
                  )}
                  {recommendation && (
                    <div className={`rounded-xl p-4 text-center border ${
                      recommendation.decision?.includes('APPROVE') ? 'bg-emerald-50 border-emerald-200' :
                      recommendation.decision?.includes('REVIEW') ? 'bg-amber-50 border-amber-200' :
                      'bg-red-50 border-red-200'
                    }`}>
                      <div className={`text-sm font-bold ${
                        recommendation.decision?.includes('APPROVE') ? 'text-emerald-700' :
                        recommendation.decision?.includes('REVIEW') ? 'text-amber-700' : 'text-red-700'
                      }`}>{recommendation.decision?.replace(/_/g, ' ')}</div>
                      <div className="text-sm opacity-70 mt-2">Decision</div>
                      {recommendation.interest_rate_pct && (
                        <div className="text-xs opacity-60 mt-0.5">
                          ₹{recommendation.suggested_loan_amount?.toFixed(1)}Cr @ {recommendation.interest_rate_pct?.toFixed(2)}%
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Five Cs Breakdown */}
                {fiveCs && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-slate-600">Five Cs Framework</h4>
                    {['Character', 'Capacity', 'Capital', 'Collateral', 'Conditions'].map(c => {
                      const data = fiveCs[c.toLowerCase()];
                      if (!data) return null;
                      return (
                        <div key={c} className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                          <ScoreBar label={c} score={data.score} />
                          {data.reasons && data.reasons.length > 0 && (
                            <div className="mt-2 pl-[108px] space-y-1">
                              {data.reasons.slice(0, 3).map((r, i) => (
                                <div key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                                  <span className="mt-0.5 flex-shrink-0">{data.score >= 60 ? '✓' : '⚠'}</span>
                                  <span>{r}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Decision Justification */}
                {recommendation?.explanation && (
                  <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                    <h4 className="text-xs font-semibold text-slate-500 mb-2">Decision Rationale</h4>
                    <p className="text-xs text-slate-600 leading-relaxed">{recommendation.explanation}</p>
                    {recommendation.strongest_factor && (
                      <div className="mt-2 flex gap-4">
                        <span className="text-[10px] text-emerald-600">Strongest: {recommendation.strongest_factor?.replace(/_/g, ' ')}</span>
                        {recommendation.weakest_factor && (
                          <span className="text-[10px] text-red-500">Weakest: {recommendation.weakest_factor?.replace(/_/g, ' ')}</span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* ML Feature Importance */}
                {mlPred?.top_factors && (
                  <div>
                    <h4 className="text-xs font-semibold text-slate-500 mb-2">Key Risk Factors</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {mlPred.top_factors.slice(0, 6).map((f, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs bg-slate-50 rounded p-2">
                          <span className={`w-2 h-2 rounded-full ${f.direction === 'positive' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                          <span className="text-slate-600">{f.feature?.replace(/_/g, ' ')}</span>
                          <span className="ml-auto font-medium text-slate-500">{f.impact?.toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Covenants */}
                {recommendation?.covenants && recommendation.covenants.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-slate-500 mb-2">Proposed Covenants</h4>
                    <div className="space-y-1.5">
                      {recommendation.covenants.map((cov, i) => (
                        <div key={i} className="flex items-start gap-2 text-xs bg-amber-50 rounded-lg p-2.5 border border-amber-100">
                          <span className="text-amber-500 mt-0.5 flex-shrink-0">⚖</span>
                          <div>
                            <span className="text-amber-800">{cov.covenant}</span>
                            {cov.current_value && (
                              <span className="text-amber-500 ml-2">
                                (Current: {typeof cov.current_value === 'number' ? cov.current_value.toFixed(2) : cov.current_value})
                              </span>
                            )}
                          </div>
                          <Badge color={cov.priority === 'mandatory' ? 'red' : 'amber'}>{cov.priority}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Section>
          )}

          {/* Loan Structure */}
          {displayLoanStructure && (
            <LoanStructureCard structure={displayLoanStructure} />
          )}

          {/* SWOT */}
          {app.swot && (
            <Section title="SWOT Analysis" icon="💡">
              <SWOTGrid swot={app.swot} />
            </Section>
          )}

          {/* Triangulation */}
          {app.triangulation && (
            <Section title="Data Triangulation" icon="🔗">
              <div className="space-y-3">
                {(() => {
                  const checks = Array.isArray(app.triangulation.checks) ? app.triangulation.checks : [];
                  const confirmed = checks.filter(c => c.status === 'confirmed').length;
                  const discrepancies = checks.filter(c => c.status === 'discrepancy').length;
                  const insufficient = checks.filter(c => c.status === 'insufficient_data').length;

                  const integrityClass =
                    app.triangulation.data_integrity === 'HIGH' ? 'bg-emerald-100 text-emerald-700' :
                    app.triangulation.data_integrity === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                    app.triangulation.data_integrity === 'MODERATE' ? 'bg-blue-100 text-blue-700' :
                    'bg-red-100 text-red-700';

                  const statusMeta = (status) => {
                    if (status === 'confirmed') {
                      return {
                        icon: '✅',
                        label: 'Confirmed',
                        rowClass: 'bg-emerald-50 border-emerald-100',
                        badgeColor: 'emerald',
                      };
                    }
                    if (status === 'discrepancy') {
                      return {
                        icon: '⚠️',
                        label: 'Discrepancy',
                        rowClass: 'bg-amber-50 border-amber-100',
                        badgeColor: 'amber',
                      };
                    }
                    return {
                      icon: 'ℹ️',
                      label: 'Insufficient Data',
                      rowClass: 'bg-slate-50 border-slate-100',
                      badgeColor: 'slate',
                    };
                  };

                  return (
                    <>
                      <div className="flex items-center justify-between gap-4 flex-wrap">
                        <div className="flex items-center gap-3">
                          <div className={`px-3 py-1.5 rounded-lg text-sm font-semibold ${integrityClass}`}>
                            {app.triangulation.data_integrity} Integrity
                          </div>
                          <span className="text-sm text-slate-600">
                            Confidence: <span className="font-semibold">{app.triangulation.overall_confidence_pct?.toFixed(1)}%</span>
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px]">
                          <span className="px-2 py-1 rounded bg-emerald-50 text-emerald-700">✅ {confirmed} confirmed</span>
                          <span className="px-2 py-1 rounded bg-amber-50 text-amber-700">⚠️ {discrepancies} discrepancy</span>
                          <span className="px-2 py-1 rounded bg-slate-50 text-slate-600">ℹ️ {insufficient} insufficient</span>
                        </div>
                      </div>

                      {app.triangulation.summary && (
                        <div className="bg-slate-50 border border-slate-100 rounded-lg p-2.5 text-[11px] text-slate-600 leading-relaxed whitespace-pre-line">
                          {app.triangulation.summary}
                        </div>
                      )}

                      {checks.length > 0 && (
                        <div className="space-y-2">
                          {checks.map((chk, i) => {
                            const meta = statusMeta(chk.status);
                            return (
                              <div key={i} className={`flex items-center justify-between p-3 rounded-lg border ${meta.rowClass}`}>
                                <div className="flex items-start gap-2">
                                  <span>{meta.icon}</span>
                                  <div>
                                    <div className="text-xs font-medium text-slate-700">{chk.check?.replace(/_/g, ' ')}</div>
                                    <div className="text-[10px] text-slate-500">{chk.detail}</div>
                                  </div>
                                </div>
                                <Badge color={meta.badgeColor}>{meta.label}</Badge>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            </Section>
          )}

          {/* Research */}
          {app.research && Object.keys(app.research).length > 0 && (
            <Section title="Secondary Research" icon="🔍" defaultOpen={false}>
              <div className="space-y-3">
                {app.research.research_summary && (
                  <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-700 leading-relaxed">
                    {cleanResearchText(app.research.research_summary)}
                  </div>
                )}
                {app.research.news_sentiment?.sentiment && (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-600">Sentiment:</span>
                    <Badge color={
                      app.research.news_sentiment.sentiment.label === 'POSITIVE' ? 'emerald' :
                      app.research.news_sentiment.sentiment.label === 'NEGATIVE' ? 'red' : 'amber'
                    }>
                      {app.research.news_sentiment.sentiment.label}
                    </Badge>
                    <span className="text-sm text-slate-500">
                      Score: {app.research.news_sentiment.sentiment.score?.toFixed(2)}
                    </span>
                  </div>
                )}
                {app.research.litigation_check && (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-600">Litigation Risk:</span>
                    <Badge color={
                      app.research.litigation_check.litigation_risk === 'LOW' ? 'emerald' :
                      app.research.litigation_check.litigation_risk === 'MEDIUM' ? 'amber' : 'red'
                    }>
                      {app.research.litigation_check.litigation_risk}
                    </Badge>
                  </div>
                )}
                {app.research.news_sentiment?.company_news && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-600 mb-2">News Headlines</h4>
                    {app.research.news_sentiment.company_news.map((n, i) => (
                      <div key={i} className="text-sm text-slate-700 p-2 border-l-2 border-slate-200 ml-1 mb-2">
                        <div className="font-medium">{cleanResearchText(n.title)}</div>
                        <div className="text-slate-500 mt-0.5">{cleanResearchText(n.snippet)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Section>
          )}

          {/* Parsed Data Summary */}
          {app.parsed_data && Object.keys(app.parsed_data).length > 0 && (
            <Section title="Parsed Document Data" icon="📋" defaultOpen={false}>
              <div className="space-y-3">
                {Object.entries(app.parsed_data).map(([docType, data]) => (
                  <div key={docType} className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-slate-700">{String(docType || '').replace(/_/g, ' ') || 'document'}</span>
                      <div className="flex items-center gap-2">
                        {data?.parse_mode && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                            {data.parse_mode === 'fast' ? '⚡ Fast' : data.parse_mode === 'max_coverage' ? '🔍 Max Coverage' : '⚖️ Balanced'}
                          </span>
                        )}
                        {data?.summary && <span className="text-[10px] text-slate-400">{data.summary}</span>}
                      </div>
                    </div>
                    {data?.fields && typeof data.fields === 'object' && (
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                        {Object.entries(data.fields).slice(0, 10).map(([k, v]) => (
                          <div key={k} className="flex justify-between text-[10px]">
                            <span className="text-slate-500">{k.replace(/_/g, ' ')}</span>
                            <span className="text-slate-700 font-medium">
                              {typeof v === 'object' ? JSON.stringify(v).slice(0, 40) : String(v)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                    {Array.isArray(data?.risks) && data.risks.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {data.risks.map((r, i) => (
                          <span key={i} className="text-[10px] px-1.5 py-0.5 bg-red-50 text-red-600 rounded">
                            {typeof r === 'object' ? (r.detail || r.type || JSON.stringify(r)) : String(r)}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Embedded visuals OCR (images/graphs inside PDF) */}
                    {data?.visual_extraction && (
                      <div className="mt-3 bg-white rounded-lg border border-slate-200 p-2.5">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10px] font-semibold text-slate-600">Image/Graph OCR</span>
                          <span className="text-[9px] text-slate-400">
                            elements: {Array.isArray(data.visual_extraction.elements) ? data.visual_extraction.elements.length : 0}
                          </span>
                        </div>

                        {data.visual_extraction.enabled === false && data.visual_extraction.reason && (
                          <div className="text-[10px] text-amber-700 bg-amber-50 border border-amber-100 rounded p-2">
                            OCR not available: {data.visual_extraction.reason}
                          </div>
                        )}

                        {Array.isArray(data.visual_extraction.elements) && data.visual_extraction.elements.length > 0 && (
                          <div className="space-y-1 max-h-44 overflow-y-auto pr-1">
                            {data.visual_extraction.elements.slice(0, 12).map((el, idx) => (
                              <div key={idx} className="text-[10px] bg-slate-50 rounded p-1.5 border border-slate-100">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-medium text-slate-600">{(el.kind || 'image').replace(/_/g, ' ')}</span>
                                  <span className="text-slate-400">p.{el.page || '-'}</span>
                                </div>
                                <div className="text-slate-700 truncate mt-0.5">{String(el.ocr_text || '').slice(0, 140)}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Open-schema dynamic extraction (RAG) */}
                    {data?.dynamic_extraction && (
                      <div className="mt-3 bg-white rounded-lg border border-slate-200 p-2.5">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10px] font-semibold text-slate-600">All Retrieved Facts (RAG)</span>
                          {data.dynamic_extraction._rag_meta?.chunks_used && (
                            <span className="text-[9px] text-slate-400">
                              chunks: {data.dynamic_extraction._rag_meta.chunks_used}/{data.dynamic_extraction._rag_meta.chunks_considered || '-'}
                            </span>
                          )}
                        </div>

                        {data.dynamic_extraction.document_summary && (
                          <p className="text-[10px] text-slate-500 leading-relaxed mb-2">
                            {data.dynamic_extraction.document_summary}
                          </p>
                        )}

                        {Array.isArray(data.dynamic_extraction.key_facts) && data.dynamic_extraction.key_facts.length > 0 && (
                          <div className="space-y-1 max-h-44 overflow-y-auto pr-1">
                            {data.dynamic_extraction.key_facts.slice(0, 15).map((fact, idx) => (
                              <div key={idx} className="text-[10px] bg-slate-50 rounded p-1.5 border border-slate-100">
                                <div className="flex items-start justify-between gap-2">
                                  <span className="font-medium text-slate-600">{fact.key || 'fact'}</span>
                                  {fact.page && <span className="text-slate-400">p.{fact.page}</span>}
                                </div>
                                <div className="text-slate-700">{String(fact.value ?? '')} {fact.unit || ''}</div>
                                {fact.evidence && <div className="text-slate-400 truncate">evidence: {fact.evidence}</div>}
                              </div>
                            ))}
                          </div>
                        )}

                        {Array.isArray(data.dynamic_extraction.risk_signals) && data.dynamic_extraction.risk_signals.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {data.dynamic_extraction.risk_signals.slice(0, 8).map((sig, idx) => (
                              <span key={idx} className={`text-[10px] px-1.5 py-0.5 rounded border ${
                                sig.severity === 'critical' ? 'bg-red-50 text-red-700 border-red-100' :
                                sig.severity === 'high' ? 'bg-amber-50 text-amber-700 border-amber-100' :
                                'bg-slate-50 text-slate-600 border-slate-100'
                              }`}>
                                {sig.signal || 'risk'}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}
      </div>
    </div>
  );
}
