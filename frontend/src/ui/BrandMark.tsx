import { copy } from "../copy";

/** Chimera's mark in the ZD BrandMark style: two forms (circle A, diamond B) joined by one arc. */
export function BrandMark() {
  return (
    <div className="brand">
      <span className="brand__mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" focusable="false">
          <path d="M7.5 21.5c2.2-6.4 5.6-9.6 8.5-9.6s6.3 3.2 8.5 9.6" className="brand__arc" />
          <circle cx="10.5" cy="11.5" r="3" className="brand__a" />
          <path d="M21.5 8.2l3.3 3.3-3.3 3.3-3.3-3.3z" className="brand__b" />
        </svg>
      </span>
      <span className="brand__text">
        <h1 className="brand__name">{copy.app.name}</h1>
        <span className="brand__kicker">{copy.app.kicker}</span>
      </span>
    </div>
  );
}
