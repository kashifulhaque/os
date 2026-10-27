/**
 * The course mark: a terminal prompt (chevron and cursor) on a rounded tile.
 * It appears in the header and on the sign-in page, so it lives in one place.
 * The favicon in index.html draws the same shape.
 */
export default function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect width="24" height="24" rx="6" fill="var(--primary)" />
      <path
        d="M6.5 8.5 11 12l-4.5 3.5"
        stroke="var(--on-primary)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="13" y="15" width="5" height="1.8" rx="0.9" fill="var(--on-primary)" />
    </svg>
  );
}
