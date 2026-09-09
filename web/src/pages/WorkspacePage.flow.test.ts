import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";


const workspaceSource = readFileSync(
  resolve(__dirname, "./WorkspacePage.tsx"),
  "utf8",
);


describe("WorkspacePage stage flow", () => {
  it("orders stages as job → match → facts → optimize", () => {
    const stagesBlock = workspaceSource.match(/const STAGES[\s\S]*?\];/)?.[0] ?? "";
    const ids = [...stagesBlock.matchAll(/id:\s*"(\w+)"/g)].map((match) => match[1]);
    expect(ids).toEqual(["job", "match", "facts", "optimize", "export", "practice"]);
  });

  it("keeps job step analyze-only without skip-ahead write CTA", () => {
    expect(workspaceSource).toContain("分析职位描述");
    expect(workspaceSource).not.toContain("分析 JD 并开始写");
    expect(workspaceSource).not.toContain("startAdaptation");
    expect(workspaceSource).toContain('setStage("match")');
    expect(workspaceSource).toContain("补充事实缺口");
    expect(workspaceSource).toContain("生成适配建议");
    expect(workspaceSource).toContain("refreshMatch");
    expect(workspaceSource).toContain("重新匹配证据");
  });
});
