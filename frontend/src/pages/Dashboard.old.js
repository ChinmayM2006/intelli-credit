import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listApplications } from '../api';

function Dashboard() {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadApplications();
  }, []);

  const loadApplications = async () => {
    try {
      const res = await listApplications();
      setApplications(res.data);
    } catch (err) {
      console.error('Failed to load applications:', err);
    }
    setLoading(false);
  };

  const getStatusBadge = (status) => {
    const map = {
      created: { class: 'badge-neutral', label: 'Created' },
      documents_uploaded: { class: 'badge-info', label: 'Documents Uploaded' },
      research_complete: { class: 'badge-warning', label: 'Research Done' },
      scored: { class: 'badge-success', label: 'Scored' },
      cam_generated: { class: 'badge-success', label: 'CAM Ready' },
    };
    const s = map[status] || { class: 'badge-neutral', label: status };
    return <span className={`badge ${s.class}`}>{s.label}</span>;
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 24, color: 'var(--primary)' }}>Credit Applications</h2>
          <p style={{ color: 'var(--text-light)', fontSize: 14 }}>AI-powered Credit Decisioning Engine</p>
        </div>
        <Link to="/new" className="btn btn-primary">+ New Application</Link>
      </div>

      {/* Stats */}
      <div className="grid-3" style={{ marginBottom: 24 }}>
        <div className="card stat-card">
          <div className="stat-value">{applications.length}</div>
          <div className="stat-label">Total Applications</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: 'var(--success)' }}>
            {applications.filter(a => a.status === 'cam_generated').length}
          </div>
          <div className="stat-label">CAMs Generated</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: 'var(--warning)' }}>
            {applications.filter(a => a.status === 'created' || a.status === 'documents_uploaded').length}
          </div>
          <div className="stat-label">In Progress</div>
        </div>
      </div>

      {/* Applications List */}
      <div className="card">
        <div className="card-header">
          <h2>All Applications</h2>
        </div>
        {loading ? (
          <div className="loading"><div className="spinner"></div> Loading...</div>
        ) : applications.length === 0 ? (
          <div className="empty-state">
            <h3>No applications yet</h3>
            <p>Create your first credit application to get started</p>
            <Link to="/new" className="btn btn-primary" style={{ marginTop: 16 }}>+ Create Application</Link>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Company</th>
                  <th>Industry</th>
                  <th>Loan Amount</th>
                  <th>Status</th>
                  <th>Score</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {applications.map(app => (
                  <tr key={app.id}>
                    <td><code>{app.id}</code></td>
                    <td><strong>{app.company_name}</strong></td>
                    <td>{app.industry || '—'}</td>
                    <td>{app.loan_amount_requested ? `₹${app.loan_amount_requested.toLocaleString()}` : '—'}</td>
                    <td>{getStatusBadge(app.status)}</td>
                    <td>
                      {app.risk_score ? (
                        <span style={{ fontWeight: 700, color: app.risk_score.overall_score >= 60 ? 'var(--success)' : app.risk_score.overall_score >= 40 ? 'var(--warning)' : 'var(--danger)' }}>
                          {app.risk_score.overall_score} ({app.risk_score.grade})
                        </span>
                      ) : '—'}
                    </td>
                    <td>
                      <Link to={`/application/${app.id}`} className="btn btn-outline btn-sm">View</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
