import { afterEach, expect, it, vi } from "vitest";
import { applyTheme, getInitialTheme } from "./theme";

afterEach(() => { vi.unstubAllGlobals(); delete document.documentElement.dataset.theme; });

it("preserves the paper default and a user's saved theme choice", () => {
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value) });
  expect(getInitialTheme()).toBe("paper");
  applyTheme("tech");
  expect(document.documentElement.dataset.theme).toBe("tech");
  expect(getInitialTheme()).toBe("tech");
});

it("keeps theme switching usable when browser persistence is unavailable", () => {
  vi.stubGlobal("localStorage", { getItem: () => { throw new Error("disabled"); }, setItem: () => { throw new Error("disabled"); } });
  expect(getInitialTheme()).toBe("paper");
  expect(() => applyTheme("tech")).not.toThrow();
  expect(document.documentElement.dataset.theme).toBe("tech");
});
