---
version: alpha
name: Innovatiepijplijn
description: "Strak, warm en typografie-gedreven — geïnspireerd op Linear, Arc en Vercel"
colors:
  # Core — warme neutralen, geen koud slate
  primary: "oklch(22% 0.015 280)"
  secondary: "oklch(52% 0.02 280)"
  neutral: "oklch(97.5% 0.003 280)"
  surface: "oklch(100% 0 0)"

  # Accent — diep indigo, niet standaard Tailwind blue
  accent: "oklch(54% 0.18 275)"
  accent-hover: "oklch(48% 0.16 275)"
  accent-glow: "oklch(54% 0.18 275 / 0.12)"

  # Status — perceptueel gebalanceerd
  success: "oklch(56% 0.11 155)"
  success-subtle: "oklch(96% 0.02 155)"
  warning: "oklch(64% 0.12 72)"
  warning-subtle: "oklch(97% 0.025 72)"
  stopped: "oklch(56% 0.14 310)"
  stopped-subtle: "oklch(95% 0.02 310)"

  # Phase colors — subtiele, warme tinten
  phase-verkenning: "oklch(58% 0.14 290)"
  phase-verkenning-subtle: "oklch(94% 0.03 290)"
  phase-experiment: "oklch(64% 0.14 55)"
  phase-experiment-subtle: "oklch(95% 0.03 55)"
  phase-pilot: "oklch(58% 0.12 160)"
  phase-pilot-subtle: "oklch(94% 0.025 160)"
  phase-opschaling: "oklch(56% 0.13 260)"
  phase-opschaling-subtle: "oklch(94% 0.025 260)"

  # Hypothesis
  hypothesis-value: "oklch(58% 0.14 290)"
  hypothesis-growth: "oklch(58% 0.12 160)"
  hypothesis-compliance: "oklch(64% 0.12 72)"

  # UI chrome — minimale borders, subtiele diepte
  border: "oklch(91% 0.008 280)"
  border-hover: "oklch(84% 0.01 280)"
  shadow-sm: "oklch(0% 0 0 / 0.04)"
  shadow-md: "oklch(0% 0 0 / 0.07)"

  # Error
  error: "oklch(58% 0.18 25)"
  error-subtle: "oklch(96% 0.03 25)"
typography:
  display-lg:
    fontFamily: "'Plus Jakarta Sans', 'Inter', system-ui, sans-serif"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -0.035em
  display-md:
    fontFamily: "'Plus Jakarta Sans', 'Inter', system-ui, sans-serif"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.025em
  heading-sm:
    fontFamily: "'Plus Jakarta Sans', 'Inter', system-ui, sans-serif"
    fontSize: 17px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.015em
  body-lg:
    fontFamily: "'Inter', system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.65
  body-md:
    fontFamily: "'Inter', system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: "'Inter', system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.55
  label-md:
    fontFamily: "'Inter', system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1
    letterSpacing: 0.01em
  label-sm:
    fontFamily: "'Inter', system-ui, sans-serif"
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1
    letterSpacing: 0.02em
rounded:
  sm: 6px
  md: 10px
  lg: 14px
  xl: 20px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  base: 16px
  lg: 20px
  xl: 28px
  "2xl": 40px
  "3xl": 56px
components:
  button-primary:
    backgroundColor: "{{colors.accent}}"
    textColor: "{{colors.surface}}"
    typography: "{{typography.body-md}}"
    rounded: "{{rounded.md}}"
    padding: "{{spacing.sm}} {{spacing.lg}}"
  card-default:
    backgroundColor: "{{colors.surface}}"
    borderColor: "{{colors.border}}"
    rounded: "{{rounded.lg}}"
    padding: "{{spacing.xl}}"
---

## Overview

Strak, warm en typografie-gedreven. Geen standaard Tailwind-uitstraling — dit design is geïnspireerd op de huidige top van product UI: **Linear** voor zijn zuinigheid, **Arc Browser** voor zijn warme neutralen en organische feel, en **Vercel** voor zijn subtiele diepte via licht i.p.v. borders.

De kernprincipes:

1. **Typografie scheidt** — witruimte en lettergrootte doen het zware werk, niet borders
2. **Warme neutralen** — geen koud slate/grijs, tinten met subtiele warmte (hue ~280)
3. **oklch kleuren** — perceptueel uniforme verzadiging, geen "schreele" hex-tinten
4. **Minimale chrome** — borders zijn 1px en zeer subtiel; diepte via shadow i.p.v. outline
5. **Noise texture** — subtiele grain op achtergrond voor organische diepte
6. **Glow, niet border** — focus-states gebruiken subtiele glow i.p.v. harde randen

Toon: professioneel maar niet bureaucratisch. Alsof Linear en Notion een kind kregen dat in Leiden woont.

## Colors

Alle kleuren zijn in **oklch** — perceptueel uniforme ruimte waar verzadiging en helderheid consistent aanvoelen. Geen hex meer (behalve fallback).

De neutralen zitten rond hue 280 (subtiel warm-blauwig) i.p.v. neutraal grijs. Dit geeft een warmer, modernder gevoel zonder dat het opvalt.

De accentkleur is **diep indigo** (oklch 54% 0.18 275) — herkenbaar als "actie" maar niet de standaard Tailwind Blue 600. Iets rijper, iets karaktervolker.

Statuskleuren hebben een `-subtle` variant met lage chroma voor achtergrondgebruik (badges, banners). De standaardvariant is alleen voor tekst en iconen.

## Typography

**Plus Jakarta Sans** voor headings (gebolide, geometrisch maar met karakter), **Inter** voor body. Beide via Google Fonts. Tight letter-spacing op display (-0.035em) voor een strakke, moderne uitstraling.

De typografische spring tussen heading (28px, weight 700) en body (15px, weight 400) is opzettelijk groot — dit creëert hiërarchie zonder extra UI-elementen.

Labels zijn 11-12px met lichte letter-spacing — functioneel, niet decoratief. Geen uppercase-cramming.

## Layout

Sidebar + main content. Sidebar is **240px** — compact maar ruimtelijk. De hoofdinhoud ademt: 40px padding左右, max-width 1200px.

Tussen secties zit **40px** witruimte (niet 24 of 32). Witruimte is het primaire scheidingsmiddel — we gebruiken geen borders tussen secties tenzij absoluut nodig.

Cards hebben **14px radius** — afgerond maar niet "app-achtig". Geen boxShadow op rust-toestand; alleen bij hover verschijnt subtiele diepte.

## Elevation & Depth

Geen zware schaduwen. Diepte wordt bereikt via:

- **Noise texture** op de pagina-achtergrond (subtiele SVG grain)
- **Subtiele shadow** bij hover (`oklch(0% 0 0 / 0.06)`)
- **Border met lage contrast** (`oklch(91% 0.008 280)`) — zichtbaar maar niet dominant
- **Glow** op focus-states i.p.v. harde ringen

Cards op rust: alleen 1px border, geen shadow. Hover: lichte shadow + background-shift.

## Shapes

Moderate rounding: **10px** voor buttons/inputs, **14px** voor cards, **20px** voor modals. Geen `rounded-full` overal — badges gebruiken 10px i.p.v. pill-vorm. Consistentie > variatie.

## Components

### Buttons
Primary: donkere achtergrond (`var(--fg)`), lichte tekst, 6px radius. Compacte padding (6×12px). Geen zware accentkleur — de primary-knop is neutraal donker, niet blauw/groen/etc. Hover: subtiele helderheids-shift.

Secondary: volledig transparant, geen border. Alleen tekstkleur verschuift van muted → fg bij hover. Zo onopvallend mogelijk.

Ghost: alleen tekst, minimale padding. Voor tertiaire acties.

De filosofie: de knop is interface, niet inhoud. Interface verdwijnt. Geen kleurige badges of opvallende knoppen — de gebruiker weet waar hij moet klikken door context, niet door visueel geschreeuw.

### Cards
Witte achtergrond, 1px `border` kleur, 14px radius, 28px padding. Rust-toestand: geen shadow. Hover: `shadow-md` + lichte `translateY(-1px)`. De transition is 0.2s ease — niet te snel, niet traag.

### Badges
Geen pill-badges. 10px radius, 11px text, weight 500 (niet 600/700). Achtergrond in `-subtle` variant, tekst in standaard variant. Geen uppercase — title-case voelt minder agressief.

### Tables
Minimale horizontale lijnen. Header: geen achtergrondkleur, alleen font-weight en subtle border-bottom. Rij-hover: lichte background-shift, geen gehele rij highlighten.

### Forms
Inputs: 1px border, 10px radius. Focus: glow-ring (`box-shadow: 0 0 0 4px oklch(54% 0.18 275 / 0.1)`) i.p.v. harde kleurwechsel. Labels: 13px regular, niet bold.

## Do's and Don'ts

- **Do** gebruik witruimte als scheidingsmiddel — 40px tussen secties is normaal
- **Do** laat typografie de hiërarchie dragen — grote spring tussen heading en body
- **Do** gebruik oklch voor alle kleuren — perceptuele consistentie boven compatibiliteit
- **Don't** gebruik hex kleuren — ze voelen "Tailwind-default" aan
- **Don't** zet shadow op cards bij rust-toestand — alleen bij hover
- **Don't** gebruik uppercase voor labels — het voelt agressief en verouderd
- **Don't** meng meer dan 2 font families — Plus Jakarta Sans + Inter is genoeg
- **Don't** gebruik `border` als primair scheidingsmiddel — witruimte eerst, border pas daarna
