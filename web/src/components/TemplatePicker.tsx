import { TEMPLATES } from "../templates/registry";


export function TemplatePicker({ selected, recommended, onChange, disabled = false }: {
  selected: string;
  recommended?: string | null;
  onChange: (id: string) => void;
  disabled?: boolean;
}) {
  const recommendation = TEMPLATES.find((item) => item.id === recommended);
  return (
    <section className={`template-picker${disabled ? " is-disabled" : ""}`} aria-labelledby="template-title">
      <div className="panel-heading">
        <div><span className="panel-index">T</span><h2 id="template-title">简历模板</h2></div>
        {recommendation && <span>推荐：{recommendation.label}</span>}
      </div>
      {disabled && <p className="panel-note">优化进行中，模板已冻结；结束后可再切换。</p>}
      <div className="template-grid">
        {TEMPLATES.map((template) => (
          <button
            type="button"
            className={`template-option ${selected === template.id ? "active" : ""}`}
            aria-label={template.label}
            aria-pressed={selected === template.id}
            disabled={disabled}
            onClick={() => onChange(template.id)}
            key={template.id}
          >
            <span className={`template-thumbnail thumbnail-${template.id}`} aria-hidden="true"><i /><i /><i /><i /></span>
            <strong>{template.label}</strong>
            <small>{template.description}</small>
          </button>
        ))}
      </div>
    </section>
  );
}
