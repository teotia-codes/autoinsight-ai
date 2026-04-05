import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const uploadDoc = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload-doc", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
};

export const uploadCsv = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload-csv", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
};

export const runAgenticAnalysis = async ({ file_path, filename, summary_text }) => {
  const response = await api.post("/agentic-analysis", {
    file_path,
    filename,
    summary_text,
  });

  return response.data;
};

export const getStaticUrl = (relativePath) => {
  if (!relativePath) return "";

  // normalize slashes
  let cleaned = relativePath.replace(/\\/g, "/");

  // remove leading ./ if present
  cleaned = cleaned.replace(/^\.\//, "");

  // if path starts with data/, remove it because backend mounts /static -> data/
  if (cleaned.startsWith("data/")) {
    cleaned = cleaned.replace(/^data\//, "");
  }

  return `${API_BASE_URL}/static/${cleaned}`;
};