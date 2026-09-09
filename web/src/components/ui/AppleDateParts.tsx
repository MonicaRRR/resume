import { useEffect, useState } from "react";


export type DatePrecision = "month" | "day";

type Parts = {
  year: string;
  month: string;
  day: string;
};


const DEFAULT_MIN_YEAR = 2020;


function currentYear(): number {
  return new Date().getFullYear();
}


function parseParts(value: string): Parts {
  const match = value.trim().match(/^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?$/);
  if (!match) return { year: "", month: "", day: "" };
  return {
    year: match[1] ?? "",
    month: match[2] ? String(Number(match[2])) : "",
    day: match[3] ? String(Number(match[3])) : "",
  };
}


function daysInMonth(yearText: string, monthText: string, minYear: number, maxYear: number): number {
  const month = Number(monthText);
  if (!Number.isInteger(month) || month < 1 || month > 12) return 31;
  const year = Number(yearText);
  if (Number.isInteger(year) && year >= minYear && year <= maxYear) {
    return new Date(year, month, 0).getDate();
  }
  if (month === 2) return 29;
  if ([4, 6, 9, 11].includes(month)) return 30;
  return 31;
}


function pad2(value: string): string {
  return String(Number(value)).padStart(2, "0");
}


function formatParts(parts: Parts, precision: DatePrecision, minYear: number, maxYear: number): string {
  const yearNum = Number(parts.year);
  if (parts.year.length !== 4 || !Number.isInteger(yearNum) || yearNum < minYear || yearNum > maxYear) {
    return "";
  }
  const monthNum = Number(parts.month);
  if (!parts.month || !Number.isInteger(monthNum) || monthNum < 1 || monthNum > 12) {
    return String(yearNum);
  }
  if (precision === "month") {
    return `${yearNum}-${pad2(parts.month)}`;
  }
  const maxDay = daysInMonth(parts.year, parts.month, minYear, maxYear);
  const dayNum = Number(parts.day);
  if (!parts.day || !Number.isInteger(dayNum) || dayNum < 1 || dayNum > maxDay) {
    return `${yearNum}-${pad2(parts.month)}`;
  }
  return `${yearNum}-${pad2(parts.month)}-${pad2(parts.day)}`;
}


function digitsOnly(raw: string): string {
  return raw.replace(/\D/g, "");
}


function clampDay(parts: Parts, minYear: number, maxYear: number): Parts {
  if (!parts.day) return parts;
  const maxDay = daysInMonth(parts.year, parts.month, minYear, maxYear);
  const dayNum = Number(parts.day);
  if (!Number.isInteger(dayNum)) return { ...parts, day: "" };
  if (dayNum > maxDay) return { ...parts, day: String(maxDay) };
  if (dayNum < 1) return { ...parts, day: "1" };
  return parts;
}


type Props = {
  value: string;
  onChange: (value: string) => void;
  precision?: DatePrecision;
  minYear?: number;
  maxYear?: number;
  "aria-label"?: string;
  disabled?: boolean;
};


export function AppleDateParts({
  value,
  onChange,
  precision = "month",
  minYear = DEFAULT_MIN_YEAR,
  maxYear = currentYear(),
  "aria-label": ariaLabel = "日期",
  disabled = false,
}: Props) {
  const [draft, setDraft] = useState<Parts>(() => parseParts(value));
  const cappedMaxYear = Math.max(minYear, maxYear);
  const maxDay = daysInMonth(draft.year, draft.month, minYear, cappedMaxYear);

  useEffect(() => {
    if (value !== formatParts(draft, precision, minYear, cappedMaxYear)) {
      setDraft(parseParts(value));
    }
    // Only re-sync when the external value changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, precision, minYear, cappedMaxYear]);

  function commit(next: Parts) {
    const safe = precision === "month"
      ? { ...next, day: "" }
      : clampDay(next, minYear, cappedMaxYear);
    setDraft(safe);
    onChange(formatParts(safe, precision, minYear, cappedMaxYear));
  }

  function onYearChange(raw: string) {
    commit({ ...draft, year: digitsOnly(raw).slice(0, 4) });
  }

  function onMonthChange(raw: string) {
    let month = digitsOnly(raw).slice(0, 2);
    if (month.length === 2) {
      const monthNum = Number(month);
      month = String(Math.min(12, Math.max(1, monthNum || 1)));
    } else if (month === "0") {
      // allow typing 01–09; keep single 0 until next digit or blur
    }
    commit(clampDay({ ...draft, month }, minYear, cappedMaxYear));
  }

  function onDayChange(raw: string) {
    let day = digitsOnly(raw).slice(0, 2);
    const limit = daysInMonth(draft.year, draft.month, minYear, cappedMaxYear);
    if (day.length === 2 || Number(day) > limit) {
      const dayNum = Number(day);
      day = String(Math.min(limit, Math.max(1, dayNum || 1)));
    }
    commit({ ...draft, day });
  }

  function onYearBlur() {
    if (!draft.year) {
      commit({ ...draft, year: "" });
      return;
    }
    if (draft.year.length < 4) {
      commit({ ...draft, year: "" });
      return;
    }
    const yearNum = Number(draft.year);
    commit({
      ...draft,
      year: String(Math.min(cappedMaxYear, Math.max(minYear, yearNum))),
    });
  }

  function onMonthBlur() {
    if (!draft.month) {
      commit({ ...draft, month: "" });
      return;
    }
    const monthNum = Number(draft.month);
    if (!Number.isInteger(monthNum) || monthNum < 1) {
      commit({ ...draft, month: "" });
      return;
    }
    commit(clampDay({ ...draft, month: String(Math.min(12, monthNum)) }, minYear, cappedMaxYear));
  }

  function onDayBlur() {
    if (!draft.day) {
      commit({ ...draft, day: "" });
      return;
    }
    const dayNum = Number(draft.day);
    const limit = daysInMonth(draft.year, draft.month, minYear, cappedMaxYear);
    if (!Number.isInteger(dayNum) || dayNum < 1) {
      commit({ ...draft, day: "" });
      return;
    }
    commit({ ...draft, day: String(Math.min(limit, dayNum)) });
  }

  return (
    <div className={`apple-date-parts precision-${precision}`} role="group" aria-label={ariaLabel}>
      <label className="apple-date-field">
        <span>年</span>
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          aria-label={`${ariaLabel} 年`}
          placeholder={`${minYear}-${cappedMaxYear}`}
          disabled={disabled}
          value={draft.year}
          onChange={(event) => onYearChange(event.target.value)}
          onBlur={onYearBlur}
        />
      </label>
      <label className="apple-date-field">
        <span>月</span>
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          aria-label={`${ariaLabel} 月`}
          placeholder="1-12"
          disabled={disabled}
          value={draft.month}
          onChange={(event) => onMonthChange(event.target.value)}
          onBlur={onMonthBlur}
        />
      </label>
      {precision === "day" ? (
        <label className="apple-date-field">
          <span>日</span>
          <input
            type="text"
            inputMode="numeric"
            autoComplete="off"
            aria-label={`${ariaLabel} 日`}
            placeholder={`1-${maxDay}`}
            disabled={disabled}
            value={draft.day}
            onChange={(event) => onDayChange(event.target.value)}
            onBlur={onDayBlur}
          />
        </label>
      ) : null}
    </div>
  );
}
