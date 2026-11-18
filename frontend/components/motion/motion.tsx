"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollToPlugin } from "gsap/ScrollToPlugin";
import { type ReactNode, type RefObject, useEffect, useRef } from "react";

gsap.registerPlugin(useGSAP, ScrollToPlugin);

const EASE = "expo.out";
const FULL = "(prefers-reduced-motion: no-preference)";
const REDUCED = "(prefers-reduced-motion: reduce)";

function placeMarker(
  root: HTMLElement | null,
  marker: HTMLElement | null,
  placed: RefObject<boolean>,
  animate: boolean,
) {
  if (!root || !marker) return;
  const target = root.querySelector<HTMLElement>('[aria-current="page"]');
  // Menu mobile fermé : rien à mesurer, l'observateur repositionnera à l'ouverture.
  if (!target?.offsetHeight) {
    gsap.set(marker, { autoAlpha: 0 });
    placed.current = false;
    return;
  }
  const vars = { y: target.offsetTop, height: target.offsetHeight, autoAlpha: 1 };
  if (animate && placed.current && !window.matchMedia(REDUCED).matches) {
    gsap.to(marker, { ...vars, duration: 0.45, ease: EASE, overwrite: true });
  } else {
    gsap.set(marker, vars);
  }
  placed.current = true;
}

/**
 * Indicateur de navigation : il glisse d'un lien à l'autre pour montrer d'où l'on vient.
 * `root` doit être positionné ; le lien actif porte `aria-current="page"`.
 */
export function useSlidingMarker(
  root: RefObject<HTMLElement | null>,
  marker: RefObject<HTMLElement | null>,
  activeKey: string,
) {
  const placed = useRef(false);
  useGSAP(() => placeMarker(root.current, marker.current, placed, true), {
    dependencies: [activeKey],
    scope: root,
  });
  useEffect(() => {
    const observer = new ResizeObserver(() =>
      placeMarker(root.current, marker.current, placed, false),
    );
    observer.observe(root.current!);
    return () => observer.disconnect();
  }, [root, marker]);
}

/**
 * Entrée d'une page : ses blocs arrivent en cascade courte (0,3 s de décalage au plus),
 * pour que l'utilisateur n'attende jamais l'animation. Contenu visible sans JavaScript.
 */
export function PageEnter({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      let items = [...root.current!.children];
      if (items.length === 1) items = [...items[0].children];
      const mm = gsap.matchMedia();
      mm.add(FULL, () => {
        gsap.from(items, {
          autoAlpha: 0,
          y: 14,
          filter: "blur(6px)",
          duration: 0.55,
          ease: EASE,
          stagger: { amount: Math.min(0.3, items.length * 0.06) },
          clearProps: "all",
        });
      });
      mm.add(REDUCED, () => {
        gsap.from(items, { autoAlpha: 0, duration: 0.2, clearProps: "all" });
      });
    },
    { scope: root },
  );

  return <div ref={root}>{children}</div>;
}

/**
 * Panneau de détail : il se déplie depuis le haut (masque et mise au point) et, s'il
 * s'ouvre hors de l'écran — toujours le cas sur mobile —, la page défile jusqu'à lui.
 */
export function DetailReveal({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const element = root.current!;
      const mm = gsap.matchMedia();
      mm.add(FULL, () => {
        gsap.fromTo(
          element,
          { clipPath: "inset(0% 0% 100% 0% round 20px)", filter: "blur(8px)", y: 10 },
          {
            clipPath: "inset(0% 0% 0% 0% round 20px)",
            filter: "blur(0px)",
            y: 0,
            duration: 0.5,
            ease: EASE,
            clearProps: "all",
          },
        );
      });
      mm.add(REDUCED, () => {
        gsap.from(element, { autoAlpha: 0, duration: 0.2, clearProps: "all" });
      });
    },
    { scope: root },
  );

  // Hors du contexte GSAP : à la fermeture, annuler ce tween ramènerait la page en haut.
  useEffect(() => {
    const element = root.current!;
    if (element.getBoundingClientRect().top <= window.innerHeight * 0.6) return;
    const scroll = gsap.to(window, {
      scrollTo: { y: element, offsetY: 80, autoKill: true }, // 80 px : sous l'en-tête collant
      duration: window.matchMedia(REDUCED).matches ? 0 : 0.6,
      ease: "power3.inOut",
    });
    return () => {
      scroll.kill();
    };
  }, []);

  return (
    <div ref={root} data-detail>
      {children}
    </div>
  );
}

/**
 * Balayage lumineux sur un bandeau de marque : une fois à l'arrivée, puis au survol.
 * Le parent doit être `relative overflow-hidden`. Absent si le mouvement est réduit.
 */
export function Sheen() {
  const band = useRef<HTMLSpanElement>(null);

  useGSAP(
    (_context, contextSafe) => {
      const element = band.current!;
      const host = element.parentElement!;
      let sweep = () => {};
      const mm = gsap.matchMedia();
      mm.add(FULL, () => {
        gsap.set(element, { autoAlpha: 1, xPercent: -120, skewX: -16 });
        const timeline = gsap.timeline({ delay: 0.35 }).to(element, {
          xPercent: 360,
          duration: 1.2,
          ease: "power2.inOut",
        });
        sweep = () => {
          if (!timeline.isActive()) timeline.delay(0).restart();
        };
      });
      const onEnter = contextSafe!(() => sweep());
      host.addEventListener("pointerenter", onEnter);
      return () => host.removeEventListener("pointerenter", onEnter);
    },
    { scope: band },
  );

  return (
    <span
      ref={band}
      aria-hidden
      className="pointer-events-none invisible absolute inset-y-0 left-0 w-1/3 bg-[linear-gradient(90deg,transparent,rgb(255_255_255/0.22)_45%,rgb(0_209_255/0.25)_55%,transparent)] opacity-0"
    />
  );
}
