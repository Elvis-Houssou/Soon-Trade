"use client";

import { animate, useReducedMotion } from "motion/react";
import { useFormatter } from "next-intl";
import { useEffect, useRef } from "react";

/** Compte jusqu'à la valeur à l'affichage. La valeur finale est rendue côté serveur. */
export function AnimatedNumber({ value }: { value: number }) {
  const node = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const format = useFormatter();

  useEffect(() => {
    if (reduced || !node.current) return;
    const element = node.current;
    const controls = animate(0, value, {
      duration: 0.8,
      ease: "easeOut",
      onUpdate: (latest) => {
        element.textContent = format.number(Math.round(latest));
      },
    });
    return () => controls.stop();
  }, [value, reduced, format]);

  return <span ref={node}>{format.number(value)}</span>;
}
