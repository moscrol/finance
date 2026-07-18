import { describe, expect, it } from "vitest";
import {
  chatEventTypes,
  publicEventTypes,
  streamEventDefinition,
  streamEventRegistry,
} from "./streamEventRegistry";

describe("stream event registry", () => {
  it("registers workflow.loaded as a public rendered event", () => {
    expect(publicEventTypes.has("workflow.loaded")).toBe(true);
    expect(chatEventTypes).toContain("workflow.loaded");
    expect(streamEventDefinition("workflow.loaded")).toMatchObject({
      public: true,
      terminal: false,
      ui_renderer: "workflow_status",
    });
  });

  it("gives every public event a payload schema and UI renderer", () => {
    const publicDefinitions = streamEventRegistry.events.filter(
      (definition) => definition.public,
    );

    expect(publicDefinitions.length).toBeGreaterThan(0);
    publicDefinitions.forEach((definition) => {
      expect(definition.payload_schema.type).toBe("object");
      expect(Array.isArray(definition.payload_schema.required)).toBe(true);
      expect(definition.ui_renderer).not.toBe("none");
    });
  });
});
