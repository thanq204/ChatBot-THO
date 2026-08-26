/** Intrinsic size of public/tho-mascot.png, used to derive width from height. */
const ASPECT = 269 / 302;

/**
 * The product mascot, as artwork.
 *
 * Decorative by default: everywhere it appears, the product is already named in
 * adjacent text, so an alt string would only make a screen reader say the name
 * twice. Pass `label` for a placement where it stands alone.
 *
 * Sized by height — the art is taller than it is wide, and both width and
 * height attributes are emitted so the browser reserves the right box before
 * the PNG loads instead of shifting the layout under it.
 */
export default function ThoMascot({ height = 74, className = "", label = "" }) {
  const width = Math.round(height * ASPECT);

  // Height goes out as a custom property rather than an inline `height`, so a
  // breakpoint can scale the art down with a plain rule. An inline style would
  // outrank the stylesheet and force !important at every override.
  return (
    <span className={`tho-mascot ${className}`.trim()} style={{ "--mascot-h": `${height}px` }}>
      <img
        src="/tho-mascot.png"
        alt={label}
        aria-hidden={label ? undefined : "true"}
        width={width}
        height={height}
      />
    </span>
  );
}
