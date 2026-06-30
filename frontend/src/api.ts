import type {
  Expertise,
  HandoverResponse,
  Health,
  Language,
  ProcessResponse,
  VerifyResponse,
} from "./types";

const BASE = "/api";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status} ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: async (): Promise<Health> => {
    const res = await fetch(`${BASE}/health`);
    if (!res.ok) throw new Error("health check failed");
    return res.json();
  },

  process: (input: {
    text: string;
    source_lang: Language;
    target_lang: Language;
    listener_expertise: Expertise;
    session_id: string;
    speaker?: string;
  }) => post<ProcessResponse>("/process", input),

  verify: (input: {
    session_id: string;
    original_text: string;
    readback_text: string;
    listener_expertise: Expertise;
  }) => post<VerifyResponse>("/verify", input),

  handover: (session_id: string) => post<HandoverResponse>("/handover", { session_id }),
};
