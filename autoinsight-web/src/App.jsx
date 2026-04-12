import { useMemo, useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import {
  uploadDoc,
  uploadCsv,
  runAgenticAnalysisStream,
  getStaticUrl,
} from "./api/autoInsightApi";
import "./App.css";


const TABS = [
  "Final Report",
  "Planner",
  "Target Validation",
  "Data Quality",
  "KPIs",
  "Signal Ranking",
  "Visualizations",
  "ML Readiness",
  "Verifier",
];

const PIPELINE_ORDER = [
  "initializing",
  "planner",
  "tool_analysis",
  "target_validation",
  "data_quality",
  "kpi",
  "signal_ranking",
  "visualization_tool",
  "ml_readiness",
  "verifier",
  "final_report",
  "refinement",
];

function App() {
  const [docFile, setDocFile] = useState(null);
  const [csvFile, setCsvFile] = useState(null);

  const [docResult, setDocResult] = useState(null);
  const [csvResult, setCsvResult] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  const [contextDir, setContextDir] = useState(null);

  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState("Processing...");
  const [error, setError] = useState("");

  const [activeTab, setActiveTab] = useState("Final Report");

  const [isStreaming, setIsStreaming] = useState(false);
  const [progressSteps, setProgressSteps] = useState([]);

  const summaryStats = useMemo(() => {
    if (!csvResult?.summary_text) return [];

    const summary = csvResult.summary_text;

    const rowsMatch = summary.match(/Dataset contains\s+(\d+)\s+rows/i);
    const colsMatch = summary.match(/and\s+(\d+)\s+columns/i);
    const missingMatch = summary.match(/No missing values detected/i);

    let duplicateRows = "—";
    const dupMatch = summary.match(/Duplicate rows\s*:\s*(\d+)/i);

    if (dupMatch) {
      duplicateRows = dupMatch[1];
    }

    return [
      { label: "Rows", value: rowsMatch ? formatNumber(rowsMatch[1]) : "—" },
      { label: "Columns", value: colsMatch ? colsMatch[1] : "—" },
      { label: "Missing Values", value: missingMatch ? "0" : "Check" },
      { label: "Duplicate Rows", value: duplicateRows },
    ];
  }, [csvResult]);

  const orderedProgressSteps = useMemo(() => {
    return [...progressSteps].sort((a, b) => {
      const aIndex = PIPELINE_ORDER.indexOf(a.step);
      const bIndex = PIPELINE_ORDER.indexOf(b.step);
      return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
    });
  }, [progressSteps]);

  const completedSteps = useMemo(() => {
    return orderedProgressSteps.filter((step) => step.status === "completed").length;
  }, [orderedProgressSteps]);

  const totalTrackedSteps = PIPELINE_ORDER.length;

  const progressPercent = useMemo(() => {
    return Math.round((completedSteps / totalTrackedSteps) * 100);
  }, [completedSteps, totalTrackedSteps]);

  const handleDocUpload = async () => {
    if (!docFile) return;

    try {
      setError("");
      setLoading(true);
      setLoadingText("Uploading context document...");

      const result = await uploadDoc(docFile);

      setDocResult(result);
      setContextDir(result?.context_dir || null);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to upload document.");
    } finally {
      setLoading(false);
      setLoadingText("Processing...");
    }
  };

  const handleCsvUpload = async () => {
    if (!csvFile) return;

    try {
      setError("");
      setLoading(true);
      setLoadingText("Uploading CSV dataset...");

      const result = await uploadCsv(csvFile);
      setCsvResult(result);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to upload CSV.");
    } finally {
      setLoading(false);
      setLoadingText("Processing...");
    }
  };

  const handleRunAnalysis = async () => {
    if (!csvResult?.file_path) {
      setError("Please upload a CSV file first.");
      return;
    }

    try {
      setError("");
      setLoading(true);
      setIsStreaming(true);
      setLoadingText("Starting agentic analysis...");
      setProgressSteps([]);
      setAnalysisResult(null);
      setActiveTab("Final Report");

      const payload = {
        file_path: csvResult.file_path,
        filename: csvResult.filename,
        summary_text: csvResult.summary_text,
        context_dir: contextDir || null,
      };

      await runAgenticAnalysisStream(payload, {
        onProgress: (event) => {
          setLoadingText(event?.message || "Running agentic analysis...");

          setProgressSteps((prev) => {
            const existingIndex = prev.findIndex((item) => item.step === event.step);

            if (existingIndex !== -1) {
              const updated = [...prev];
              updated[existingIndex] = {
                ...updated[existingIndex],
                ...event,
              };
              return updated;
            }

            return [...prev, event];
          });
        },
        onDone: (result) => {
          console.log("Streaming agentic analysis result:", result);
          setAnalysisResult(result);
          setActiveTab("Final Report");
          setIsStreaming(false);
          setLoading(false);
          setLoadingText("Processing...");
        },
        onError: (err) => {
          console.error("Streaming analysis error:", err);
          setError(err?.message || "Agentic analysis failed.");
          setIsStreaming(false);
          setLoading(false);
          setLoadingText("Processing...");
        },
      });
    } catch (err) {
      console.error("Agentic analysis failed:", err);
      setError(err?.message || "Agentic analysis failed.");
      setIsStreaming(false);
      setLoading(false);
      setLoadingText("Processing...");
    }
  };

  const renderTabContent = () => {
    if (!analysisResult) return null;

    switch (activeTab) {
      case "Planner":
        return <MarkdownBlock content={analysisResult.planner_output} />;

      case "Target Validation":
        return <PlainTextBlock content={analysisResult.target_validation_output} />;

      case "Data Quality":
        return <PlainTextBlock content={analysisResult.data_quality_output} />;

      case "KPIs":
        return (
          <div className="stack-gap">
            <KpiPreview data={analysisResult.kpi_structured} />
            <PlainTextBlock content={analysisResult.kpi_output} />
          </div>
        );

      case "Signal Ranking":
        return <PlainTextBlock content={analysisResult.signal_ranking_output} />;

      case "Visualizations":
        return (
          <div className="stack-gap">
            <PlainTextBlock content={analysisResult.visualization_summary} />
            <PlotlyGallery visualizations={analysisResult.visualizations || []} />
          </div>
        );

      case "ML Readiness":
        return <PlainTextBlock content={analysisResult.ml_readiness_output} />;

      case "Verifier":
        return <MarkdownBlock content={analysisResult.verifier_output} />;

      case "Final Report":
        return <MarkdownBlock content={analysisResult.final_report} />;

      default:
        return null;
    }
  };

  return (
    <div className="app-shell">
      {loading && !isStreaming && <LoadingOverlay text={loadingText} />}

      <header className="hero">
        <div className="container hero-inner">
          <div className="hero-left">
            <p className="eyebrow">AI-Powered Analytics Workspace</p>
            <h1 className="brand-title">AutoInsight AI</h1>
            <p className="brand-subtitle">
              Autonomous analytics, KPI extraction, visualization generation,
              ML-readiness checks, and executive report creation from your datasets.
            </p>
          </div>

          <div className="hero-badge-card">
            <div className="hero-badge">
              <span className="hero-dot"></span>
              {analysisResult
                ? "Analysis Completed"
                : isStreaming
                ? "Analysis Running"
                : "System Ready"}
            </div>

            <div className="hero-mini-grid">
              <MiniStat label="Model" value="Qwen + Agents" />
              <MiniStat label="Backend" value="FastAPI" />
              <MiniStat label="Frontend" value="React" />
              <MiniStat label="Mode" value={isStreaming ? "Streaming" : "Stable"} />
            </div>
          </div>
        </div>
      </header>

      <main className="container main-content">
        {error && (
          <div className="alert alert-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        <section className="upload-section">
          <div className="upload-grid">
            <UploadCard
              title="Upload Context Document"
              subtitle="Optional business/domain knowledge for more relevant analysis"
              file={docFile}
              accept=".txt,.md"
              onChange={(e) => setDocFile(e.target.files?.[0] || null)}
              buttonLabel="Choose Context File"
              actionLabel="Upload Context"
              actionClass="btn-secondary"
              onAction={handleDocUpload}
              disabled={!docFile || loading}
              successText={
                docResult
                  ? `Uploaded: ${docResult.filename}${contextDir ? " • Context Indexed" : ""}`
                  : ""
              }
            />

            <UploadCard
              title="Upload CSV Dataset"
              subtitle="Upload the structured dataset you want AutoInsight to analyze"
              file={csvFile}
              accept=".csv"
              onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
              buttonLabel="Choose CSV File"
              actionLabel="Upload CSV"
              actionClass="btn-success"
              onAction={handleCsvUpload}
              disabled={!csvFile || loading}
              successText={csvResult ? `Uploaded: ${csvResult.filename}` : ""}
            />
          </div>

          <div className="action-panel">
            <div>
              <h3 className="action-title">Run Full Agentic Analysis</h3>
              <p className="action-subtitle">
                Generate insights, KPIs, charts, ML-readiness checks, and a polished final report.
              </p>
            </div>

            <button
              className="btn btn-primary btn-large"
              onClick={handleRunAnalysis}
              disabled={!csvResult || loading}
            >
              {isStreaming ? "Running Analysis..." : "Run Analysis"}
            </button>
          </div>
        </section>

        {isStreaming && (
          <section className="section-card progress-section">
            <div className="section-header">
              <div>
                <p className="section-eyebrow">Live Pipeline Status</p>
                <h2 className="section-title">Analysis Progress</h2>
              </div>
              <div className="analysis-chip">
                {completedSteps}/{totalTrackedSteps} Done
              </div>
            </div>

            <p className="progress-subtitle">
              AutoInsight is running your multi-agent analytics pipeline step-by-step...
            </p>

            <div className="progress-bar-wrap">
              <div className="progress-bar-track">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${progressPercent}%` }}
                ></div>
              </div>
              <span className="progress-bar-label">{progressPercent}%</span>
            </div>

            <div className="progress-list">
              {PIPELINE_ORDER.map((stepName) => {
                const step = orderedProgressSteps.find((item) => item.step === stepName);

                let status = "pending";
                let message = "Waiting...";

                if (step) {
                  status = step.status || "pending";
                  message =
                    step.message ||
                    (status === "completed"
                      ? "Completed"
                      : status === "started"
                      ? "Running..."
                      : "Waiting...");
                }

                return (
                  <div key={stepName} className={`progress-item ${status}`}>
                    <div className="progress-left">
                      <span className="progress-dot"></span>
                      <div className="progress-texts">
                        <span className="progress-step-name">
                          {formatStepName(stepName)}
                        </span>
                        <span className="progress-step-message">{message}</span>
                      </div>
                    </div>

                    <span className={`progress-status ${status}`}>
                      {status === "started"
                        ? "Running"
                        : status === "completed"
                        ? "Completed"
                        : status === "error"
                        ? "Failed"
                        : "Pending"}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {csvResult && (
          <section className="section-card">
            <div className="section-header">
              <div>
                <p className="section-eyebrow">Dataset Overview</p>
                <h2 className="section-title">Dataset Summary</h2>
              </div>
              <div className="file-chip">{csvResult.filename}</div>
            </div>

            <div className="stats-grid">
              {summaryStats.map((item) => (
                <div className="stat-card" key={item.label}>
                  <p className="stat-label">{item.label}</p>
                  <p className="stat-value">{item.value}</p>
                </div>
              ))}
            </div>

            <SummaryPanel summaryText={csvResult.summary_text} />
          </section>
        )}

        {analysisResult && (
          <>
            <section className="section-card">
              <div className="section-header">
                <div>
                  <p className="section-eyebrow">AI Results</p>
                  <h2 className="section-title">Analysis Workspace</h2>
                </div>
                <div className="analysis-chip">
                  Charts: {Array.isArray(analysisResult.visualizations) ? analysisResult.visualizations.length : 0}
                </div>
              </div>

              <div className="tabs">
                {TABS.map((tab) => (
                  <button
                    key={tab}
                    className={`tab-btn ${activeTab === tab ? "active" : ""}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {renderTabContent()}
            </section>

            {Array.isArray(analysisResult.visualizations) && analysisResult.visualizations.length > 0 && (
              <section className="section-card">
                <div className="section-header">
                  <div>
                    <p className="section-eyebrow">Visual Intelligence</p>
                    <h2 className="section-title">Generated Charts</h2>
                  </div>
                  <div className="analysis-chip">
                    Charts: {analysisResult.visualizations.length}
                  </div>
                </div>
                <PlotlyGallery visualizations={analysisResult.visualizations} />
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function UploadCard({
  title,
  subtitle,
  file,
  accept,
  onChange,
  buttonLabel,
  actionLabel,
  actionClass,
  onAction,
  disabled,
  successText,
}) {
  return (
    <div className="upload-card">
      <div>
        <h2 className="card-title">{title}</h2>
        <p className="card-subtitle">{subtitle}</p>
      </div>

      <label className="file-btn">
        {buttonLabel}
        <input type="file" accept={accept} onChange={onChange} hidden />
      </label>

      {file && <p className="file-name">Selected: {file.name}</p>}
      {successText && <p className="success-inline">{successText}</p>}

      <button className={`btn ${actionClass}`} onClick={onAction} disabled={disabled}>
        {actionLabel}
      </button>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="mini-stat">
      <p className="mini-stat-label">{label}</p>
      <p className="mini-stat-value">{value}</p>
    </div>
  );
}

function SummaryPanel({ summaryText }) {
  const lines = (summaryText || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <div className="summary-panel">
      {lines.map((line, idx) => (
        <div key={idx} className="summary-line">
          <span className="summary-dot"></span>
          <span>{line}</span>
        </div>
      ))}
    </div>
  );
}

function KpiPreview({ data }) {
  if (!data || typeof data !== "object") return null;

  const entries = Object.entries(data).slice(0, 4);
  if (!entries.length) return null;

  return (
    <div className="stats-grid">
      {entries.map(([key, value]) => (
        <div className="stat-card" key={key}>
          <p className="stat-label">{formatKey(key)}</p>
          <p className="stat-value small">{String(value)}</p>
        </div>
      ))}
    </div>
  );
}

function PlainTextBlock({ content }) {
  return (
    <div className="content-box">
      <pre className="plain-text">{content || "No content available."}</pre>
    </div>
  );
}

function MarkdownBlock({ content }) {
  return (
    <div className="content-box markdown-box">
      <ReactMarkdown>{content || "No content available."}</ReactMarkdown>
    </div>
  );
}

function SafePlot({ viz, fallbackTitle }) {
  const containerRef = useRef(null);
  const spec = viz?.plotly_spec;
  const data = Array.isArray(spec?.data) ? spec.data : [];
  const layout = spec?.layout && typeof spec.layout === "object" ? spec.layout : {};

  useEffect(() => {
    if (!containerRef.current || !data.length) return;

    const render = (Plotly) => {
      Plotly.newPlot(
        containerRef.current,
        data,
        { ...layout, autosize: true },
        {
          responsive: true,
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ["sendDataToCloud"],
          toImageButtonOptions: { format: "png", filename: fallbackTitle || "chart" },
        }
      );
    };

    // Use already-loaded Plotly if available, otherwise load from CDN
    if (window.Plotly) {
      render(window.Plotly);
    } else {
      const script = document.createElement("script");
      script.src = "https://cdn.plot.ly/plotly-2.35.2.min.js";
      script.onload = () => render(window.Plotly);
      document.head.appendChild(script);
    }

    return () => {
      if (containerRef.current && window.Plotly) {
        window.Plotly.purge(containerRef.current);
      }
    };
  }, [viz]);

  if (!data.length) {
    return (
      <div className="content-box empty-box" style={{ minHeight: "350px" }}>
        No chart data available for {fallbackTitle}.
      </div>
    );
  }

  return <div ref={containerRef} style={{ width: "100%", minHeight: "350px" }} />;
}

function PlotlyGallery({ visualizations }) {
  if (!Array.isArray(visualizations) || !visualizations.length) {
    return <div className="content-box empty-box">No charts generated.</div>;
  }

  return (
    <div className="chart-grid">
      {visualizations.map((viz, index) => {
        const spec = viz?.plotly_spec;
        const hasPlotly =
          spec &&
          typeof spec === "object" &&
          Array.isArray(spec.data) &&
          spec.data.length > 0;

        const imageUrl = viz?.path ? getStaticUrl(viz.path) : null;

        return (
          <div key={index} className="chart-card">
            <div className="chart-top">
              <span className="chart-badge">{viz.title || `Chart ${index + 1}`}</span>
            </div>

            {hasPlotly ? (
              <SafePlot
                viz={viz}
                fallbackTitle={viz.title || `Chart ${index + 1}`}
              />
            ) : imageUrl ? (
              <div className="chart-image-wrap">
                <img
                  src={imageUrl}
                  alt={viz.title || `Chart ${index + 1}`}
                  className="chart-image"
                  style={{
                    width: "100%",
                    minHeight: "350px",
                    objectFit: "contain",
                    borderRadius: "12px",
                  }}
                  onError={(e) => {
                    console.error("Failed to load chart image:", imageUrl);
                    e.currentTarget.style.display = "none";
                  }}
                />
              </div>
            ) : (
              <div className="content-box empty-box" style={{ minHeight: "350px" }}>
                Chart unavailable for this visualization.
              </div>
            )}

            {viz.interpretation && (
              <div className="chart-footer">
                <p className="chart-path">{viz.interpretation}</p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function LoadingOverlay({ text }) {
  return (
    <div className="loading-overlay">
      <div className="loading-box">
        <div className="spinner"></div>
        <p>{text}</p>
      </div>
    </div>
  );
}

function formatKey(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatNumber(value) {
  return Number(value).toLocaleString();
}

function formatStepName(step) {
  if (!step) return "Unknown Step";
  return step
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default App;