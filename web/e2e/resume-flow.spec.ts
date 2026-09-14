import { expect, test, type APIRequestContext, type Page } from "@playwright/test";


async function seedProfile(request: APIRequestContext) {
  const profile = await request.put("http://127.0.0.1:8000/api/profile", {
    data: {
      resume: {
        basics: {
          name: "张宁",
          gender: "女",
          birthday: "2002-05-18",
          email: "",
          phone: "",
          location: "上海",
          wechat: "",
          political_status: "",
          photo_data_url: "",
          target_role: { value: "后端工程师", source_fact_ids: [], origin: "manual", confidence: 1 },
          summary: { value: "", source_fact_ids: [], origin: "manual", confidence: 1 },
        },
        education: [{
          id: "edu-1", institution: "示例大学", degree: "本科", field: "计算机", start_date: "2020-09", end_date: "2024-06", highlights: [],
        }],
        work_experience: [{
          id: "work-1", company: "示例科技", title: "后端实习生", start_date: "2023-06", end_date: "2023-09",
          bullets: [{ value: "使用 Python 开发 API", source_fact_ids: [], origin: "manual", confidence: 1 }],
        }],
        projects: [],
        skills: [{
          id: "skill-1", name: "专业技能",
          items: [{ value: "Python", source_fact_ids: [], origin: "manual", confidence: 1 }],
        }],
        certificates: [],
        awards: [],
        custom_sections: [],
        section_order: ["basics", "work_experience", "projects", "education", "skills"],
        layout_profile: {
          source_kind: "builtin", font_family: "", heading_font_family: "", accent_color: "",
          base_font_size: null, line_height: null, columns: 1, imported: false,
        },
      },
    },
  });
  expect(profile.ok()).toBeTruthy();
  expect((await profile.json()).ready).toBeTruthy();
}


async function createProject(page: Page, title: string, applicationType: "校招" | "实习" | "社招" = "实习") {
  await page.goto("/");
  await page.getByLabel("项目名称").fill(title);
  await page.getByLabel("公司名称 选填").fill("示例科技");
  await page.locator("label.type-option").filter({ hasText: applicationType }).click();
  await page.getByLabel("职位描述").fill("负责 Python API 开发、数据库性能优化与接口稳定性治理");
  await page.getByRole("button", { name: "创建项目并分析 JD" }).click();
  await expect(page.getByText("Word 真实分页预览")).toBeVisible({ timeout: 60_000 });
}


test("从经历库到针对岗位的简历和模拟面试", async ({ page, request }) => {
  const projectTitle = `后端工程师-${Date.now()}`;
  await seedProfile(request);
  await createProject(page, projectTitle, "实习");

  await page.getByRole("button", { name: /02\s*匹配分析/ }).click();
  const suggest = page.getByRole("button", { name: "生成适配建议" });
  await expect(suggest).toBeVisible({ timeout: 90_000 });
  await suggest.click();

  await page.getByRole("radio", { name: /快速优化/ }).check({ force: true });
  await page.getByRole("button", { name: "开始快速优化" }).click();
  await expect(page.getByText("可以逐条审阅")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText(/0\/\d+ 已同意/)).toBeVisible();

  await page.getByRole("button", { name: "同意这项" }).click();
  await page.getByLabel("我同意仅应用已勾选的建议").check();
  await page.getByRole("button", { name: /应用已同意的修改/ }).click();
  await expect(page.getByText(/已应用 1 条建议并生成新版本/)).toBeVisible({ timeout: 60_000 });

  await page.getByRole("button", { name: "专业双栏" }).click();
  await expect(page.getByRole("img", { name: /简历第 1 页/ })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/页 ·/)).toBeVisible();

  await page.getByRole("button", { name: "05 导出" }).click();
  await expect(page.getByRole("button", { name: /下载 Word 简历/ })).toBeEnabled();
  await page.getByRole("button", { name: "06 求职训练" }).click();
  await page.getByRole("link", { name: "进入面试 / 笔试训练" }).click();
  await page.getByRole("button", { name: /模拟面试/ }).click();
  await expect(page.getByText("请结合经历说明你如何保证 API 的稳定性？")).toBeVisible();
  await page.getByLabel("你的回答").fill("我通过指标、日志和链路追踪监控接口，并设置限流和降级策略。");
  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.getByRole("heading", { name: "本轮训练完成" })).toBeVisible();
});


test("深度优化经过审查返工后仍由用户确认", async ({ page, request }) => {
  test.setTimeout(180_000);
  const projectTitle = `深度优化-${Date.now()}`;
  await seedProfile(request);
  await createProject(page, projectTitle, "校招");

  await page.getByRole("button", { name: /04\s*建议确认/ }).click();
  await page.locator("fieldset.optimization-mode-selector label").filter({ hasText: "深度优化" }).click();
  await expect(page.getByRole("button", { name: "开始深度优化" })).toBeEnabled();
  await page.getByRole("button", { name: "开始深度优化" }).click();

  // Deep runs can pass reviewing between 1s polls; accept either live stage or ready outcome.
  await expect(page.getByText(/独立质量审查|可以逐条审阅/)).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("可以逐条审阅")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("深度优化已达到质量门槛")).toBeVisible();
  await expect(page.getByText(/0\/\d+ 已同意/)).toBeVisible();

  await page.getByRole("button", { name: "同意这项" }).click();
  await page.getByLabel("我同意仅应用已勾选的建议").check();
  await page.getByRole("button", { name: /应用已同意的修改/ }).click();
  await expect(page.getByText(/已应用 1 条建议并生成新版本/)).toBeVisible({ timeout: 60_000 });
});
