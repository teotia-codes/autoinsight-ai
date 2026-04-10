import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const uploadCsv = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload-csv", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
};

export const uploadDoc = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload-doc", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
};

export const runAgenticAnalysis = async (payload) => {
  const response = await api.post("/agentic-analysis", payload);
  return response.data;
};

export const runAgenticAnalysisStream = async (payload, { onProgress, onDone, onError }) => {
  try {
    const response = await fetch(`${API_BASE_URL}/agentic-analysis-stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok || !response.body) {
      const text = await response.text().catch(() => "");
      throw new Error(text || "Failed to start streaming analysis");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";

      for (const chunk of chunks) {
        const lines = chunk.split("\n");
        let eventType = "message";
        let data = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.replace("event: ", "").trim();
          } else if (line.startsWith("data: ")) {
            data += line.replace("data: ", "");
          }
        }

        if (!data) continue;

        try {
          const parsed = JSON.parse(data);

          if (eventType === "progress" && onProgress) {
            onProgress(parsed);
          } else if (eventType === "done" && onDone) {
            onDone(parsed);
          } else if (eventType === "error" && onError) {
            onError(parsed);
          }
        } catch (parseErr) {
          console.error("Failed to parse SSE event:", parseErr, data);
        }
      }
    }
  } catch (err) {
    console.error("runAgenticAnalysisStream error:", err);
    if (onError) {
      onError({ message: err.message || "Streaming analysis failed." });
    } else {
      throw err;
    }
  }
};

export const getStaticUrl = (path) => {
  if (!path) return "";

  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  const normalized = path.replace(/\\/g, "/");

  if (normalized.startsWith("/static/")) {
    return `${API_BASE_URL}${normalized}`;
  }

  if (normalized.startsWith("data/")) {
    return `${API_BASE_URL}/static/${normalized.slice("data/".length)}`;
  }

  return `${API_BASE_URL}/${normalized.replace(/^\/+/, "")}`;
};