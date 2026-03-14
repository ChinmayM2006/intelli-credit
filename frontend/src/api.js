import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Health
export const getHealth = () => api.get('/health');

// Applications
export const createApplication = (data) => api.post('/applications', data);
export const listApplications = () => api.get('/applications');
export const getApplication = (id) => api.get(`/applications/${id}`);

// Document upload
export const uploadDocument = (appId, file, options = {}) => {
  const { docType = '', parseMode = 'balanced', uploadId = '' } = options;
  const formData = new FormData();
  formData.append('file', file);
  if (docType) formData.append('doc_type', docType);
  formData.append('parse_mode', parseMode);
  if (uploadId) formData.append('upload_id', uploadId);
  return api.post(`/applications/${appId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const getUploadProgress = (appId, uploadId) =>
  api.get(`/applications/${appId}/upload-progress/${uploadId}`);

// Document classification confirmation (human-in-the-loop)
export const confirmClassification = (appId, docId, docType) =>
  api.put(`/applications/${appId}/documents/${docId}/confirm`, { doc_type: docType });

// List documents for an application
export const listDocuments = (appId) => api.get(`/applications/${appId}/documents`);

// Research
export const runResearch = (appId) => api.post(`/applications/${appId}/research`);

// Primary insights
export const addPrimaryInsight = (appId, data) =>
  api.post(`/applications/${appId}/insights`, data);

// Scoring
export const calculateScore = (appId) => api.post(`/applications/${appId}/score`);

// SWOT
export const generateSWOT = (appId) => api.post(`/applications/${appId}/swot`);

// Triangulation
export const runTriangulation = (appId) => api.post(`/applications/${appId}/triangulate`);

// Report
export const generateReport = (appId) => api.post(`/applications/${appId}/generate-report`);
export const downloadReportURL = (appId) => `${API_BASE}/applications/${appId}/download-report`;

// Full pipeline (one-click)
export const runPipeline = (appId) => api.post(`/applications/${appId}/run-pipeline`);

// Demo
export const populateDemo = () => api.post('/demo/populate');

export default api;
