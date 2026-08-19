import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useGenerateActions } from "./use-generate-actions";
import * as trendsApi from "@/lib/api/trends";
import type { CreateTopicData } from "@/components/topics/create-topic-modal";
import type { RankedTopic } from "@/types/api";
import type { CreateSessionResponse } from "@/lib/api/trends";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

vi.mock("@/lib/api/trends", () => ({
  createManualTopic: vi.fn(),
  createResearchSession: vi.fn(),
}));

const mockCreateManualTopic = vi.mocked(trendsApi.createManualTopic);
const mockCreateResearchSession = vi.mocked(trendsApi.createResearchSession);

const createTopicData: CreateTopicData = {
  title: "AI Regulation",
  description: "New AI regulation trends",
  domain: "ai-ml",
  keywords: ["ai", "regulation", "policy"],
  target_audience: "policy makers",
  content_tone: "analytical",
  preferred_angle: "regulatory impact",
};

const rankedTopic: RankedTopic = {
  id: "topic-42",
  title: "Zero Trust",
  description: "desc",
  source: "hackernews",
  external_url: "https://example.com",
  trend_score: 80,
  discovered_at: new Date().toISOString(),
  velocity: 10,
  domain_keywords: ["security"],
  composite_score: 80,
  rank: 1,
  source_count: 2,
  domain: "cybersecurity",
  trend_status: "trending",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useGenerateActions", () => {
  describe("handleConfirm", () => {
    it("navigates to /research/{session_id} on success", async () => {
      mockCreateResearchSession.mockResolvedValue({
        session_id: "s9",
        status: "planning",
        started_at: "",
      });
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      await act(async () => {
        await result.current.handleConfirm(rankedTopic, { target_audience: "devs" });
      });

      expect(mockCreateResearchSession).toHaveBeenCalledWith(rankedTopic.id, {
        target_audience: "devs",
      });
      expect(push).toHaveBeenCalledWith("/research/s9");
      expect(setToast).not.toHaveBeenCalledWith(expect.stringContaining("Check Research page"));
    });

    it("shows a 'Starting research' toast synchronously, before createResearchSession resolves", async () => {
      let resolveSession!: (value: CreateSessionResponse) => void;
      mockCreateResearchSession.mockImplementation(
        () =>
          new Promise<CreateSessionResponse>((resolve) => {
            resolveSession = resolve;
          }),
      );
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      let confirmPromise!: Promise<void>;
      act(() => {
        confirmPromise = result.current.handleConfirm(rankedTopic);
      });

      expect(setToast).toHaveBeenCalledWith(
        expect.stringContaining(`Starting research for "${rankedTopic.title}"`),
      );
      expect(push).not.toHaveBeenCalled();

      await act(async () => {
        resolveSession({ session_id: "s9", status: "planning", started_at: "" });
        await confirmPromise;
      });

      expect(push).toHaveBeenCalledWith("/research/s9");
    });

    it("shows a failure toast and does not navigate when the topic has no id", async () => {
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      await act(async () => {
        await result.current.handleConfirm({ ...rankedTopic, id: undefined });
      });

      expect(mockCreateResearchSession).not.toHaveBeenCalled();
      expect(push).not.toHaveBeenCalled();
      expect(setToast).toHaveBeenCalledWith(expect.stringContaining("no ID"));
    });

    it("shows a failure toast and does not navigate when the request fails", async () => {
      mockCreateResearchSession.mockRejectedValue(new Error("network error"));
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      await act(async () => {
        await result.current.handleConfirm(rankedTopic);
      });

      expect(push).not.toHaveBeenCalled();
      expect(setToast).toHaveBeenCalledWith(expect.stringContaining("Failed to start research"));
    });
  });

  describe("handleCreateAndGenerate", () => {
    it("forwards keywords to createResearchSession and navigates on success", async () => {
      mockCreateManualTopic.mockResolvedValue({
        topic: { id: "t1", title: "AI Regulation" } as unknown as trendsApi.PersistedTopic,
        is_duplicate: false,
        duplicate_of: null,
      });
      mockCreateResearchSession.mockResolvedValue({
        session_id: "s9",
        status: "planning",
        started_at: "",
      });
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      await act(async () => {
        await result.current.handleCreateAndGenerate(createTopicData);
      });

      expect(mockCreateResearchSession).toHaveBeenCalledWith(
        "t1",
        expect.objectContaining({ keywords: createTopicData.keywords }),
      );
      await waitFor(() => expect(push).toHaveBeenCalledWith("/research/s9"));
    });

    it("shows a 'Starting research' toast synchronously, before createManualTopic resolves", async () => {
      let resolveManualTopic!: (
        value: Awaited<ReturnType<typeof trendsApi.createManualTopic>>,
      ) => void;
      mockCreateManualTopic.mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveManualTopic = resolve;
          }),
      );
      mockCreateResearchSession.mockResolvedValue({
        session_id: "s9",
        status: "planning",
        started_at: "",
      });
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      let generatePromise!: Promise<void>;
      act(() => {
        generatePromise = result.current.handleCreateAndGenerate(createTopicData);
      });

      expect(setToast).toHaveBeenCalledWith(
        expect.stringContaining(`Starting research for "${createTopicData.title}"`),
      );
      expect(push).not.toHaveBeenCalled();

      await act(async () => {
        resolveManualTopic({
          topic: { id: "t1", title: "AI Regulation" } as unknown as trendsApi.PersistedTopic,
          is_duplicate: false,
          duplicate_of: null,
        });
        await generatePromise;
      });

      expect(push).toHaveBeenCalledWith("/research/s9");
    });

    it("uses duplicate_of as the topic id when the manual topic is a duplicate", async () => {
      mockCreateManualTopic.mockResolvedValue({
        topic: { id: "t1", title: "AI Regulation" } as unknown as trendsApi.PersistedTopic,
        is_duplicate: true,
        duplicate_of: "existing-topic",
      });
      mockCreateResearchSession.mockResolvedValue({
        session_id: "s10",
        status: "planning",
        started_at: "",
      });
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      await act(async () => {
        await result.current.handleCreateAndGenerate(createTopicData);
      });

      expect(mockCreateResearchSession).toHaveBeenCalledWith(
        "existing-topic",
        expect.objectContaining({ keywords: createTopicData.keywords }),
      );
      expect(push).toHaveBeenCalledWith("/research/s10");
    });

    it("forwards require_outline_approval to createResearchSession when set", async () => {
      mockCreateManualTopic.mockResolvedValue({
        topic: { id: "t1", title: "AI Regulation" } as unknown as trendsApi.PersistedTopic,
        is_duplicate: false,
        duplicate_of: null,
      });
      mockCreateResearchSession.mockResolvedValue({
        session_id: "s9",
        status: "planning",
        started_at: "",
      });
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      await act(async () => {
        await result.current.handleCreateAndGenerate({
          ...createTopicData,
          require_outline_approval: true,
        });
      });

      expect(mockCreateResearchSession).toHaveBeenCalledWith(
        "t1",
        expect.objectContaining({ require_outline_approval: true }),
      );
    });

    it("shows a failure toast and does not navigate when the request fails", async () => {
      mockCreateManualTopic.mockRejectedValue(new Error("boom"));
      const setToast = vi.fn();
      const { result } = renderHook(() => useGenerateActions({ setToast }));

      await act(async () => {
        await result.current.handleCreateAndGenerate(createTopicData);
      });

      expect(push).not.toHaveBeenCalled();
      expect(setToast).toHaveBeenCalledWith(expect.stringContaining("Failed to create topic"));
    });
  });
});
