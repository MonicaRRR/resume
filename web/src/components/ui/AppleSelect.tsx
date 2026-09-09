import { useEffect, useId, useRef, useState } from "react";


export type AppleSelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};


type Props = {
  value: string;
  options: AppleSelectOption[];
  onChange: (value: string) => void;
  "aria-label"?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
};


export function AppleSelect({
  value,
  options,
  onChange,
  "aria-label": ariaLabel,
  placeholder = "请选择",
  required = false,
  disabled = false,
  className = "",
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();
  const selected = options.find((option) => option.value === value);

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

  return (
    <div className={`apple-select ${open ? "open" : ""} ${className}`.trim()} ref={rootRef}>
      <button
        type="button"
        className="apple-select-trigger"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-required={required || undefined}
        disabled={disabled}
        onPointerDown={() => { /* highlight on press via CSS :active */ }}
        onClick={() => !disabled && setOpen((current) => !current)}
      >
        <span data-placeholder={!selected || undefined}>{selected?.label || placeholder}</span>
      </button>
      <div className="apple-select-menu" id={listId} role="listbox" data-open={open} aria-hidden={!open}>
        {options.map((option) => (
          <button
            key={option.value || "__empty"}
            type="button"
            role="option"
            tabIndex={open ? 0 : -1}
            className={`apple-select-option${option.value === value ? " selected" : ""}`}
            aria-selected={option.value === value}
            disabled={option.disabled}
            onClick={() => {
              onChange(option.value);
              setOpen(false);
            }}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
