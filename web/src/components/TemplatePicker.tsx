import { TEMPLATES } from "../templates/registry";


export function TemplatePicker({ selected, recommended, onChange }: {
  selected: string;
  recommended?: string | null;
  onChange: (id: string) => void;
}) {
  const recommendation = TEMPLATES.find((item) => item.id === recommended);
  return (
    <section className="template-picker" aria-labelledby="template-title">
      <div className="panel-heading">
        <div><span className="panel-index">T</span><h2 id="template-title">简历模板</h2></div>
        {recommendation && <span>推荐：{recommendation.label}</span>}
      </div>
      <div className="template-grid">
        {TEMPLATES.map((template) => (
          <button
            type="button"
            className={`template-option ${selected === template.id ? "active" : ""}`}
            aria-label={template.label}
            aria-pressed={selected === template.id}
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
