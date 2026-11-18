"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { type ReactNode, type RefObject, Suspense, useRef } from "react";
import { usePathname } from "@/i18n/navigation";

gsap.registerPlugin(useGSAP, ScrollTrigger, SplitText);

const EASE = "expo.out";
const FULL = "(prefers-reduced-motion: no-preference)";

/*
 * Repères posés dans le balisage (attribut data-m) :
 * header, hero, hero-media, glow, badge, title, lead, cta, reveal, service, track, step.
 * `data-m-pre` : masqué par la feuille de style jusqu'à l'entrée (voir globals.css).
 */

/** Révèle les blocs au défilement, une seule fois, par petits groupes. */
function revealOnScroll(targets: Element[], from: gsap.TweenVars) {
  if (!targets.length) return;
  gsap.set(targets, { autoAlpha: 0, ...from });
  ScrollTrigger.batch(targets, {
    start: "top 88%",
    once: true,
    onEnter: (batch) =>
      gsap.to(batch, {
        autoAlpha: 1,
        x: 0,
        y: 0,
        scale: 1,
        rotate: 0,
        filter: "blur(0px)",
        duration: 0.8,
        ease: EASE,
        stagger: 0.09,
        clearProps: "filter,transform",
      }),
  });
}

/** Page d'accueil : titre mot à mot, halo qui suit le pointeur, parallaxe, révélations. */
export function HomeMotion({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    (_context, contextSafe) => {
      const q = gsap.utils.selector(root);
      const one = (name: string) => q(`[data-m="${name}"]`)[0] as HTMLElement | undefined;
      const mm = gsap.matchMedia();

      mm.add(FULL, () => {
        const split = SplitText.create(q('[data-m="title"]'), { type: "words", mask: "words" });
        gsap
          .timeline({ defaults: { ease: EASE } })
          .from(q('[data-m="header"] > *'), { autoAlpha: 0, y: -14, duration: 0.6, stagger: 0.05 })
          .from(q('[data-m="hero"]'), { clipPath: "inset(6% 4% 6% 4% round 28px)", duration: 1.1 }, 0)
          .from(q('[data-m="hero-media"]'), { autoAlpha: 0, scale: 1.12, duration: 1.6, ease: "power2.out" }, 0)
          .from(q('[data-m="badge"]'), { autoAlpha: 0, y: 12, filter: "blur(6px)", duration: 0.6 }, 0.15)
          .from(split.words, { yPercent: 115, duration: 1, stagger: 0.055 }, 0.25)
          .from(q('[data-m="lead"]'), { autoAlpha: 0, y: 16, filter: "blur(6px)", duration: 0.8 }, 0.55)
          .from(q('[data-m="cta"] > *'), { autoAlpha: 0, y: 14, scale: 0.96, duration: 0.7, stagger: 0.08 }, 0.7)
          .from(q('[data-m="glow"]'), { autoAlpha: 0, scale: 0.6, duration: 1.4, ease: "power2.out" }, 0.3);
        // Les états de départ sont posés : on peut lever le masque CSS sans saut visible.
        gsap.set(q("[data-m-pre]"), { autoAlpha: 1 });

        const hero = one("hero");
        if (hero) {
          gsap.to(q('[data-m="hero-media"]'), {
            yPercent: 10,
            ease: "none",
            scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: true },
          });
        }

        // Halo : dérive lente au repos, suit le pointeur sur les écrans à souris.
        const glow = one("glow");
        if (hero && glow) {
          const drift = gsap.to(glow, {
            xPercent: -18,
            yPercent: 14,
            duration: 7,
            ease: "sine.inOut",
            repeat: -1,
            yoyo: true,
          });
          if (window.matchMedia("(pointer: fine)").matches) {
            const toX = gsap.quickTo(glow, "x", { duration: 0.9, ease: "power3.out" });
            const toY = gsap.quickTo(glow, "y", { duration: 0.9, ease: "power3.out" });
            const onMove = contextSafe!((event: PointerEvent) => {
              drift.pause();
              const box = hero.getBoundingClientRect();
              toX(event.clientX - box.left - glow.offsetLeft - glow.offsetWidth / 2);
              toY(event.clientY - box.top - glow.offsetTop - glow.offsetHeight / 2);
            });
            const onLeave = contextSafe!(() => {
              toX(0);
              toY(0);
              drift.resume();
            });
            hero.addEventListener("pointermove", onMove);
            hero.addEventListener("pointerleave", onLeave);
            return () => {
              hero.removeEventListener("pointermove", onMove);
              hero.removeEventListener("pointerleave", onLeave);
            };
          }
        }
      });

      mm.add(FULL, () => {
        revealOnScroll(q('[data-m="reveal"]'), { y: 28, filter: "blur(8px)" });
        revealOnScroll(q('[data-m="service"]'), { y: 32, filter: "blur(8px)" });
        revealOnScroll(q('[data-m="service"] [data-m="icon"]'), { scale: 0.5, rotate: -20 });
        revealOnScroll(q('[data-m="step"]'), { x: -24, filter: "blur(8px)" });

        const track = one("track");
        if (track) {
          gsap.from(track, {
            scaleX: 0,
            ease: "none",
            scrollTrigger: { trigger: track.parentElement, start: "top 80%", end: "bottom 60%", scrub: 0.6 },
          });
        }
      });
    },
    { scope: root },
  );

  return <div ref={root}>{children}</div>;
}

/**
 * Écrans d'authentification : décor lumineux en dérive lente, entrée de la carte,
 * puis cascade des champs à chaque changement d'écran (connexion → mot de passe…).
 */
/** Changement d'écran : seuls les champs de la carte rejouent leur entrée. */
function ScreenCascade({ root }: { root: RefObject<HTMLDivElement | null> }) {
  const pathname = usePathname();
  const shown = useRef(pathname);
  useGSAP(
    () => {
      // Comparer l'adresse (et non un simple drapeau) : le mode strict rejoue les effets au montage.
      if (shown.current === pathname) return;
      shown.current = pathname;
      const card = root.current!.querySelector('[data-m="card"]');
      const form = card?.firstElementChild;
      const items = form?.children.length ? [...form.children] : card ? [...card.children] : [];
      gsap.matchMedia().add(FULL, () => {
        gsap.from(items, { autoAlpha: 0, y: 10, filter: "blur(6px)", duration: 0.5, ease: EASE, stagger: 0.05, clearProps: "all" });
      });
    },
    { dependencies: [pathname] },
  );
  return null;
}

export function AuthMotion({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);

  // Entrée et décor : une seule fois, la mise en page persiste entre les écrans.
  useGSAP(
    () => {
      const q = gsap.utils.selector(root);
      const mm = gsap.matchMedia();
      mm.add(FULL, () => {
        gsap
          .timeline({ defaults: { ease: EASE } })
          .from(q('[data-m="logo"]'), { autoAlpha: 0, y: -18, scale: 0.92, duration: 0.8 })
          .from(
            q('[data-m="card"]'),
            {
              autoAlpha: 0,
              y: 24,
              clipPath: "inset(0% 0% 100% 0% round 20px)",
              filter: "blur(10px)",
              duration: 0.9,
              clearProps: "filter,clipPath,transform",
            },
            0.1,
          )
          // Le contenu de la carte et des contrôles vit sous <Suspense> et s'hydrate plus tard :
          // y toucher ici provoquerait une erreur d'hydratation. On anime donc les blocs entiers.
          .from(q('[data-m="controls"]'), { autoAlpha: 0, y: 10, duration: 0.6 }, 0.5)
          .from(q('[data-m="orb"]'), { autoAlpha: 0, scale: 0.4, duration: 2, ease: "power2.out", stagger: 0.2 }, 0);
        gsap.set(q("[data-m-pre]"), { autoAlpha: 1 });

        q('[data-m="orb"]').forEach((orb, index) =>
          gsap.to(orb, {
            xPercent: index ? -22 : 26,
            yPercent: index ? 18 : -14,
            rotate: index ? -40 : 40,
            duration: 9 + index * 3,
            ease: "sine.inOut",
            repeat: -1,
            yoyo: true,
          }),
        );
      });
    },
    { scope: root },
  );

  return (
    <div ref={root} className="relative isolate overflow-hidden">
      {/* L'adresse des pages à jeton est inconnue au prérendu : sa lecture doit rester sous Suspense. */}
      <Suspense>
        <ScreenCascade root={root} />
      </Suspense>
      {/* Décor : grille fine estompée et deux halos de marque. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] bg-[size:44px_44px] opacity-60 [mask-image:radial-gradient(ellipse_at_center,black_10%,transparent_70%)]"
      />
      <div
        data-m="orb"
        aria-hidden
        className="pointer-events-none fixed -left-32 -top-32 -z-10 size-[28rem] rounded-full bg-primary/25 blur-3xl"
      />
      <div
        data-m="orb"
        aria-hidden
        className="pointer-events-none fixed -bottom-40 -right-32 -z-10 size-[32rem] rounded-full bg-secondary/20 blur-3xl"
      />
      {children}
    </div>
  );
}

/** Secousse brève à l'apparition d'un message d'erreur (absente si le mouvement est réduit). */
export function Shake({ children, trigger }: { children: ReactNode; trigger: unknown }) {
  const root = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      gsap.matchMedia().add(FULL, () => {
        gsap.fromTo(
          root.current,
          { x: 0, autoAlpha: 0 },
          { keyframes: { x: [0, -8, 7, -5, 3, 0] }, autoAlpha: 1, duration: 0.45, ease: "power2.out" },
        );
      });
    },
    { dependencies: [trigger], scope: root, revertOnUpdate: true },
  );
  return <div ref={root}>{children}</div>;
}
