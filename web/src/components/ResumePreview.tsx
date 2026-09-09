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
  onOverflowChange,
}: {
  projectId: string;
  resume: ResumeDocument;
  templateId: string;
  applicationType: ApplicationType;
  onOverflowChange?: (overflow: boolean) => void;
}) {
  const onePagePolicy = isOnePageApplication(applicationType);
  const [pageCount, setPageCount] = useState(1);
  const [pageImages, setPageImages] = useState<string[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [downloading, setDownloading] = useState(false);

  const overflow = onePagePolicy && pageCount > 1;
  useEffect(() => onOverflowChange?.(overflow), [onOverflowChange, overflow]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setStatus("loading");
      setErrorMessage("");
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
    <section className={`preview-panel pdf-preview ${onePagePolicy ? "compact-preview" : ""}`} aria-label="简历预览">
      <div className="preview-toolbar">
        <div>
          <strong>Word 真实分页预览</strong>
          <span>
            {status === "loading"
              ? "正在用 Word 引擎排版…"
              : status === "error"
                ? errorMessage
                : onePagePolicy
                  ? (overflow
                    ? `实际 ${pageCount} 页 · 建议压到 1 页，也可直接导出`
                    : "当前 1 页 · 符合校招/实习页数建议")
                  : `${pageCount} 页 · 与导出 Word 同源排版`}
          </span>
        </div>
        <button type="button" disabled={status !== "ready" || downloading} onClick={() => void savePdf()}>
          {downloading ? "正在导出…" : "下载 PDF"}
        </button>
      </div>
      {overflow && status === "ready" && (
        <div className="overflow-warning" role="alert">
          <strong>内容已超出第 1 页（共 {pageCount} 页）</strong>
          <span>以下为 LibreOffice 按 Word 文档真实分页的结果；校招/实习仍建议压到 1 页，也可直接导出。</span>
        </div>
      )}
      <div className="pdf-stage">
        {status === "loading" && pageImages.length === 0 && (
          <div className="pdf-status" role="status">正在生成 Word → PDF 预览…</div>
        )}
        {status === "loading" && pageImages.length > 0 && (
          <div className="pdf-refresh" role="status">正在按最新内容重新排版…</div>
        )}
        {status === "error" && (
          <div className="pdf-status pdf-status-error" role="alert">
            <strong>预览暂时不可用</strong>
            <span>{errorMessage || "请确认本机已安装 LibreOffice，或直接导出 Word 查看。"}</span>
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
