import registryDocument from "../../contracts/stream_events.json";

interface PayloadSchema {
  type: "object";
  required: string[];
}

export interface StreamEventDefinition {
  event_type: string;
  payload_schema: PayloadSchema;
  public: boolean;
  terminal: boolean;
  ui_renderer: string;
}

interface StreamEventRegistryDocument {
  schema_version: number;
  events: StreamEventDefinition[];
}

export const streamEventRegistry =
  registryDocument as StreamEventRegistryDocument;

export const streamSchemaVersion = streamEventRegistry.schema_version;

export const chatEventTypes = streamEventRegistry.events
  .filter(
    (definition) =>
      definition.public && definition.ui_renderer !== "none",
  )
  .map((definition) => definition.event_type);

export const publicEventTypes = new Set(
  streamEventRegistry.events
    .filter((definition) => definition.public)
    .map((definition) => definition.event_type),
);

export function streamEventDefinition(
  eventType: string,
): StreamEventDefinition | undefined {
  return streamEventRegistry.events.find(
    (definition) => definition.event_type === eventType,
  );
}
