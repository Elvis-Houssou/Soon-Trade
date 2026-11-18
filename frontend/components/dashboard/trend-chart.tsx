"use client";

import { useFormatter, useTranslations } from "next-intl";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/** `points` : un point par mois, `month` au format AAAA-MM, du plus ancien au plus récent. */
export function TrendChart({ points, unit }: { points: { month: string; value: number | string }[]; unit: string }) {
  const t = useTranslations("common");
  const format = useFormatter();
  const data = points.map((point) => {
    const [year, month] = point.month.split("-").map(Number);
    return {
      month: format.dateTime(new Date(Date.UTC(year, month - 1, 15)), { month: "short", timeZone: "UTC" }),
      value: Number(point.value),
    };
  });
  const summary = data.map((point) => `${point.month} : ${format.number(point.value)}`).join(", ");

  return (
    <figure>
      <div className="h-56" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.3} />
                <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
            <YAxis
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(value: number) => format.number(value, { notation: "compact" })}
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            />
            <Tooltip
              formatter={(value) => [`${format.number(Number(value))} ${unit}`, ""]}
              separator=""
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                color: "var(--foreground)",
              }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--primary)"
              strokeWidth={2.5}
              fill="url(#trend-fill)"
              dot={{ r: 3, fill: "var(--primary)", strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="sr-only">
        {t("chartCaption", { unit })} {summary}.
      </figcaption>
    </figure>
  );
}
