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
  const match = value.trim().match(/^(\d{0,4})(?:-(\d{0,2})(?:-(\d{0,2}))?)?$/);
  if (!match) return { year: value.replace(/\D/g, "").slice(0, 4), month: "", day: "" };
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


function serializeParts(parts: Parts, precision: DatePrecision): string {
  if (!parts.year && !parts.month && !parts.day) return "";
  let value = parts.year;
  if (parts.month || parts.day) value += `-${parts.month}`;
  if (precision === "day" && parts.day) value += `-${parts.day}`;
  return value;
}


function digitsOnly(raw: string): string {
  return raw.replace(/\D/g, "");
}


type Props = {
  value: string;
  onChange: (value: string) => void;
  precision?: DatePrecision;
  minYear?: number;
  maxYear?: number;
  "aria-label"?: string;
  disabled?: boolean;
  invalid?: boolean;
  errorMessage?: string;
};

export function dateRangeIsReversed(start: string, end: string): boolean {
  const startMatch = start.trim().match(/^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?$/);
  const endMatch = end.trim().match(/^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?$/);
  if (!startMatch || !endMatch) return false;
  const startKey = Number(startMatch[1]) * 10_000
    + Number(startMatch[2] || 1) * 100
    + Number(startMatch[3] || 1);
  const endKey = Number(endMatch[1]) * 10_000
    + Number(endMatch[2] || 12) * 100
    + Number(endMatch[3] || 31);
  return startKey > endKey;
}

export function dateValueIsInvalid(
  value: string,
  precision: DatePrecision,
  minYear = DEFAULT_MIN_YEAR,
  maxYear = currentYear(),
): boolean {
  if (!value.trim()) return false;
  const parts = parseParts(value);
  const year = Number(parts.year);
  if (parts.year.length !== 4 || !Number.isInteger(year) || year < minYear || year > maxYear) return true;
  if (parts.month) {
    const month = Number(parts.month);
    if (!Number.isInteger(month) || month < 1 || month > 12) return true;
  }
  if (precision === "day" && parts.day) {
    const day = Number(parts.day);
    if (!Number.isInteger(day) || day < 1 || day > daysInMonth(parts.year, parts.month, minYear, maxYear)) return true;
  }
  return false;
}


export function AppleDateParts({
  value,
  onChange,
  precision = "month",
  minYear = DEFAULT_MIN_YEAR,
  maxYear = currentYear(),
  "aria-label": ariaLabel = "日期",
  disabled = false,
  invalid = false,
  errorMessage = "",
}: Props) {
  const [draft, setDraft] = useState<Parts>(() => parseParts(value));
  const cappedMaxYear = Math.max(minYear, maxYear);
  const maxDay = daysInMonth(draft.year, draft.month, minYear, cappedMaxYear);

  useEffect(() => {
    if (value !== serializeParts(draft, precision)) {
      setDraft(parseParts(value));
    }
    // Only re-sync when the external value changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, precision, minYear, cappedMaxYear]);

  function commit(next: Parts) {
    const safe = precision === "month" ? { ...next, day: "" } : next;
    setDraft(safe);
    onChange(serializeParts(safe, precision));
  }

  function onYearChange(raw: string) {
    commit({ ...draft, year: digitsOnly(raw).slice(0, 4) });
  }

  function onMonthChange(raw: string) {
    const month = digitsOnly(raw).slice(0, 2);
    commit({ ...draft, month });
  }

  function onDayChange(raw: string) {
    const day = digitsOnly(raw).slice(0, 2);
    commit({ ...draft, day });
  }

  function onYearBlur() {
    commit(draft);
  }

  function onMonthBlur() {
    const month = Number(draft.month);
    commit(
      draft.month && Number.isInteger(month) && month >= 1 && month <= 12
        ? { ...draft, month: String(month).padStart(2, "0") }
        : draft,
    );
  }

  function onDayBlur() {
    const day = Number(draft.day);
    commit(
      draft.day && Number.isInteger(day) && day >= 1 && day <= maxDay
        ? { ...draft, day: String(day).padStart(2, "0") }
        : draft,
    );
  }

  const yearNumber = Number(draft.year);
  const monthNumber = Number(draft.month);
  const dayNumber = Number(draft.day);
  const yearInvalid = Boolean(draft.year) && (
    draft.year.length !== 4
    || !Number.isInteger(yearNumber)
    || yearNumber < minYear
    || yearNumber > cappedMaxYear
  );
  const monthInvalid = Boolean(draft.month) && (
    !Number.isInteger(monthNumber) || monthNumber < 1 || monthNumber > 12
  );
  const dayInvalid = precision === "day" && Boolean(draft.day) && (
    !Number.isInteger(dayNumber) || dayNumber < 1 || dayNumber > maxDay
  );
  const hasInvalidPart = yearInvalid || monthInvalid || dayInvalid;
  const showInvalid = invalid || hasInvalidPart;
  const partMessage = yearInvalid
    ? `年份需在 ${minYear}–${cappedMaxYear} 之间`
    : monthInvalid
      ? "月份需在 1–12 之间"
      : dayInvalid
        ? `日期需在 1–${maxDay} 之间`
        : "";

  return (
    <div
      className={`apple-date-parts precision-${precision}${showInvalid ? " is-invalid" : ""}`}
      role="group"
      aria-label={ariaLabel}
      aria-invalid={showInvalid || undefined}
    >
      <label className="apple-date-field">
        <span>年</span>
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          aria-label={`${ariaLabel} 年`}
          placeholder="YYYY"
          aria-invalid={(invalid || yearInvalid) || undefined}
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
          placeholder="MM"
          aria-invalid={(invalid || monthInvalid) || undefined}
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
            placeholder="DD"
            aria-invalid={(invalid || dayInvalid) || undefined}
            disabled={disabled}
            value={draft.day}
            onChange={(event) => onDayChange(event.target.value)}
            onBlur={onDayBlur}
          />
        </label>
      ) : null}
      {(errorMessage || partMessage) && (
        <p className="apple-date-error" role="alert">{errorMessage || partMessage}</p>
      )}
    </div>
  );
}
