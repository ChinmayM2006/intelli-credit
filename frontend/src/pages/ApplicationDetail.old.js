import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  getApplication, uploadDocument, analyzeStructured,
  runResearch, addPrimaryInsight, calculateScore,
  generateCAM, downloadCAM
} from '../api';

const STEPS = [
  { key: 'upload', label: 'Upload Documents', num: 1 },
  { key: 'analyze', label: 'Analyze Data', num: 2 },
  { key: 'research', label: 'Research Agent', num: 3 },
  { key: 'insights', label: 'Primary Insights', num: 4 },
  { key: 'score', label: 'Risk Scoring', num: 5 },
  { key: 'cam', label: 'Generate CAM', num: 6 },
];

const DOC_TYPES = [
  { value: 'gst', label: 'GST Returns (GSTR-2A / 3B)' },
  { value: 'itr', label: 'Income Tax Return' },
  { value: 'bank_statement', label: 'Bank Statement' },
  { value: 'annual_report', label: 'Annual Report' },
  { value: 'financial_statement', label: 'Financial Statement' },
  { value: 'board_minutes', label: 'Board Meeting Minutes' },
  { value: 'rating_report', label: 'Rating Agency Report' },
  { value: 'shareholding', label: 'Shareholding Pattern' },
  { value: 'sanction_letter', label: 'Sanction Letter (Other Banks)' },
  { value: 'legal_notice', label: 'Legal Notice / Dispute' },
  { value: 'other', label: 'Other Document' },
];

function ApplicationDetail() {
  const { id } = useParams();
  const [app, setApp] = useState(null);
  const [activeStep, setActiveStep] = useState('upload');
  const [loading, setLoading] = useState({});
  const [uploadDocType, setUploadDocType] = useState('gst');
  const [uploadResult, setUploadResult] = useState(null);
  const [researchForm, setResearchForm] = useState({ promoters: '', industry: '' });
  const [insightForm, setInsightForm] = useState({ note_type: 'factory_visit', content: '', officer_name: '' });
  const [analysisResult, setAnalysisResult] = useState(null);
  const [researchResult, setResearchResult] = useState(null);

  const loadApp = useCallback(async () => {
    try {
      const res = await getApplication(id);
      setApp(res.data);
      if (res.data.industry) setResearchForm(f => ({ ...f, industry: res.data.industry }));
    } catch (err) {
      console.error(err);
    }
  }, [id]);

  useEffect(() => { loadApp(); }, [loadApp]);

  if (!app) return <div className="loading"><div className="spinner"></div> Loading application...</div>;

  const setStepLoading = (step, val) => setLoading(p => ({ ...p, [step]: val }));

  // Handlers
  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setStepLoading('upload', true);
    setUploadResult(null);
    try {
      const res = await uploadDocument(id, uploadDocType, file);
      setUploadResult(res.data);
      await loadApp();
    } catch (err) {
      alert('Upload failed: ' + (err.response?.data?.detail || err.message));
    }
    setStepLoading('upload', false);
  };

  const handleAnalyze = async () => {
    setStepLoading('analyze', true);
    try {
      const res = await analyzeStructured(id);
      setAnalysisResult(res.data);
      await loadApp();
    } catch (err) {
      alert('Analysis failed');
    }
    setStepLoading('analyze', false);
  };

  const handleResearch = async () => {
    setStepLoading('research', true);
    try {
      const promoterNames = researchForm.promoters ? researchForm.promoters.split(',').map(s => s.trim()) : [];
      const res = await runResearch(id, app.company_name, promoterNames, researchForm.industry);
      setResearchResult(res.data);
      await loadApp();
    } catch (err) {
      alert('Research failed');
    }
    setStepLoading('research', false);
  };

  const handleAddInsight = async () => {
    if (!insightForm.content) return;
    setStepLoading('insights', true);
    try {
      await addPrimaryInsight(id, insightForm.note_type, insightForm.content, insightForm.officer_name);
      setInsightForm({ note_type: 'factory_visit', content: '', officer_name: '' });
      await loadApp();
    } catch (err) {
      alert('Failed to add insight');
    }
    setStepLoading('insights', false);
  };

  const handleScore = async () => {
    setStepLoading('score', true);
    try {
      await calculateScore(id);
      await loadApp();
    } catch (err) {
      alert('Scoring failed');
    }
    setStepLoading('score', false);
  };

  const handleGenerateCAM = async () => {
    setStepLoading('cam', true);
    try {
      await generateCAM(id);
      await loadApp();
    } catch (err) {
      alert('CAM generation failed');
    }
    setStepLoading('cam', false);
  };

  const getStepStatus = (step) => {
    const s = app.status;
    const order = { created: 0, documents_uploaded: 1, research_complete: 2, scored: 3, cam_generated: 4 };
    const stepOrder = { upload: 0, analyze: 1, research: 2, insights: 2, score: 3, cam: 4 };
    const appOrder = order[s] || 0;
    const sOrder = stepOrder[step] || 0;
    if (appOrder > sOrder) return 'completed';
    return '';
  };

  const scoreColor = (score) => {
    if (score >= 60) return 'var(--success)';
    if (score >= 40) return 'var(--warning)';
    return 'var(--danger)';
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 24, color: 'var(--primary)' }}>{app.company_name}</h2>
          <p style={{ color: 'var(--text-light)', fontSize: 14 }}>
            ID: {app.id} | Industry: {app.industry || 'N/A'} | CIN: {app.cin || 'N/A'}
          </p>
          {app.loan_amount_requested && (
            <p style={{ fontSize: 16, fontWeight: 600, marginTop: 4 }}>
              Loan Requested: ₹{app.loan_amount_requested.toLocaleString()}
              {app.loan_purpose && ` — ${app.loan_purpose}`}
            </p>
          )}
        </div>
        {app.risk_score && (
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 36, fontWeight: 800, color: scoreColor(app.risk_score.overall_score) }}>
              {app.risk_score.overall_score}
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--primary)' }}>
              Grade: {app.risk_score.grade}
            </div>
          </div>
        )}
      </div>

      {/* Pipeline */}
      <div className="pipeline">
        {STEPS.map(step => (
          <div
            key={step.key}
            className={`pipeline-step ${activeStep === step.key ? 'active' : ''} ${getStepStatus(step.key)}`}
            onClick={() => setActiveStep(step.key)}
          >
            <div className="pipeline-step-number">{step.num}</div>
            <div className="pipeline-step-label">{step.label}</div>
          </div>
        ))}
      </div>

      {/* Step Content */}
      {activeStep === 'upload' && (
        <div className="card">
          <div className="card-header">
            <h2>📄 Upload Documents</h2>
            <span className="badge badge-info">{app.documents?.length || 0} uploaded</span>
          </div>
          <p style={{ color: 'var(--text-light)', fontSize: 14, marginBottom: 16 }}>
            Upload financial documents (PDF, Excel, CSV). The AI will automatically extract key fields, amounts, and risk indicators.
          </p>
          <div className="form-row" style={{ marginBottom: 16 }}>
            <div className="form-group">
              <label>Document Type</label>
              <select value={uploadDocType} onChange={e => setUploadDocType(e.target.value)}>
                {DOC_TYPES.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Select File</label>
              <input type="file" accept=".pdf,.xlsx,.xls,.csv" onChange={handleUpload} disabled={loading.upload} />
            </div>
          </div>
          {loading.upload && <div className="loading"><div className="spinner"></div> Parsing document with AI...</div>}
          {uploadResult && (
            <div className="alert alert-success">
              <strong>Document parsed successfully!</strong><br />
              Summary: {uploadResult.parsed?.summary}<br />
              Risks found: {uploadResult.parsed?.risks?.length || 0}
            </div>
          )}

          {/* Uploaded documents table */}
          {app.documents?.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <h3 style={{ fontSize: 16, marginBottom: 12 }}>Uploaded Documents</h3>
              <table>
                <thead>
                  <tr><th>Type</th><th>File</th><th>Summary</th><th>Risks</th></tr>
                </thead>
                <tbody>
                  {app.documents.map((doc, i) => (
                    <tr key={i}>
                      <td><span className="badge badge-info">{doc.doc_type?.replace('_', ' ')}</span></td>
                      <td>{doc.filename}</td>
                      <td style={{ fontSize: 13 }}>{doc.parsed_summary}</td>
                      <td>
                        {doc.risks_identified?.length > 0 ? (
                          <span className="badge badge-danger">{doc.risks_identified.length} risks</span>
                        ) : (
                          <span className="badge badge-success">Clean</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeStep === 'analyze' && (
        <div className="card">
          <div className="card-header">
            <h2>🔍 Structured Data Analysis</h2>
          </div>
          <p style={{ color: 'var(--text-light)', fontSize: 14, marginBottom: 16 }}>
            Cross-reference GST returns against bank statements to identify circular trading, revenue inflation, or data inconsistencies.
          </p>
          <button className="btn btn-primary" onClick={handleAnalyze} disabled={loading.analyze}>
            {loading.analyze ? 'Analyzing...' : 'Run Cross-Reference Analysis'}
          </button>
          {loading.analyze && <div className="loading"><div className="spinner"></div> Analyzing structured data...</div>}
          {(analysisResult || app.parsed_data?.structured_analysis) && (
            <div style={{ marginTop: 20 }}>
              {(() => {
                const data = analysisResult || app.parsed_data?.structured_analysis;
                const crossRef = data?.cross_reference;
                return (
                  <>
                    {crossRef && (
                      <div className="alert alert-info">
                        <strong>GST vs Bank Cross-Reference</strong><br />
                        Consistency Score: <strong>{crossRef.consistency_score}/100</strong><br />
                        {crossRef.recommendation}
                      </div>
                    )}
                    {crossRef?.flags?.map((flag, i) => (
                      <div key={i} className="risk-item">
                        <span className={`risk-severity ${flag.severity?.toLowerCase()}`}>{flag.severity}</span>
                        <div>
                          <strong>{flag.type?.replace('_', ' ')}</strong>
                          <p style={{ fontSize: 13, margin: '4px 0 0' }}>{flag.detail}</p>
                          {flag.explanation && <p style={{ fontSize: 12, color: 'var(--text-light)' }}>{flag.explanation}</p>}
                        </div>
                      </div>
                    ))}
                    <details style={{ marginTop: 12 }}>
                      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>View Raw Analysis</summary>
                      <pre className="json-viewer">{JSON.stringify(data, null, 2)}</pre>
                    </details>
                  </>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {activeStep === 'research' && (
        <div className="card">
          <div className="card-header">
            <h2>🔎 Research Agent — "Digital Credit Manager"</h2>
          </div>
          <p style={{ color: 'var(--text-light)', fontSize: 14, marginBottom: 16 }}>
            Automatically research news, MCA filings, litigation history, and sector trends for the company.
          </p>
          <div className="form-row" style={{ marginBottom: 16 }}>
            <div className="form-group">
              <label>Promoter Names (comma-separated)</label>
              <input
                type="text"
                placeholder="e.g., Mukesh Ambani, Nita Ambani"
                value={researchForm.promoters}
                onChange={e => setResearchForm({ ...researchForm, promoters: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Industry</label>
              <input
                type="text"
                value={researchForm.industry}
                onChange={e => setResearchForm({ ...researchForm, industry: e.target.value })}
              />
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleResearch} disabled={loading.research}>
            {loading.research ? 'Researching...' : '🤖 Run AI Research Agent'}
          </button>
          {loading.research && <div className="loading"><div className="spinner"></div> Agent is crawling the web...</div>}
          {(researchResult || app.research?.company_name) && (
            <div style={{ marginTop: 20 }}>
              {(() => {
                const data = researchResult || app.research;
                return (
                  <>
                    {/* Summary */}
                    {data.research_summary && (
                      <div className="alert alert-info" style={{ whiteSpace: 'pre-line' }}>
                        {data.research_summary}
                      </div>
                    )}

                    {/* Sentiment */}
                    {data.news_sentiment?.sentiment && (
                      <div style={{ marginBottom: 16 }}>
                        <h3 style={{ fontSize: 15 }}>News Sentiment</h3>
                        <span
                          className={`badge ${
                            data.news_sentiment.sentiment.label === 'POSITIVE' ? 'badge-success' :
                            data.news_sentiment.sentiment.label === 'NEGATIVE' ? 'badge-danger' : 'badge-warning'
                          }`}
                          style={{ fontSize: 14, marginTop: 4 }}
                        >
                          {data.news_sentiment.sentiment.label} (Score: {data.news_sentiment.sentiment.score})
                        </span>
                      </div>
                    )}

                    {/* Litigation */}
                    {data.litigation_check && (
                      <div style={{ marginBottom: 16 }}>
                        <h3 style={{ fontSize: 15 }}>Litigation Check</h3>
                        <span className={`badge ${
                          data.litigation_check.litigation_risk === 'LOW' ? 'badge-success' :
                          data.litigation_check.litigation_risk === 'MEDIUM' ? 'badge-warning' : 'badge-danger'
                        }`} style={{ fontSize: 14 }}>
                          Risk: {data.litigation_check.litigation_risk}
                        </span>
                        {data.litigation_check.search_results?.map((r, i) => (
                          <div key={i} style={{ marginTop: 8, padding: 8, background: 'var(--bg)', borderRadius: 8 }}>
                            <strong style={{ fontSize: 13 }}>{r.title}</strong>
                            <p style={{ fontSize: 12, color: 'var(--text-light)' }}>{r.snippet}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Risk Flags */}
                    {data.overall_risk_flags?.length > 0 && (
                      <div>
                        <h3 style={{ fontSize: 15, marginBottom: 8 }}>Risk Flags from Research</h3>
                        {data.overall_risk_flags.map((f, i) => (
                          <div key={i} className="risk-item">
                            <span className={`risk-severity ${f.severity?.toLowerCase()}`}>{f.severity}</span>
                            <div>{f.detail}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    <details style={{ marginTop: 12 }}>
                      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>View Full Research Data</summary>
                      <pre className="json-viewer">{JSON.stringify(data, null, 2)}</pre>
                    </details>
                  </>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {activeStep === 'insights' && (
        <div className="card">
          <div className="card-header">
            <h2>📝 Primary Insights (Due Diligence)</h2>
            <span className="badge badge-info">{app.primary_insights?.length || 0} insights</span>
          </div>
          <p style={{ color: 'var(--text-light)', fontSize: 14, marginBottom: 16 }}>
            Credit officers can input qualitative notes from factory visits, management interviews, or other due diligence.
            The AI adjusts the risk score based on these observations.
          </p>
          <div className="form-row">
            <div className="form-group">
              <label>Insight Type</label>
              <select value={insightForm.note_type} onChange={e => setInsightForm({ ...insightForm, note_type: e.target.value })}>
                <option value="factory_visit">Factory / Site Visit</option>
                <option value="management_interview">Management Interview</option>
                <option value="other">Other Observation</option>
              </select>
            </div>
            <div className="form-group">
              <label>Officer Name</label>
              <input
                type="text"
                value={insightForm.officer_name}
                onChange={e => setInsightForm({ ...insightForm, officer_name: e.target.value })}
                placeholder="Your name"
              />
            </div>
          </div>
          <div className="form-group">
            <label>Observation / Note</label>
            <textarea
              value={insightForm.content}
              onChange={e => setInsightForm({ ...insightForm, content: e.target.value })}
              placeholder='e.g., "Factory found operating at 40% capacity. Only 2 of 5 production lines active. Inventory piling up in the warehouse."'
              rows={4}
            />
          </div>
          <button className="btn btn-primary" onClick={handleAddInsight} disabled={loading.insights || !insightForm.content}>
            {loading.insights ? 'Adding...' : 'Add Insight'}
          </button>

          {app.primary_insights?.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <h3 style={{ fontSize: 15, marginBottom: 12 }}>Recorded Insights</h3>
              {app.primary_insights.map((ins, i) => (
                <div key={i} style={{ padding: 12, background: 'var(--bg)', borderRadius: 8, marginBottom: 8, borderLeft: '4px solid var(--primary)' }}>
                  <div style={{ fontSize: 12, color: 'var(--text-light)', marginBottom: 4 }}>
                    <strong>{ins.note_type?.replace('_', ' ').toUpperCase()}</strong>
                    {ins.officer_name && ` — ${ins.officer_name}`}
                    {ins.added_at && ` — ${new Date(ins.added_at).toLocaleString()}`}
                  </div>
                  <p style={{ fontSize: 14 }}>{ins.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeStep === 'score' && (
        <div className="card">
          <div className="card-header">
            <h2>📊 Risk Scoring — Five Cs of Credit</h2>
          </div>
          <p style={{ color: 'var(--text-light)', fontSize: 14, marginBottom: 16 }}>
            Calculate a comprehensive, explainable credit risk score using the Five Cs framework (Character, Capacity, Capital, Collateral, Conditions).
          </p>
          <button className="btn btn-primary" onClick={handleScore} disabled={loading.score}>
            {loading.score ? 'Calculating...' : '🧠 Calculate Risk Score'}
          </button>
          {loading.score && <div className="loading"><div className="spinner"></div> Running ML scoring model...</div>}

          {app.risk_score && (
            <div style={{ marginTop: 20 }}>
              {/* Score overview */}
              <div className="grid-3" style={{ marginBottom: 24 }}>
                <div className="card" style={{ textAlign: 'center' }}>
                  <div
                    className="score-circle"
                    style={{ background: scoreColor(app.risk_score.overall_score) }}
                  >
                    {app.risk_score.overall_score}
                  </div>
                  <div className="score-grade">Grade: {app.risk_score.grade}</div>
                </div>
                <div className="card">
                  <h3 style={{ fontSize: 14, color: 'var(--text-light)', marginBottom: 12 }}>Decision</h3>
                  <div
                    className={`decision-badge ${
                      app.risk_score.recommendation.decision.includes('APPROVE') && !app.risk_score.recommendation.decision.includes('REDUCED')
                        ? 'decision-approve'
                        : app.risk_score.recommendation.decision === 'REJECT'
                        ? 'decision-reject'
                        : 'decision-conditional'
                    }`}
                  >
                    {app.risk_score.recommendation.decision.replace(/_/g, ' ')}
                  </div>
                  {app.risk_score.recommendation.suggested_loan_amount > 0 && (
                    <p style={{ marginTop: 12, fontSize: 14 }}>
                      <strong>Suggested Amount:</strong> ₹{app.risk_score.recommendation.suggested_loan_amount.toLocaleString()}
                    </p>
                  )}
                  {app.risk_score.recommendation.risk_premium_pct && (
                    <p style={{ fontSize: 14 }}>
                      <strong>Risk Premium:</strong> {app.risk_score.recommendation.risk_premium_pct}%
                    </p>
                  )}
                </div>
                <div className="card">
                  <h3 style={{ fontSize: 14, color: 'var(--text-light)', marginBottom: 12 }}>Confidence</h3>
                  <p style={{ fontSize: 20, fontWeight: 700 }}>{app.risk_score.explainability?.confidence || 'N/A'}</p>
                  <p style={{ fontSize: 12, color: 'var(--text-light)', marginTop: 4 }}>
                    Based on {app.risk_score.explainability?.data_sources?.length || 0} data sources
                  </p>
                </div>
              </div>

              {/* Five Cs Bars */}
              <div className="card">
                <h3 style={{ fontSize: 16, marginBottom: 16, color: 'var(--primary)' }}>Five Cs Breakdown</h3>
                {Object.entries(app.risk_score.five_cs || {}).map(([name, data]) => (
                  <div key={name} className="five-cs-bar">
                    <div className="five-cs-bar-label">
                      <span>{name.charAt(0).toUpperCase() + name.slice(1)} ({(data.weight * 100).toFixed(0)}%)</span>
                      <span>{data.score}/100</span>
                    </div>
                    <div className="five-cs-bar-track">
                      <div
                        className="five-cs-bar-fill"
                        style={{
                          width: `${data.score}%`,
                          background: data.score >= 60 ? 'var(--success)' : data.score >= 40 ? 'var(--warning)' : 'var(--danger)',
                        }}
                      >
                        {data.score}
                      </div>
                    </div>
                    {data.reasons?.length > 0 && (
                      <ul style={{ fontSize: 12, color: 'var(--text-light)', margin: '4px 0 8px 16px' }}>
                        {data.reasons.map((r, i) => <li key={i}>{r}</li>)}
                      </ul>
                    )}
                  </div>
                ))}
              </div>

              {/* Explanation */}
              <div className="card" style={{ marginTop: 16 }}>
                <h3 style={{ fontSize: 16, marginBottom: 12, color: 'var(--primary)' }}>Explainability</h3>
                <p style={{ fontSize: 14 }}>{app.risk_score.recommendation.explanation}</p>
                {app.risk_score.recommendation.conditions?.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <h4 style={{ fontSize: 14, marginBottom: 8 }}>Conditions:</h4>
                    <ul style={{ fontSize: 13, paddingLeft: 20 }}>
                      {app.risk_score.recommendation.conditions.map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                  </div>
                )}
              </div>

              {/* All Risks */}
              {app.risk_score.all_risks?.length > 0 && (
                <div className="card" style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 16, marginBottom: 12, color: 'var(--danger)' }}>
                    All Identified Risks ({app.risk_score.all_risks.length})
                  </h3>
                  {app.risk_score.all_risks.map((risk, i) => (
                    <div key={i} className="risk-item">
                      <span className={`risk-severity ${risk.severity?.toLowerCase()}`}>{risk.severity}</span>
                      <div>
                        <strong style={{ fontSize: 13 }}>{risk.category?.toUpperCase()} — {risk.type}</strong>
                        <p style={{ fontSize: 12, margin: '2px 0 0' }}>{risk.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeStep === 'cam' && (
        <div className="card">
          <div className="card-header">
            <h2>📋 Credit Appraisal Memo (CAM)</h2>
          </div>
          <p style={{ color: 'var(--text-light)', fontSize: 14, marginBottom: 16 }}>
            Generate a professional, structured Credit Appraisal Memo (PDF) summarizing all findings,
            the Five Cs analysis, risk matrix, and lending recommendation.
          </p>
          {!app.risk_score ? (
            <div className="alert alert-warning">
              Please complete risk scoring (Step 5) before generating the CAM.
            </div>
          ) : (
            <>
              <button className="btn btn-success" onClick={handleGenerateCAM} disabled={loading.cam}>
                {loading.cam ? 'Generating PDF...' : '📄 Generate CAM PDF'}
              </button>
              {loading.cam && <div className="loading"><div className="spinner"></div> Building professional CAM document...</div>}
            </>
          )}
          {app.cam_path && (
            <div style={{ marginTop: 20 }}>
              <div className="alert alert-success">
                <strong>CAM Generated Successfully!</strong><br />
                Your Credit Appraisal Memo is ready for download.
              </div>
              <a href={downloadCAM(id)} target="_blank" rel="noopener noreferrer" className="btn btn-primary">
                📥 Download CAM (PDF)
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ApplicationDetail;
