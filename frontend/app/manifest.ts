import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SOON TRADE",
    short_name: "SOON TRADE",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0f1f",
    theme_color: "#6c3bff",
    icons: [{ src: "/brand/icons/icon-gradient-192.png", sizes: "192x192", type: "image/png" }],
  };
}
