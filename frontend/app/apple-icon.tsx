import { ImageResponse } from "next/og";

// Écran d'accueil iOS : carré plein, iOS arrondit lui-même les coins. Même dessin que icon.svg.
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(170deg, #62a8ff, #5f71ff 50%, #8532ef)",
        }}
      >
        <svg width="140" height="140" viewBox="0 0 64 64">
          <path
            d="M32 32C28 26 24.5 24 21 24a8 8 0 0 0 0 16c3.5 0 7-2 11-8s7.5-8 11-8a8 8 0 0 1 0 16c-3.5 0-7-2-11-8Z"
            fill="none"
            stroke="#fff"
            strokeWidth="4.5"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    size,
  );
}
