import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "@/lib/api/client";
import { createBrief, deleteBrief, duplicateBrief, fetchBriefs, updateBrief } from "./briefs";
import type { Brief } from "@/types/brief";

vi.mock("@/lib/api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

const brief: Brief = { id: "b1", owner_id: "u", name: "A", keywords: [], content_type: "article",
  length_target: "medium", structural_diagram_mode: "illustration",
  require_outline_approval: false, created_at: "", updated_at: "" };

describe("briefs api", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetchBriefs GETs /briefs", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [brief] });
    expect(await fetchBriefs()).toEqual([brief]);
    expect(apiClient.get).toHaveBeenCalledWith("/briefs");
  });

  it("createBrief POSTs body", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: brief });
    await createBrief({ ...brief });
    expect(apiClient.post).toHaveBeenCalledWith("/briefs", expect.objectContaining({ name: "A" }));
  });

  it("updateBrief PATCHes by id", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: brief });
    await updateBrief("b1", { name: "Z" });
    expect(apiClient.patch).toHaveBeenCalledWith("/briefs/b1", { name: "Z" });
  });

  it("deleteBrief DELETEs by id", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({});
    await deleteBrief("b1");
    expect(apiClient.delete).toHaveBeenCalledWith("/briefs/b1");
  });

  it("duplicateBrief POSTs /duplicate", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: brief });
    await duplicateBrief("b1");
    expect(apiClient.post).toHaveBeenCalledWith("/briefs/b1/duplicate");
  });
});
