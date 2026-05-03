/**
 * Centralized API configuration.
 *
 * Reads the backend URL from Vite's environment variable system.
 * In development, VITE_API_BASE_URL defaults to http://localhost:8000/api/v1.
 * In production, set VITE_API_BASE_URL in .env.production to the real backend URL.
 *
 * Usage:  import { API_BASE_URL } from '../config';
 *
 * Every service file imports from here — no hardcoded URLs anywhere else.
 */

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
