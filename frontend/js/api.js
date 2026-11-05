/* Single place for backend communication. No other module calls fetch(). */
const API_BASE_URL = "http://127.0.0.1:8000/api";

async function apiRequest(path, options = {}) {
  const requestOptions = { ...options, headers: { ...(options.headers || {}) } };
  const token = typeof Auth !== "undefined" ? Auth.token() : null;
  if (token) requestOptions.headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, requestOptions);
  } catch (networkError) {
    const error = new Error(
      "Tidak dapat menghubungi backend. Pastikan server berjalan di " + API_BASE_URL + "."
    );
    error.status = 0;
    throw error;
  }

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (parseError) {
      data = null;
    }
  }

  if (!response.ok) {
    let message = `Permintaan gagal (${response.status}).`;
    if (data && typeof data.detail === "string") {
      message = data.detail;
    } else if (data && Array.isArray(data.detail)) {
      message = data.detail.map((item) => item.msg || "validasi gagal").join(", ");
    }
    const error = new Error(message);
    error.status = response.status;
    error.code = data && data.code;
    error.payload = data;

    if (
      response.status === 401 &&
      data &&
      (data.code === "unauthenticated" || data.code === "session_expired") &&
      typeof Auth !== "undefined"
    ) {
      Auth.clear();
      if (!window.location.pathname.endsWith("login.html")) {
        window.location.replace("index.html");
      }
    }
    throw error;
  }
  return data;
}

async function apiBlob(path) {
  const headers = {};
  const token = typeof Auth !== "undefined" ? Auth.token() : null;
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (!response.ok) {
    throw new Error(`Gagal memuat berkas (${response.status}).`);
  }
  return response.blob();
}

function sessionUsername() {
  const session = typeof Auth !== "undefined" ? Auth.get() : null;
  return (session && session.user && session.user.username) || "demo-student";
}

function jsonOptions(method, payload) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}

const API = {
  login: (username, password) =>
    apiRequest("/auth/login", jsonOptions("POST", { username, password })),
  session: () => apiRequest("/auth/session"),
  logout: () => apiRequest("/auth/logout", { method: "POST" }),

  health: () => apiRequest("/health"),
  session: () => apiRequest("/demo/session"),
  tags: (search = "") =>
    apiRequest(`/tags${search ? `?search=${encodeURIComponent(search)}` : ""}`),

  getProfile: (username = sessionUsername()) => apiRequest(`/profile/${username}`),
  analyze: (description, username = sessionUsername()) =>
    apiRequest(`/profile/${username}/analyze`, jsonOptions("POST", { description })),
  confirm: (payload, username = sessionUsername()) =>
    apiRequest(`/profile/${username}/confirm`, jsonOptions("POST", payload)),
  updateProfile: (payload, username = sessionUsername()) =>
    apiRequest(`/profile/${username}`, jsonOptions("PUT", payload)),

  recommendations: (username = sessionUsername()) =>
    apiRequest(`/recommendations/${username}`),
  recompute: () => apiRequest("/recommendations/recompute", { method: "POST" }),

  extractions: () => apiRequest("/admin/extractions"),
  extraction: (id) => apiRequest(`/admin/extractions/${id}`),
  createExtraction: (formData) =>
    apiRequest("/admin/extractions", { method: "POST", body: formData }),
  patchExtraction: (id, payload) =>
    apiRequest(`/admin/extractions/${id}`, jsonOptions("PATCH", payload)),
  approveExtraction: (id) =>
    apiRequest(`/admin/extractions/${id}/approve`, { method: "POST" }),
  rejectExtraction: (id, reason) =>
    apiRequest(`/admin/extractions/${id}/reject`, jsonOptions("POST", { reason })),
  pendingScholarships: () => apiRequest("/admin/scholarships/pending"),
  createManualScholarship: (payload) =>
    apiRequest("/admin/scholarships", jsonOptions("POST", payload)),

  submitScholarship: (formData) =>
    apiRequest("/submissions", { method: "POST", body: formData }),
  mySubmissions: () => apiRequest("/submissions/me"),

  adminSubmissions: (status = "") =>
    apiRequest(`/admin/submissions${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  submissionImage: (imagePath) => apiBlob(imagePath),
  processSubmission: (id, payload) =>
    apiRequest(`/admin/submissions/${id}/process`, jsonOptions("POST", payload)),

  adminStats: () => apiRequest("/admin/stats"),
  adminUsers: () => apiRequest("/admin/users"),
  createAdminUser: (payload) => apiRequest("/admin/users", jsonOptions("POST", payload)),
  resetUserPassword: (userId, password) =>
    apiRequest(
      `/admin/users/${userId}/reset-password`,
      jsonOptions("POST", password ? { password } : {})
    ),

  adminScholarships: (params = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.search) query.set("search", params.search);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/admin/scholarships${suffix}`);
  },
  adminScholarship: (id) => apiRequest(`/admin/scholarships/${id}`),
  patchAdminScholarship: (id, payload) =>
    apiRequest(`/admin/scholarships/${id}`, jsonOptions("PATCH", payload)),
  approveAdminScholarship: (id) =>
    apiRequest(`/admin/scholarships/${id}/approve`, { method: "POST" }),
  rejectAdminScholarship: (id, reason) =>
    apiRequest(`/admin/scholarships/${id}/reject`, jsonOptions("POST", { reason })),
};
