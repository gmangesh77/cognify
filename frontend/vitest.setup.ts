import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";
import { vi } from "vitest";

// Allow waitFor to work correctly with vitest fake timers
configure({
  asyncWrapper: async (cb) => {
    try { await vi.runAllTimersAsync(); } catch {}
    return cb();
  },
  unstable_advanceTimersWrapper: (cb) => {
    const result = cb();
    try { vi.advanceTimersByTime(0); } catch {}
    return result;
  },
});
