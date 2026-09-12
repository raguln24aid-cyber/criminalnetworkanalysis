import axios from 'axios';

// Single source of truth for talking to the backend. Every page must import
// this instead of calling axios directly - it's what actually attaches the
// auth token to requests and reacts to the backend rejecting it, neither of
// which existed before (every page was firing unauthenticated requests, and
// the backend now requires a token on almost everything).
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let redirecting = false;
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401 && !redirecting) {
      // Token missing/expired/rejected - the backend is the real gate, this
      // just gets the user back to the login screen instead of a page full
      // of failed requests.
      redirecting = true;
      localStorage.removeItem('token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export function getStoredToken() {
  return localStorage.getItem('token');
}

// Decodes the JWT payload client-side to check expiry before ever sending it.
// This is a UX convenience only (avoids a doomed request round-trip) - the
// backend still independently verifies signature and expiry on every call,
// so a forged or tampered token gains nothing from this check passing.
export function isTokenValid(token) {
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    if (!payload.exp) return false;
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export function getCurrentUser() {
  const token = getStoredToken();
  if (!isTokenValid(token)) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return { username: payload.sub, role: payload.role };
  } catch {
    return null;
  }
}

export default api;
