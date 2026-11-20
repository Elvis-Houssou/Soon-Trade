import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SOON TRADE",
    short_name: "SOON TRADE",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0f1f",
    theme_color: "#6c3bff",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png" },
    ],
  };
}
