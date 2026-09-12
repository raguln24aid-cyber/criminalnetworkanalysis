import { useRef, useState } from 'react';
import { Upload, File, CheckCircle, XCircle } from 'lucide-react';
import api from '../api/client';

const ALLOWED_EXTENSIONS = ['.csv', '.json', '.txt', '.pdf'];
const MAX_FILE_SIZE = 50 * 1024 * 1024;

function getExtension(filename) {
  const dot = filename.lastIndexOf('.');
  return dot >= 0 ? filename.slice(dot).toLowerCase() : '';
}

function validateFile(file) {
  if (!file || file.size === 0) {
    return 'File is empty.';
  }
  if (file.size > MAX_FILE_SIZE) {
    return 'File is too large. Maximum size is 50 MB.';
  }
  const ext = getExtension(file.name);
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return 'Unsupported file type. Please upload CSV, JSON, TXT, or PDF files.';
  }
  return null;
}

function getUploadErrorMessage(error) {
  if (!error.response) {
    return 'Unable to connect to the ingestion server. Make sure the FastAPI backend is running on port 8000.';
  }
  const status = error.response.status;
  const detail = error.response.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => item.msg || String(item)).join(', ');
  }
  if (status === 413) return 'File is too large. Maximum size is 50 MB.';
  if (status === 400) return 'Upload rejected. Check the file type and try again.';
  if (status === 422) return 'Invalid upload request. Please try again.';
  if (status >= 500) return 'Server error while uploading. Please try again later.';
  return 'Upload failed.';
}

export default function DataIngestion() {
  const inputRef = useRef(null);
  const dragCounter = useRef(0);
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);

  const isUploading = files.some((f) => f.state === 'uploading');

  const updateFile = (id, patch) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  };

  const uploadFile = async (id, file) => {
    updateFile(id, { state: 'uploading', error: null, message: null });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/api/data/upload', formData);
      const docId = response.data.document_id;
      
      updateFile(id, {
        state: 'processing',
        message: 'Processing started...',
        savedAs: response.data.filename,
        documentId: docId
      });
      
      pollStatus(id, docId);
    } catch (error) {
      updateFile(id, {
        state: 'error',
        error: getUploadErrorMessage(error),
      });
    }
  };

  const pollStatus = (id, docId) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/processing/${docId}`);
        const data = res.data;
        if (data.status === 'completed') {
           clearInterval(interval);
           updateFile(id, {
             state: 'completed',
             message: `✓ Processing completed. Records: ${data.records_processed}, Entities: ${data.entities_found}, Relationships: ${data.relationships_found}, Events: ${data.events_found}`
               + (data.evidence_id ? ` | Evidence ID: ${data.evidence_id} (verify in Evidence Explorer)` : ''),
             progress: 100
           });
           // Let Network Explorer (if already open) refresh itself instead of
           // requiring a manual browser refresh to see the new graph.
           window.dispatchEvent(new CustomEvent('nexus:ingestion-completed', { detail: { documentId: docId } }));
        } else if (data.status === 'failed') {
           clearInterval(interval);
           updateFile(id, {
             state: 'error',
             error: data.error || 'Processing failed'
           });
        } else {
           updateFile(id, {
             message: `Stage: ${data.stage} - ${data.progress}%`,
             progress: data.progress,
             stats: `Records: ${data.records_processed || 0} | Entities: ${data.entities_found || 0} | Relationships: ${data.relationships_found || 0}`
           });
        }
      } catch (err) {
         clearInterval(interval);
         updateFile(id, { state: 'error', error: 'Failed to fetch status' });
      }
    }, 1500);
  };

  const handleFiles = (fileList) => {
    const incoming = Array.from(fileList).map((file) => {
      const validationError = validateFile(file);
      return {
        id: crypto.randomUUID(),
        file,
        state: validationError ? 'error' : 'pending',
        error: validationError,
        message: null,
        savedAs: null,
      };
    });

    setFiles((prev) => [...prev, ...incoming]);

    incoming.forEach((item) => {
      if (!item.error) {
        uploadFile(item.id, item.file);
      }
    });
  };

  const handleBrowse = (event) => {
    event.stopPropagation();
    if (!isUploading) {
      inputRef.current?.click();
    }
  };

  const handleDropZoneClick = () => {
    if (!isUploading) {
      inputRef.current?.click();
    }
  };

  const handleDragEnter = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounter.current += 1;
    setIsDragging(true);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (isUploading) return;
    if (event.dataTransfer.files?.length) {
      handleFiles(event.dataTransfer.files);
    }
  };

  const handleInputChange = (event) => {
    if (event.target.files?.length) {
      handleFiles(event.target.files);
    }
    event.target.value = '';
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Data Ingestion</h1>
        <p className="text-slate-400">Upload fragmented intelligence and evidence files</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,.json,.txt,.pdf"
        multiple
        className="hidden"
        onChange={handleInputChange}
      />

      <div
        onClick={handleDropZoneClick}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center text-center transition-colors cursor-pointer ${
          isDragging
            ? 'border-primary-500 bg-dark-800'
            : 'border-dark-700 bg-dark-800/50 hover:bg-dark-800'
        } ${isUploading ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <div className="w-16 h-16 bg-primary-500/20 rounded-full flex items-center justify-center mb-4">
          <Upload className="w-8 h-8 text-primary-400" />
        </div>
        <h3 className="text-lg font-medium text-white mb-2">Drag and drop files here</h3>
        <p className="text-sm text-slate-400 mb-6">Supports CSV, JSON, TXT, PDF (Synthetic demo supports CSV)</p>
        <button
          type="button"
          onClick={handleBrowse}
          disabled={isUploading}
          className="bg-dark-700 hover:bg-dark-600 text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Browse Files
        </button>
      </div>

      {files.length > 0 && (
        <div className="glass-panel p-6">
          <h3 className="text-lg font-medium text-white mb-4">Selected Files</h3>

          <div className="space-y-3">
            {files.map((f) => (
              <div
                key={f.id}
                className="flex items-start justify-between p-3 rounded-lg bg-dark-900 border border-dark-700"
              >
                <div className="flex items-start min-w-0 flex-1">
                  <File className="w-5 h-5 text-slate-400 mr-3 mt-0.5 shrink-0" />
                  <div className="min-w-0 w-full">
                    <span className="text-sm text-slate-200 block truncate font-semibold">{f.file.name}</span>
                    {f.state === 'uploading' && (
                      <span className="text-xs text-primary-400">Uploading...</span>
                    )}
                    {f.state === 'processing' && (
                      <div className="w-full mt-2">
                         <div className="flex justify-between text-xs text-primary-400 mb-1">
                            <span>{f.message}</span>
                            <span>{f.progress || 0}%</span>
                         </div>
                         <div className="w-full bg-dark-700 rounded-full h-1.5 mb-1">
                            <div className="bg-primary-500 h-1.5 rounded-full transition-all duration-300" style={{ width: `${f.progress || 0}%` }}></div>
                         </div>
                         <span className="text-[10px] text-slate-400">{f.stats}</span>
                      </div>
                    )}
                    {f.state === 'completed' && (
                      <span className="text-xs text-green-400 mt-1 block">{f.message}</span>
                    )}
                    {f.state === 'error' && (
                      <span className="text-xs text-red-400 mt-1 block">{f.error}</span>
                    )}
                  </div>
                </div>
                {f.state === 'completed' && <CheckCircle className="w-5 h-5 text-green-400 shrink-0 ml-3" />}
                {f.state === 'error' && <XCircle className="w-5 h-5 text-red-400 shrink-0 ml-3" />}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
