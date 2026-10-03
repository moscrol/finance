export type WorkbenchTheme = "paper" | "tech";

const STORAGE_KEY = "workbench-theme";

export function getInitialTheme(): WorkbenchTheme {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "paper" || saved === "tech") return saved;
  } catch {
    // localStorage 不可用时退回默认
  }
  return "paper";
}

export function applyTheme(theme: WorkbenchTheme): void {
  document.documentElement.dataset.theme = theme;
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // 持久化失败不影响本次切换
  }
}
