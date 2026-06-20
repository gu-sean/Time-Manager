interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
}

export default function Toggle({ checked, onChange, label }: ToggleProps) {
  return (
    <button
      className={`tm-toggle-track ${checked ? 'on' : 'off'}`}
      type="button"
      onClick={() => onChange(!checked)}
      aria-label={label ?? '토글'}
    >
      <span className="tm-toggle-knob" />
    </button>
  );
}
