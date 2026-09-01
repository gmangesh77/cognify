import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "@/lib/api/client";
import { extractPromptViolations, listPrompts, resetPrompt, updatePrompt } from "./prompts";

vi.mock("@/lib/api/client", () => ({
  apiClient: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const view = {
  key: "content_outline.user",
  step: "content_outline",
  description: "d",
  variables: ["title"],
  default_template: "D",
  template: "D",
  is_overridden: false,
  updated_by: null,
  updated_at: null,
};

describe("prompts api", () => {
  beforeEach(() => vi.clearAllMocks());

  it("listPrompts unwraps items", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [view] } });
    expect(await listPrompts()).toEqual([view]);
    expect(apiClient.get).toHaveBeenCalledWith("/prompts");
  });

  it("updatePrompt PUTs the template", async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ data: view });
    await updatePrompt("content_outline.user", "T");
    expect(apiClient.put).toHaveBeenCalledWith("/prompts/content_outline.user", { template: "T" });
  });

  it("resetPrompt DELETEs", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: view });
    await resetPrompt("content_outline.user");
    expect(apiClient.delete).toHaveBeenCalledWith("/prompts/content_outline.user");
  });

  it("extractPromptViolations reads detail.violations on 422 only", () => {
    const err = { response: { status: 422, data: { detail: { violations: ["unknown variable {x}"] } } } };
    expect(extractPromptViolations(err)).toEqual(["unknown variable {x}"]);
    expect(extractPromptViolations({ response: { status: 500 } })).toEqual([]);
  });
});
