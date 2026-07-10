import type { ArtifactDescriptor } from "./types";

export function supportsDailyProjection(
  artifact: ArtifactDescriptor,
): boolean {
  if (artifact.category === "daily_agent") return true;
  const filename = artifact.source_path.split("/").at(-1) ?? "";
  return (
    artifact.category === "daily_review" &&
    /-daily-review\.(?:html|md)$/.test(filename)
  );
}
