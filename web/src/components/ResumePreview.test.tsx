import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { blankResume } from "../resume";
import { ResumePreview } from "./ResumePreview";


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});


function mockPreviewPages(pages: number) {
  const payload = {
    page_count: pages,
    pages: Array.from({ length: pages }, () => "iVBORw0KGgo="),
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/preview/pages")) {
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/preview/pdf")) {
      return new Response(new Blob(["%PDF-1.4"], { type: "application/pdf" }), {
        status: 200,
        headers: { "Content-Type": "application/pdf", "X-Resume-Page-Count": String(pages) },
      });
    }
    return new Response("not found", { status: 404 });
  }));
}


test("校招超一页时展示 Word 分页图与溢出提示", async () => {
  mockPreviewPages(3);
  const resume = blankResume();
  resume.basics.name = "张宁";

  render(
    <ResumePreview
      projectId="proj-1"
      resume={resume}
      templateId="clear-single"
      applicationType="campus"
    />,
  );

  await waitFor(() => {
    expect(screen.getByText(/内容已超出第 1 页（共 3 页）/)).toBeInTheDocument();
  });
  expect(screen.getByRole("button", { name: "下载 PDF" })).toBeEnabled();
  expect(screen.getAllByRole("img", { name: /简历第 \d+ 页/ })).toHaveLength(3);
  expect(screen.getByText(/LaTeX 真实分页预览/)).toBeInTheDocument();
});


test("社招多页仅显示页数，不显示一页溢出警告", async () => {
  mockPreviewPages(2);
  const resume = blankResume();
  resume.basics.name = "张宁";

  render(
    <ResumePreview
      projectId="proj-2"
      resume={resume}
      templateId="career-depth"
      applicationType="experienced"
    />,
  );

  await waitFor(() => {
    expect(screen.getByText(/2 页 · 与导出 LaTeX 同源排版/)).toBeInTheDocument();
  });
  expect(screen.queryByText(/内容已超出第 1 页/)).not.toBeInTheDocument();
  expect(screen.getAllByRole("img", { name: /简历第 \d+ 页/ })).toHaveLength(2);
});


test("缺少 LaTeX 编译器时切换浏览器预览", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(
    JSON.stringify({ detail: { code: "PREVIEW_UNAVAILABLE", message: "未找到 LibreOffice（soffice），无法生成 PDF 预览" } }),
    { status: 503, headers: { "Content-Type": "application/json" } },
  )));

  render(
    <ResumePreview
      projectId="proj-3"
      resume={blankResume()}
      templateId="clear-single"
      applicationType="campus"
    />,
  );

  await waitFor(() => expect(screen.getByLabelText("简历浏览器预览")).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "下载 PDF" })).toBeDisabled();
});
