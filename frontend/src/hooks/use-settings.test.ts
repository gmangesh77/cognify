import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSettings } from "./use-settings";
import * as settingsApi from "@/lib/api/settings";

vi.mock("@/lib/api/settings", () => ({
  fetchDomains: vi.fn(),
  fetchApiKeys: vi.fn(),
  fetchLlmConfig: vi.fn(),
  fetchSeoDefaults: vi.fn(),
  fetchGeneralConfig: vi.fn(),
  createDomain: vi.fn(),
  updateDomain: vi.fn(),
  deleteDomain: vi.fn(),
  updateLlmConfig: vi.fn(),
  addApiKey: vi.fn(),
  rotateApiKey: vi.fn(),
  updateSeoDefaults: vi.fn(),
  updateGeneralConfig: vi.fn(),
}));

const MOCK_DOMAINS = [
  { id: "d1", name: "Cybersecurity", status: "active", trend_sources: ["hackernews"], keywords: ["security"], article_count: 12 },
  { id: "d2", name: "AI Research", status: "active", trend_sources: ["arxiv"], keywords: ["ai"], article_count: 5 },
];
const MOCK_API_KEYS = [
  { id: "k1", service: "anthropic", masked_key: "sk-ant-••••••••7f3a", status: "active" },
  { id: "k2", service: "serpapi", masked_key: "serp-••••••••4b2c", status: "active" },
  { id: "k3", service: "openai", masked_key: "sk-••••••••9d1e", status: "active" },
  { id: "k4", service: "newsapi", masked_key: "news-••••••••3a7b", status: "active" },
];
const MOCK_LLM = { primary_model: "claude-opus-4", drafting_model: "claude-sonnet-4", image_generation: "stable-diffusion-xl" };
const MOCK_SEO = { auto_meta_tags: true, keyword_optimization: true, auto_cover_images: true, include_citations: true, human_review_before_publish: true };
const MOCK_GENERAL = { article_length_target: "3000-5000", content_tone: "professional" };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(settingsApi.fetchDomains).mockResolvedValue(MOCK_DOMAINS as never);
  vi.mocked(settingsApi.fetchApiKeys).mockResolvedValue(MOCK_API_KEYS as never);
  vi.mocked(settingsApi.fetchLlmConfig).mockResolvedValue(MOCK_LLM as never);
  vi.mocked(settingsApi.fetchSeoDefaults).mockResolvedValue(MOCK_SEO as never);
  vi.mocked(settingsApi.fetchGeneralConfig).mockResolvedValue(MOCK_GENERAL as never);
  vi.mocked(settingsApi.createDomain).mockResolvedValue({ id: "d3", name: "Cloud Computing", status: "active", trend_sources: ["hackernews"], keywords: ["AWS", "Azure"], article_count: 0 } as never);
  vi.mocked(settingsApi.updateDomain).mockImplementation((_id, body) => Promise.resolve({ ...MOCK_DOMAINS[0], ...body, id: MOCK_DOMAINS[0].id } as never));
  vi.mocked(settingsApi.deleteDomain).mockResolvedValue(undefined as never);
  vi.mocked(settingsApi.updateLlmConfig).mockImplementation((body) => Promise.resolve({ ...MOCK_LLM, ...body } as never));
  vi.mocked(settingsApi.addApiKey).mockResolvedValue({ id: "k5", service: "arxiv", masked_key: "arx-••••••••1234", status: "active" } as never);
  vi.mocked(settingsApi.rotateApiKey).mockResolvedValue({ id: "k1", service: "anthropic", masked_key: "sk-ant-••••••••new1", status: "active" } as never);
  vi.mocked(settingsApi.updateSeoDefaults).mockImplementation((body) => Promise.resolve({ ...MOCK_SEO, ...body } as never));
  vi.mocked(settingsApi.updateGeneralConfig).mockImplementation((body) => Promise.resolve({ ...MOCK_GENERAL, ...body } as never));
});

describe("useSettings", () => {
  it("initializes with mock domains", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.domains).toHaveLength(2);
    expect(result.current.domains[0].name).toBe("Cybersecurity");
  });

  it("initializes with mock LLM config", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.llmConfig.primaryModel).toBe("claude-opus-4");
  });

  it("initializes with mock API keys", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.apiKeys).toHaveLength(4);
  });

  it("initializes with mock SEO defaults", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.seoDefaults.autoMetaTags).toBe(true);
  });

  it("initializes with mock general config", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.generalConfig.contentTone).toBe("professional");
  });

  it("adds a domain", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.addDomain({
        name: "Cloud Computing",
        status: "active",
        trendSources: ["hackernews"],
        keywords: ["AWS", "Azure"],
      });
    });
    expect(result.current.domains).toHaveLength(3);
    expect(result.current.domains[2].name).toBe("Cloud Computing");
    expect(result.current.domains[2].articleCount).toBe(0);
  });

  it("updates a domain", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    const id = result.current.domains[0].id;
    await act(async () => {
      await result.current.updateDomain(id, { name: "InfoSec" });
    });
    expect(result.current.domains[0].name).toBe("InfoSec");
  });

  it("deletes a domain", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    const id = result.current.domains[1].id;
    await act(async () => {
      await result.current.deleteDomain(id);
    });
    expect(result.current.domains).toHaveLength(1);
  });

  it("updates LLM config", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.updateLlmConfig({ primaryModel: "claude-sonnet-4" });
    });
    expect(result.current.llmConfig.primaryModel).toBe("claude-sonnet-4");
  });

  it("adds an API key", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.addApiKey("arxiv", "arxiv-key-123");
    });
    expect(result.current.apiKeys).toHaveLength(5);
    expect(result.current.apiKeys[4].service).toBe("arxiv");
    expect(result.current.apiKeys[4].maskedKey).toContain("••••");
  });

  it("rotates an API key", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    const id = result.current.apiKeys[0].id;
    await act(async () => {
      await result.current.rotateApiKey(id, "new-key-456");
    });
    expect(result.current.apiKeys[0].maskedKey).toContain("••••");
    expect(result.current.apiKeys[0].maskedKey).not.toBe("sk-ant-••••••••7f3a");
  });

  it("toggles a SEO default", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    act(() => {
      result.current.toggleSeoDefault("autoMetaTags");
    });
    expect(result.current.seoDefaults.autoMetaTags).toBe(false);
  });

  it("updates general config", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.updateGeneralConfig({ contentTone: "casual" });
    });
    expect(result.current.generalConfig.contentTone).toBe("casual");
  });
});
