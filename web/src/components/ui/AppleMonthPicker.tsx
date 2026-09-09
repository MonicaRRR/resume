import { useEffect, useId, useMemo, useRef, useState } from "react";


const MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];


function parseValue(value: string): { year: number; month: number } | null {
  if (!/^\d{4}-\d{2}$/.test(value)) return null;
  const [yearText, monthText] = value.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  if (!year || month < 1 || month > 12) return null;
  return { year, month };
}


function formatValue(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}


function formatLabel(value: string): string {
  const parsed = parseValue(value);
  if (!parsed) return "选择年月";
  return `${parsed.year}年${parsed.month}月`;
}


type Props = {
  value: string;
  onChange: (value: string) => void;
  "aria-label"?: string;
  disabled?: boolean;
  className?: string;
};


export function AppleMonthPicker({
  value,
  onChange,
  "aria-label": ariaLabel,
  disabled = false,
  className = "",
}: Props) {
  const now = useMemo(() => new Date(), []);
  const initial = parseValue(value) ?? { year: now.getFullYear(), month: now.getMonth() + 1 };
  const [open, setOpen] = useState(false);
  const [viewYear, setViewYear] = useState(initial.year);
  const rootRef = useRef<HTMLDivElement>(null);
  const popoverId = useId();

  useEffect(() => {
    if (!open) return;
    const parsed = parseValue(value);
    if (parsed) setViewYear(parsed.year);
  }, [open, value]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = parseValue(value);

  return (
    <div className={`apple-month ${open ? "open" : ""} ${className}`.trim()} ref={rootRef}>
      <button
        type="button"
        className="apple-month-trigger"
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={popoverId}
        disabled={disabled}
        onClick={() => !disabled && setOpen((current) => !current)}
      >
        <span data-placeholder={!selected || undefined}>{formatLabel(value)}</span>
      </button>
      <div className="apple-month-popover" id={popoverId} role="dialog" data-open={open} aria-hidden={!open}>
        <div className="apple-month-nav">
          <button type="button" aria-label="上一年" tabIndex={open ? 0 : -1} onClick={() => setViewYear((year) => year - 1)}>‹</button>
          <strong>{viewYear}年</strong>
          <button type="button" aria-label="下一年" tabIndex={open ? 0 : -1} onClick={() => setViewYear((year) => year + 1)}>›</button>
        </div>
        <div className="apple-month-grid">
          {MONTHS.map((label, index) => {
            const month = index + 1;
            const isSelected = selected?.year === viewYear && selected.month === month;
            return (
              <button
                key={label}
                type="button"
                tabIndex={open ? 0 : -1}
                className={isSelected ? "selected" : undefined}
                aria-selected={isSelected}
                onClick={() => {
                  onChange(formatValue(viewYear, month));
                  setOpen(false);
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
        {value ? (
          <button
            type="button"
            className="text-button"
            tabIndex={open ? 0 : -1}
            style={{ justifySelf: "center", marginTop: 4 }}
            onClick={() => {
              onChange("");
              setOpen(false);
            }}
          >
            清除
          </button>
        ) : null}
      </div>
    </div>
  );
}
