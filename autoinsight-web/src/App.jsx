import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { uploadDoc, uploadCsv, runAgenticAnalysis } from "./api/autoInsightApi";
import "./index.css";

function App() {
  const [docFile, setDocFile] = useState(null);
  const [csvFile, setCsvFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("Idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const handleAnalyze = async () => {
    if (!docFile || !csvFile) {
      setError("Please select both a supporting context document and a CSV file.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      setStatus("Uploading supporting context document...");
      const docRes = await uploadDoc(docFile);
      console.log("Document upload response:", docRes);

      setStatus("Uploading CSV dataset...");
      const csvRes = await uploadCsv(csvFile);
      console.log("CSV upload response:", csvRes);

      setStatus("Running agentic analysis...");

      // ✅ THIS IS THE CORRECT PAYLOAD FOR YOUR BACKEND
      const analysisPayload = {
        file_path: csvRes.file_path,
        filename: csvRes.filename,
        summary_text: csvRes.summary_text,
      };

      console.log("Agentic analysis payload:", analysisPayload);

      const analysisRes = await runAgenticAnalysis(analysisPayload);
      console.log("Agentic analysis response:", analysisRes);

      setResult(analysisRes);
      setStatus("Analysis complete.");
    } catch (err) {
      console.error("AutoInsight error:", err);
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Something went wrong while running AutoInsight."
      );
      setStatus("Failed.");
    } finally {
      setLoading(false);
    }
  };

  const finalReport =
    result?.final_report ||
    result?.report ||
    result?.result?.final_report ||
    "No final report found in response.";

  return (
    <div className="app">
      <div className="container">
        <h1>AutoInsight AI</h1>
        <p className="subtitle">
          Autonomous business-aware analytics using RAG, agentic workflows, and AI-generated reporting.
        </p>

        <div className="card">
          <label>Supporting Context Document (.txt or .md)</label>
          <input
            type="file"
            accept=".txt,.md"
            onChange={(e) => setDocFile(e.target.files[0])}
          />
          {docFile && <p className="file-name">Selected: {docFile.name}</p>}
        </div>

        <div className="card">
          <label>CSV Dataset</label>
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setCsvFile(e.target.files[0])}
          />
          {csvFile && <p className="file-name">Selected: {csvFile.name}</p>}
        </div>

        <button onClick={handleAnalyze} disabled={loading}>
          {loading ? "Analyzing..." : "Run Agentic Analysis"}
        </button>

        <div className="status-box">
          <strong>Status:</strong> {status}
        </div>

        {error && (
          <div className="error-box">
            <strong>Error:</strong> {error}
          </div>
        )}

        {result && (
          <div className="results">
            <div className="card">
              <h2>Raw API Response</h2>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>

            <div className="card markdown-card">
              <h2>Final Report</h2>
              <ReactMarkdown>{finalReport}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;