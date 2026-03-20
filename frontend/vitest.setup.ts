import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";
import { vi } from "vitest";

// Allow waitFor to work correctly with vitest fake timers
configure({
  asyncWrapper: async (cb) => {
    let result!: ReturnType<typeof cb>;
    await vi.runAllTimersAsync();
    result = await cb();
    return result;
  },
  unstable_advanceTimersWrapper: (cb) => {
    const result = cb();
    vi.advanceTimersByTime(0);
    return result;
  },
});
