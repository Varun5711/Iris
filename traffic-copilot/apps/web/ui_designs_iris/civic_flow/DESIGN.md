# Design System Strategy: The Civil Architect

## 1. Overview & Creative North Star
The visual identity of this design system is anchored by a Creative North Star we call **"The Civil Architect."** 

Unlike standard government software that feels utilitarian and rigid, "The Civil Architect" approach treats data as a high-end editorial piece. We move beyond the "dashboard template" by using intentional asymmetry, generous white space, and a sophisticated layering of surfaces. The goal is to convey authoritative intelligence through soft minimalism. We don't use heavy borders to contain information; we use structural confidence and tonal depth to guide the eye. It is professional, stable, and undeniably premium.

---

## 2. Colors
Our palette is a study in legibility and calm. We avoid high-contrast black/white pairings in favor of soft, atmospheric neutrals.

### Palette Highlights
- **Primary Intelligence:** `#2A6C0D` (Primary) and `#6AB04C` (Primary Container). This muted green represents growth and "Go" status, but in a way that feels organic rather than neon.
- **Surface Foundations:** `#F8F9FB` (Surface) serves as our canvas. It is a soft off-white that reduces eye strain during long-shift monitoring.
- **Typography:** `#2D3436` (On Surface) ensures high readability without the harshness of pure black.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to section off the UI. Boundaries must be defined solely through background color shifts.
- To separate a sidebar from a main view, transition from `surface` to `surface_container_low`. 
- To define a card, place a `surface_container_lowest` (Pure White) element on a `surface_container_low` background. 

### Signature Textures
Avoid flat, "dead" buttons. For primary actions, use a subtle linear gradient transitioning from `primary` (#2A6C0D) to `primary_container` (#6AB04C) at a 145-degree angle. This adds a "soul" to the component that suggests a physical, tactile button.

---

## 3. Typography
We utilize **Public Sans** across the entire system. It is a typeface designed for government use—neutral, yet modern and friendly.

- **Display & Headlines:** Use `display-md` (2.75rem) for high-level metrics. The large scale creates an editorial "hero" moment for the most critical data.
- **Information Hierarchy:** Use `title-sm` (1rem) for card headers to maintain a compact but authoritative feel.
- **Data Tables:** All tabular data should utilize `body-sm` (0.75rem) with increased letter-spacing (+0.02em) to ensure clarity in dense information environments.

---

## 4. Elevation & Depth
In this system, depth is a functional tool, not a decoration. We achieve hierarchy through **Tonal Layering** rather than traditional drop shadows.

### The Layering Principle
Stack containers to define importance:
1.  **Base Layer:** `surface` (#F8F9FB).
2.  **Section Layer:** `surface_container_low` (#F2F4F6) for grouping large content blocks (e.g., the map controls).
3.  **Action Layer:** `surface_container_lowest` (#FFFFFF) for individual data cards.

### Ambient Shadows
When a card must "float" (e.g., a map overlay), use an extra-diffused shadow:
- **Blur:** 24px–32px
- **Opacity:** 4%–6%
- **Color:** Use a tinted version of `on_surface` (a deep grey-blue) to mimic natural light. Never use pure black for shadows.

### The "Ghost Border" Fallback
If a visual boundary is absolutely required for accessibility (e.g., a search input), use a "Ghost Border": the `outline_variant` token at **15% opacity**. It should be felt, not seen.

---

## 5. Components

### Cards & Data Blocks
- **Corner Radius:** Use the `md` scale (0.75rem / 12px) for all main containers.
- **Rule:** Forbid the use of divider lines. Separate content using the Spacing Scale (typically `3` or `4` units) to create "breathing room" that naturally groups information.

### Buttons
- **Primary:** Rounded-full (pill shape). Use the signature gradient (Primary to Primary Container).
- **Secondary:** Surface-colored with a `primary` text label. No border.
- **States:** On hover, increase the surface brightness by 4%. On press, use the `surface_tint` at 8% opacity.

### Charts & Data Visualization
- **Thin-Line Philosophy:** Line charts must use a 1.5px stroke width. 
- **Data Fills:** Use a subtle 10% opacity fill under line charts using the `primary_fixed` color to provide a "volume" feel without obscuring the grid.

### AI Copilot (Special Component)
As a high-end intelligence system, the Copilot should feel like a distinct entity. Use a `surface_container_lowest` card with a subtle `secondary_container` (#C9E9B5) glow at the bottom edge to signify "active intelligence."

---

## 6. Do's and Don'ts

### Do:
- **Use Intentional Asymmetry:** Align primary metrics to the left and secondary "meta-data" to the right to create a natural reading flow.
- **Embrace White Space:** If a dashboard feels "empty," increase the spacing between cards rather than making the cards larger.
- **Layer Tonally:** Use background color shifts (`surface` vs `surface_container`) as your primary way to organize the page.

### Don't:
- **Don't use 100% opaque borders.** This creates "visual noise" and makes the system feel dated and boxed-in.
- **Don't use Glassmorphism.** While popular, this system prioritizes the "Civil Architect" look—solid, dependable, and high-readability. Avoid blurs and transparency behind text.
- **Don't use high-contrast shadows.** Heavy shadows make the UI feel heavy. We want the interface to feel light and fast.
- **Don't use dividers.** If you need to separate two pieces of text, use a 0.7rem (`2`) spacing gap instead of a line.