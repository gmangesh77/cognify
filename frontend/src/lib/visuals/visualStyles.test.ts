import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getCachedVisualStyles,
  getVisualStylesCached,
  resetVisualStylesCache,
} from "./visualStyles";

vi.mock("@/lib/api/visuals", () => ({
  fetchVisualStyles: vi.fn(),
}));

import { fetchVisualStyles } from "@/lib/api/visuals";

const fakeResponse = {
  styles: [
    {
      key: "lifestyle_photo",
      label: "Lifestyle Photo",
      category: "photo" as const,
      default_aspect: "16:9" as const,
      short_desc: "Editorial DSLR.",
      prompt_fragment: "Render as editorial DSLR.",
    },
  ],
  role_defaults: { hero: "lifestyle_photo" },
  personas: [{ key: "general_business", direction: "Calm and grounded." }],
  default_persona: "general_business",
  banned_cliches_block: "BANNED CLICHES (do not generate any of these):",
  planner_catalogue_block: "Available visual styles:",
};

describe("getVisualStylesCached", () => {
  beforeEach(() => {
    resetVisualStylesCache();
    vi.mocked(fetchVisualStyles).mockReset();
  });

  afterEach(() => {
    resetVisualStylesCache();
  });

  it("fetches once and serves cached responses afterwards", async () => {
    vi.mocked(fetchVisualStyles).mockResolvedValue(fakeResponse);
    const a = await getVisualStylesCached();
    const b = await getVisualStylesCached();
    expect(a).toEqual(fakeResponse);
    expect(b).toEqual(fakeResponse);
    expect(fetchVisualStyles).toHaveBeenCalledTimes(1);
  });

  it("dedupes concurrent inflight calls", async () => {
    vi.mocked(fetchVisualStyles).mockResolvedValue(fakeResponse);
    const [a, b] = await Promise.all([
      getVisualStylesCached(),
      getVisualStylesCached(),
    ]);
    expect(a).toBe(b);
    expect(fetchVisualStyles).toHaveBeenCalledTimes(1);
  });

  it("getCachedVisualStyles is null before first fetch", () => {
    expect(getCachedVisualStyles()).toBeNull();
  });

  it("getCachedVisualStyles returns the cached value after fetch", async () => {
    vi.mocked(fetchVisualStyles).mockResolvedValue(fakeResponse);
    await getVisualStylesCached();
    expect(getCachedVisualStyles()).toEqual(fakeResponse);
  });

  it("resetVisualStylesCache forces a refetch", async () => {
    vi.mocked(fetchVisualStyles).mockResolvedValue(fakeResponse);
    await getVisualStylesCached();
    resetVisualStylesCache();
    await getVisualStylesCached();
    expect(fetchVisualStyles).toHaveBeenCalledTimes(2);
  });
});
