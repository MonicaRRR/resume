import { useEffect, useState } from "react";

import { api, ApiError, downloadPreviewPdf } from "../api/client";
import { isOnePageApplication } from "../resume";
import type { ApplicationType, ResumeDocument } from "../types";


const PREVIEW_DEBOUNCE_MS = 450;


export function ResumePreview({
  projectId,
  resume,
  templateId,
  applicationType,
  targetRole = "",
  onOverflowChange,
  variant = "default",
}: {
  projectId: string;
  resume: ResumeDocument;
  templateId: string;
  applicationType: ApplicationType;
  targetRole?: string;
  onOverflowChange?: (overflow: boolean) => void;
  variant?: "default" | "annotation";
}) {
  const onePagePolicy = isOnePageApplication(applicationType);
  const annotationMode = variant === "annotation";
  const [pageCount, setPageCount] = useState(1);
  const [pageImages, setPageImages] = useState<string[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [fallback, setFallback] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const overflow = onePagePolicy && pageCount > 1;
  useEffect(() => onOverflowChange?.(overflow), [onOverflowChange, overflow]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setStatus("loading");
      setErrorMessage("");
      setFallback(false);
      try {
        const result = await api.previewPages(projectId, resume, templateId, controller.signal);
        if (cancelled) return;
        setPageImages(result.pages.map((page) => `data:image/png;base64,${page}`));
        setPageCount(result.page_count);
        setStatus("ready");
      } catch (error) {
        if (cancelled || (error instanceof DOMException && error.name === "AbortError")) return;
        setStatus("error");
        setErrorMessage(error instanceof ApiError ? error.message : "预览生成失败");
        setFallback(error instanceof ApiError && error.code === "PREVIEW_UNAVAILABLE");
        setPageCount(1);
        setPageImages([]);
      }
    }, PREVIEW_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [projectId, resume, templateId]);

  const savePdf = async () => {
    setDownloading(true);
    try {
      await downloadPreviewPdf(projectId, resume, templateId, "resume-preview.pdf");
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "PDF 下载失败");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <section
      className={`preview-panel pdf-preview ${onePagePolicy ? "compact-preview" : ""}${annotationMode ? " annotation-pdf-preview" : ""}`}
      aria-label="简历预览"
    >
      <div className="preview-toolbar">
        <div>
            <strong>{annotationMode ? "与导出同源 · 批注审阅" : fallback ? "浏览器预览（LaTeX 编译器未安装）" : "LaTeX 真实分页预览"}</strong>
          <span>
            {status === "loading"
              ? "正在用 LaTeX 引擎排版…"
              : status === "error"
                ? errorMessage
                : annotationMode
                  ? `${pageCount} 页 · 与导出 LaTeX/PDF 同一排版`
                  : onePagePolicy
                    ? (overflow
                      ? `实际 ${pageCount} 页 · 建议压到 1 页，也可直接导出`
                      : "当前 1 页 · 符合校招/实习页数建议")
                    : `${pageCount} 页 · 与导出 LaTeX 同源排版`}
          </span>
        </div>
        <button type="button" disabled={status !== "ready" || downloading} onClick={() => void savePdf()}>
          {downloading ? "正在导出…" : "下载 PDF"}
        </button>
      </div>
      {overflow && status === "ready" && (
        <div className="overflow-warning" role="alert">
          <strong>内容已超出第 1 页（共 {pageCount} 页）</strong>
          <span>以下为 LaTeX 的真实分页结果；校招/实习仍建议压到 1 页，也可直接导出。</span>
        </div>
      )}
      <div className="pdf-stage">
        {status === "loading" && pageImages.length === 0 && (
          <div className="pdf-status" role="status">正在生成 LaTeX → PDF 预览…</div>
        )}
        {status === "loading" && pageImages.length > 0 && (
          <div className="pdf-refresh" role="status">正在按最新内容重新排版…</div>
        )}
        {status === "error" && fallback && (
          <div className="resume-html-fallback" aria-label="简历浏览器预览">
            <h1>{resume.basics.name || "未填写姓名"}</h1>
            <p>{[targetRole || resume.basics.target_role.value, resume.basics.email, resume.basics.phone].filter(Boolean).join(" · ")}</p>
            {resume.basics.summary.value && <section><h2>个人简介</h2><p>{resume.basics.summary.value}</p></section>}
            {resume.education.length > 0 && <section><h2>教育经历</h2>{resume.education.map((item) => <p key={item.id}><strong>{item.institution}</strong> · {item.degree} · {item.field} · {item.start_date}—{item.end_date}</p>)}</section>}
            {resume.work_experience.length > 0 && <section><h2>实习/工作经历</h2>{resume.work_experience.map((item) => <div key={item.id}><p><strong>{item.company}</strong> · {item.title} · {item.start_date}—{item.end_date}</p>{item.bullets.map((bullet, index) => <p key={`${item.id}-b-${index}`}>• {bullet.value}</p>)}</div>)}</section>}
            {resume.projects.length > 0 && <section><h2>项目经历</h2>{resume.projects.map((item) => <div key={item.id}><p><strong>{item.name}</strong> · {item.role} · {item.start_date}—{item.end_date}</p>{item.bullets.map((bullet, index) => <p key={`${item.id}-b-${index}`}>• {bullet.value}</p>)}</div>)}</section>}
            {resume.skills.length > 0 && <section><h2>专业技能</h2><p>{resume.skills.flatMap((group) => group.items.map((item) => item.value)).join(" · ")}</p></section>}
            <p className="preview-fallback-note">已切换为浏览器预览；安装 XeLaTeX 后可生成与导出一致的 PDF。</p>
          </div>
        )}
        {status === "error" && !fallback && (
          <div className="pdf-status pdf-status-error" role="alert">
            <strong>预览暂时不可用</strong>
            <span>{errorMessage || "请安装 XeLaTeX，或使用浏览器预览。"}</span>
          </div>
        )}
        {pageImages.length > 0 && status !== "error" && (
          <div className={`pdf-pages${status === "loading" ? " pdf-pages-refreshing" : ""}`}>
            {pageImages.map((src, index) => (
              <figure className="pdf-page" key={`page-${index}`}>
                <figcaption className="resume-page-meta">第 {index + 1} / {pageCount} 页</figcaption>
                <img src={src} alt={`简历第 ${index + 1} 页`} className="pdf-page-image" />
              </figure>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
