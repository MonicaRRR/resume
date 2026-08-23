import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";


test("从中文经历到针对岗位的简历和模拟面试", async ({ page }) => {
  const projectTitle = `后端工程师-${Date.now()}`;
  await page.goto("/");
  await page.getByLabel("项目名称").fill(projectTitle);
  await page.getByLabel("公司名称 选填").fill("示例科技");
  await page.locator("label.type-option").filter({ hasText: "实习" }).click();
  await page.getByLabel("职位描述").fill("负责 Python API 开发、数据库性能优化与接口稳定性治理");
  await page.getByRole("button", { name: "创建求职项目" }).click();

  await page.getByLabel("上传现有简历").setInputFiles(fileURLToPath(new URL("../../backend/tests/fixtures/sample_resume.txt", import.meta.url)));
  await expect(page.locator(".resume-sheet").getByRole("heading", { name: "张宁" })).toBeVisible();
  await expect(page.getByText("一页紧凑预览")).toBeVisible();

  await page.getByRole("button", { name: /岗位信息/ }).click();
  await page.getByRole("button", { name: "分析职位描述" }).click();
  await expect(page.getByRole("heading", { name: "岗位证据地图" })).toBeVisible();
  await page.getByRole("button", { name: "生成优化建议" }).click();
  await page.getByRole("checkbox", { name: /具备 Python API/ }).check();
  await page.getByRole("button", { name: "应用已选修改" }).click();

  await page.getByRole("button", { name: "专业双栏" }).click();
  await expect(page.locator(".resume-sheet")).toContainText("张宁");
  await expect(page.locator(".resume-sheet")).toContainText("具备 Python API 开发经验");

  await page.getByRole("button", { name: "05 导出" }).click();
  await expect(page.getByRole("button", { name: /下载可编辑文档/ })).toBeEnabled();
  await page.getByRole("button", { name: "06 求职训练" }).click();
  await page.getByRole("link", { name: "进入面试 / 笔试训练" }).click();
  await page.getByRole("button", { name: /模拟面试/ }).click();
  await expect(page.getByText("请结合经历说明你如何保证 API 的稳定性？")).toBeVisible();
  await page.getByLabel("你的回答").fill("我通过指标、日志和链路追踪监控接口，并设置限流和降级策略。");
  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.getByRole("heading", { name: "本轮训练完成" })).toBeVisible();
  await expect(page.getByText("回答方向正确，可进一步补充结果证据。")).toBeVisible();
});
