import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createApplication } from '../api';

function NewApplication() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    company_name: '',
    cin: '',
    industry: '',
    loan_amount_requested: '',
    loan_purpose: '',
  });
  const [loading, setLoading] = useState(false);

  const industries = [
    'Manufacturing', 'Infrastructure', 'Real Estate', 'NBFC / Financial Services',
    'IT / Software', 'Pharmaceuticals', 'Textiles', 'Agriculture / Agri-business',
    'Chemicals', 'Steel / Metals', 'FMCG', 'Automotive', 'Energy / Power',
    'Telecom', 'Healthcare', 'Education', 'Logistics / Transport', 'Other',
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.company_name) return;
    setLoading(true);
    try {
      const res = await createApplication({
        ...form,
        loan_amount_requested: form.loan_amount_requested ? parseFloat(form.loan_amount_requested) : null,
      });
      navigate(`/application/${res.data.application_id}`);
    } catch (err) {
      alert('Failed to create application');
    }
    setLoading(false);
  };

  return (
    <div>
      <h2 style={{ fontSize: 24, color: 'var(--primary)', marginBottom: 24 }}>New Credit Application</h2>
      <div className="card" style={{ maxWidth: 700 }}>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Company Name *</label>
            <input
              type="text"
              value={form.company_name}
              onChange={e => setForm({ ...form, company_name: e.target.value })}
              placeholder="e.g., Reliance Industries Ltd"
              required
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>CIN (Corporate Identification Number)</label>
              <input
                type="text"
                value={form.cin}
                onChange={e => setForm({ ...form, cin: e.target.value })}
                placeholder="e.g., L17110MH1973PLC019786"
              />
            </div>
            <div className="form-group">
              <label>Industry</label>
              <select value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })}>
                <option value="">Select Industry</option>
                {industries.map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Loan Amount Requested (₹)</label>
              <input
                type="number"
                value={form.loan_amount_requested}
                onChange={e => setForm({ ...form, loan_amount_requested: e.target.value })}
                placeholder="e.g., 50000000"
              />
            </div>
            <div className="form-group">
              <label>Loan Purpose</label>
              <input
                type="text"
                value={form.loan_purpose}
                onChange={e => setForm({ ...form, loan_purpose: e.target.value })}
                placeholder="e.g., Working Capital / Term Loan / Project Finance"
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading || !form.company_name}>
            {loading ? 'Creating...' : 'Create Application →'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default NewApplication;
