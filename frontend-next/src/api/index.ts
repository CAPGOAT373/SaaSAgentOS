/**
 * Agent OS V6.0 - API layer barrel
 *
 * Usage:
 *   import { api, AgentOSClient, ApiError } from "@/api";
 *   import type { Agent, AuthLoginResponse } from "@/api";
 *
 * Layout:
 *   schema.ts  - spec-accurate types generated from OpenAPI.JSON
 *   types.ts   - curated domain/response types derived from the backend
 *   client.ts  - typed fetch API client
 */

export { AgentOSClient, ApiError, api } from "./client";
export type { AuthStore, ClientConfig } from "./client";

export { axiosInstance } from "./axios-client";
export { default as axiosApi } from "./axios-client";
export type { ApiResponse } from "./axios-client";

export type * from "./schema";
export type * from "./types";
