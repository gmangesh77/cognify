import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * INFRA-008 / CLAUDE.md "files < 200 lines" — enforced for every page and
 * component source file. Hooks, types, lib and mocks are tracked separately.
 */
const ROOTS = ["src/app", "src/components"];
const MAX_LINES = 200;
const SOURCE = /\.(ts|tsx)$/;
const EXCLUDED = /\.(test|spec)\.tsx?$/;

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (SOURCE.test(entry) && !EXCLUDED.test(entry)) out.push(full);
  }
  return out;
}

function lineCount(file: string): number {
  const text = readFileSync(file, "utf8");
  return text.split("\n").length - (text.endsWith("\n") ? 1 : 0);
}

describe("file size budget", () => {
  it("keeps every page/component source file within 200 lines", () => {
    const offenders = ROOTS.flatMap((root) => walk(join(process.cwd(), root)))
      .map((file) => ({
        file: relative(process.cwd(), file),
        lines: lineCount(file),
      }))
      .filter((f) => f.lines > MAX_LINES);
    expect(offenders).toEqual([]);
  });
});
