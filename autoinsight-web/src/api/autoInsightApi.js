import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const uploadDoc = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload-doc", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
};

export const uploadCsv = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload-csv", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
};

export const runAgenticAnalysis = async (payload) => {
  const response = await api.post("/agentic-analysis", payload);
  return response.data;
};