import type { StructuredReport, StructuredReportModule } from "./types";

export function upsertStructuredReportModule(
  report: StructuredReport,
  module: StructuredReportModule,
): StructuredReport {
  const index = report.modules.findIndex((item) => item.module_id === module.module_id);
  if (index === -1) {
    return { ...report, modules: [...report.modules, module] };
  }
  const modules = [...report.modules];
  modules[index] = module;
  return { ...report, modules };
}
