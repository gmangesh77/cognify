import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "@/lib/api/client";
import {
  addSample,
  createPersona,
  deletePersona,
  deleteSample,
  extractPersonaViolations,
  getPersona,
  listPersonas,
  scorePersona,
  updatePersona,
} from "./personas";

vi.mock("@/lib/api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

const summary = {
  id: "p1",
  name: "House Style",
  description: "Editorial voice",
  sample_count: 5,
  ready: true,
  updated_at: "2026-09-01T00:00:00Z",
};

const detail = {
  ...summary,
  fingerprint: { dims: {}, sample_count: 5 },
  samples: [{ id: "s1", word_count: 200, preview: "Some prose…", created_at: "2026-09-01T00:00:00Z" }],
};

const score = {
  score: 82,
  band: "match" as const,
  per_dim: {},
  deviations: [],
};

describe("personas api", () => {
  beforeEach(() => vi.clearAllMocks());

  it("listPersonas unwraps items", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [summary] } });
    expect(await listPersonas()).toEqual([summary]);
    expect(apiClient.get).toHaveBeenCalledWith("/personas");
  });

  it("createPersona POSTs the body", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: summary });
    const result = await createPersona({ name: "House Style", description: "Editorial voice" });
    expect(result).toEqual(summary);
    expect(apiClient.post).toHaveBeenCalledWith("/personas", {
      name: "House Style",
      description: "Editorial voice",
    });
  });

  it("getPersona GETs by id", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: detail });
    expect(await getPersona("p1")).toEqual(detail);
    expect(apiClient.get).toHaveBeenCalledWith("/personas/p1");
  });

  it("updatePersona PATCHes the patch", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: summary });
    await updatePersona("p1", { name: "New Name" });
    expect(apiClient.patch).toHaveBeenCalledWith("/personas/p1", { name: "New Name" });
  });

  it("deletePersona DELETEs", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined });
    await deletePersona("p1");
    expect(apiClient.delete).toHaveBeenCalledWith("/personas/p1");
  });

  it("addSample POSTs the text and returns the detail", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: detail });
    const result = await addSample("p1", "Some long sample text.");
    expect(result).toEqual(detail);
    expect(apiClient.post).toHaveBeenCalledWith("/personas/p1/samples", {
      text: "Some long sample text.",
    });
  });

  it("deleteSample DELETEs the sample and returns the detail", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: detail });
    const result = await deleteSample("p1", "s1");
    expect(result).toEqual(detail);
    expect(apiClient.delete).toHaveBeenCalledWith("/personas/p1/samples/s1");
  });

  it("scorePersona POSTs the text and returns a VoiceScore", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: score });
    const result = await scorePersona("p1", "Some draft text.");
    expect(result).toEqual(score);
    expect(apiClient.post).toHaveBeenCalledWith("/personas/p1/score", { text: "Some draft text." });
  });

  it("extractPersonaViolations reads detail.violations on 422 only", () => {
    const err = { response: { status: 422, data: { detail: { violations: ["need 5 samples of 150+ words, have 2"] } } } };
    expect(extractPersonaViolations(err)).toEqual(["need 5 samples of 150+ words, have 2"]);
    expect(extractPersonaViolations({ response: { status: 500 } })).toEqual([]);
    expect(extractPersonaViolations(undefined)).toEqual([]);
  });
});
