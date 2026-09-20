import { useState, type KeyboardEvent } from "react";
import { useLocations } from "../hooks/useMetadata";

interface Props { value: string; error?: string; onType: (value: string) => void; onSelect: (value: string) => void }

export function LocationPicker({ value, error, onType, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [retry, setRetry] = useState(0);
  const resource = useLocations(value.trim(), retry);
  const options = resource.data?.values ?? [];
  const choose = (option: string) => { onSelect(option); setOpen(false); setActive(-1); };
  const keyboard = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault(); setOpen(true);
      setActive((previous) => options.length === 0 ? -1 :
        event.key === "ArrowDown" ? (previous + 1) % options.length : (previous - 1 + options.length) % options.length);
    } else if (event.key === "Enter" && open && active >= 0 && options[active]) {
      event.preventDefault(); choose(options[active]);
    } else if (event.key === "Escape") { event.preventDefault(); setOpen(false); }
  };
  return (
    <div className="field location-field">
      <label htmlFor="location">Location <span className="required-label">Required</span></label>
      <div className="combobox-wrap" onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}>
        <input id="location" role="combobox" aria-autocomplete="list" autoComplete="off"
          aria-expanded={open} aria-controls={open ? "location-options" : undefined}
          aria-activedescendant={open && options[active] ? `location-option-${active}` : undefined}
          aria-describedby={error ? "location-help location-error" : "location-help"}
          aria-invalid={Boolean(error)} maxLength={80} placeholder="Indiranagar"
          value={value} onFocus={() => setOpen(true)}
          onChange={(event) => { onType(event.target.value); setActive(-1); setOpen(true); }} onKeyDown={keyboard} />
        {open && <div className="location-popup">
          <ul id="location-options" role="listbox" aria-label="Bengaluru localities">
            {options.map((option, index) => <li id={`location-option-${index}`} key={option} role="option" aria-selected={active === index}
              onMouseDown={(event) => event.preventDefault()} onClick={() => choose(option)}>
              <span>{option}</span><span aria-hidden="true">↗</span>
            </li>)}
          </ul>
          {resource.status === "loading" && <p role="status">Finding localities…</p>}
          {resource.status === "ready" && options.length === 0 && <p>No locality found. Coverage is Bengaluru only; try another locality.</p>}
          {resource.status === "error" && <p role="alert">Localities could not load. <button type="button" className="text-button"
            onMouseDown={(event) => event.preventDefault()} onClick={() => setRetry((count) => count + 1)}>Retry localities</button></p>}
        </div>}
      </div>
      <p className="field-help" id="location-help">Currently available in select neighbourhoods</p>
      {error && <p className="field-error" id="location-error" role="alert">{error}</p>}
    </div>
  );
}
