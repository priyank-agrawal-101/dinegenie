---
name: Bengaluru Culinary Noir
colors:
  surface: '#111413'
  surface-dim: '#111413'
  surface-bright: '#373a39'
  surface-container-lowest: '#0c0f0e'
  surface-container-low: '#191c1b'
  surface-container: '#1d201f'
  surface-container-high: '#282b29'
  surface-container-highest: '#323534'
  on-surface: '#e1e3e1'
  on-surface-variant: '#d3c5af'
  inverse-surface: '#e1e3e1'
  inverse-on-surface: '#2e3130'
  outline: '#9c8f7b'
  outline-variant: '#4f4535'
  surface-tint: '#f7bd42'
  primary: '#ffd179'
  on-primary: '#412d00'
  primary-container: '#ebb338'
  on-primary-container: '#634700'
  inverse-primary: '#7b5900'
  secondary: '#a5d1b2'
  on-secondary: '#0f3722'
  secondary-container: '#274f37'
  on-secondary-container: '#94bfa1'
  tertiary: '#ffd26c'
  on-tertiary: '#3f2e00'
  tertiary-container: '#e2b64e'
  on-tertiary-container: '#614700'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdea4'
  primary-fixed-dim: '#f7bd42'
  on-primary-fixed: '#261900'
  on-primary-fixed-variant: '#5d4200'
  secondary-fixed: '#c1edcd'
  secondary-fixed-dim: '#a5d1b2'
  on-secondary-fixed: '#002110'
  on-secondary-fixed-variant: '#274f37'
  tertiary-fixed: '#ffdf9c'
  tertiary-fixed-dim: '#eec057'
  on-tertiary-fixed: '#251a00'
  on-tertiary-fixed-variant: '#5b4300'
  background: '#111413'
  on-background: '#e1e3e1'
  surface-variant: '#323534'
typography:
  display-lg:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
  display-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 34px
    fontWeight: '600'
    lineHeight: 42px
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 36px
    fontWeight: '500'
    lineHeight: 44px
  headline-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 26px
    fontWeight: '500'
    lineHeight: 32px
  headline-md:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Playfair Display
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  title-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system expresses an intimate, nocturnal editorial perspective on Bengaluru’s culinary scene. The experience channels the atmosphere of late-night Indiranagar speakeasies, heritage filter coffee salons in Basavanagudi, and modern microbreweries in Lavelle Road. It combines the visual authority of a private dining concierge with the warmth of bespoke hospitality.

The visual direction merges **Editorial Dark Mode** with **Tactile Glass and Tonal Layering**:
- **Atmospheric Warm Dark**: Rejects stark, clinical blues and pure blacks in favor of deep, warm obsidian and botanical charcoal.
- **Gastronomic Accents**: Warm saffron golds and aromatic cardamoms evoke spice, warmth, and culinary prestige without feeling loud or utilitarian.
- **Editorial Sophistication**: High-contrast serif headlines paired with precise geometric sans body typography offer the feel of an exclusive print food journal backed by ambient machine intelligence.
- **Emotional Resonance**: Exclusive, deeply knowledgeable, comforting, and intuitive.

## Colors

The palette is engineered for intimate nighttime viewing with high legibility and rich contextual hierarchy:

- **Canvas & Base**:
  - Root Canvas: `#0D0F0E` (Near-black warm charcoal)
  - Surface Level 1: `#151817` (Deep obsidian charcoal for navigation bars and large section containers)
  - Surface Level 2: `#1C201E` (Raised card surface)
  - Surface Level 3: `#242A27` (Interactive surfaces, dropdowns, and overlays)

- **Accents**:
  - **Primary (Royal Saffron)**: `#EBB338` (Interactive states, primary actions, ratings, active indicators). Light hover variant: `#F5C75D`.
  - **Secondary (Aromatic Sage)**: `#7EA88B` (Dietary indicators, botanical pairings, verified badges, serene states). Soft variant: `#A2C4AD`.
  - **Gold Glow Tint**: `rgba(235, 179, 56, 0.15)` for ambient focal spotlights.

- **Typography & Structural Contrast**:
  - Primary Text: `#F5F5F3` (Crisp off-white, achieves 14:1 contrast ratio on `#0D0F0E`)
  - Secondary Text: `#9DA39F` (Muted warm stone for metadata, location timestamps, and descriptions)
  - Ghost Text: `#686E6A` (Disabled states, structural borders, placeholder text)

- **Borders & Dividers**:
  - Structural Hairline: `rgba(255, 255, 255, 0.08)`
  - Active / Curated Border: `rgba(235, 179, 56, 0.22)`
  - Botanic Accent Border: `rgba(126, 168, 139, 0.25)`

## Typography

The type system balances evocative editorial storytelling with crisp functional clarity:

- **Headlines (Playfair Display)**: Used for restaurant titles, curation headers, sensory dish labels, and high-level conversational AI outputs. Italics are sparingly applied to evoke culinary prestige (e.g., *Chef’s Reserve*, *Artisanal Roastery*).
- **Body & UI (Plus Jakarta Sans)**: Used for descriptions, ratings, addresses, menus, and system controls. The modern geometric apertures ensure high legibility against low-luminance dark backgrounds.
- **Micro-Copy & Badges**: Small labels (`label-sm`) feature a `+0.04em` tracking adjustment to maintain legibility when set in uppercase or tight pill badges.

## Layout & Spacing

The layout is built upon a balanced multi-device grid that prioritizes edge-to-edge culinary photography on mobile while establishing clean column structures on desktop:

- **Mobile (< 768px)**: 4 columns, `gutter` of `1rem`, outer screen `margin` of `1rem`. Restaurant feeds flow vertically with horizontal swipe carousels for neighborhoods (e.g., Koramangala, Indiranagar, Malleshwaram).
- **Tablet (768px - 1024px)**: 8 columns, `gutter` of `1.25rem`, outer `margin-tablet` of `2rem`. Supports split-view curation panels and map-integrated lists.
- **Desktop (> 1024px)**: 12 columns with a maximum canvas width of `1280px`, `gutter-desktop` of `1.5rem`, and outer `margin-desktop` of `3rem`.

Spacing adheres to a strict 4px/8px module:
- Micro-spacing (`space-xs`: 4px, `space-sm`: 8px) guides internal badge padding, icon-to-text offsets, and dense food attribute tags.
- Macro-spacing (`space-md`: 16px, `space-lg`: 24px, `space-xl`: 40px) controls content chunking, conversational AI bubble separations, and section breaks.

## Elevation & Depth

Visual hierarchy uses warm, low-opacity luminosity rather than harsh vertical drop shadows. Depth is achieved via three coordinated methods:

1. **Surface Tiers**:
   - **Level 0 (Canvas)**: `#0D0F0E` (Static ground)
   - **Level 1 (Sections/Floating Nav)**: `#151817` with subtle outer blur: `0 4px 20px rgba(0, 0, 0, 0.45)`
   - **Level 2 (Cards/Sheets)**: `#1C201E` framed by `1px solid rgba(255, 255, 255, 0.08)`
   - **Level 3 (Modals/Popovers)**: `#242A27` with `0 12px 32px rgba(0, 0, 0, 0.65)`

2. **Specular Borders (The "Ghost Light" Rule)**:
   Elevated cards feature a top-lit perimeter effect: borders utilize an angled subtle gradient, transitioning from `rgba(255, 255, 255, 0.12)` at the top edge to `rgba(255, 255, 255, 0.03)` at the bottom edge.

3. **Culinary Halo / Warm Radial Blooms**:
   AI recommendations and top-tier curated picks feature a restrained background glow:
   - `box-shadow: 0 0 40px -10px rgba(235, 179, 56, 0.12)`
   This emphasizes elite culinary selections without washing out the deep dark background.

## Shapes

The geometric framework is tailored for tactile mobile interactions and balanced framing:

- **Cards & Primary Sheets**: Defined by `rounded-2xl` (1.25rem / 20px) to deliver an inviting, approachable shape that softens high-contrast photography.
- **Input Fields & Form Controls**: Standardized at `rounded-xl` (0.75rem / 12px) for structured thumb placement and alignment with mobile keyboards.
- **Badges, Filter Chips & Action Pills**: Full rounded caps (`rounded-full` / 9999px) provide instant affordance for interactive micro-filters (e.g., *Craft Beer*, *Filter Coffee*, *Outdoor Seating*).
- **Nested Media**: Food photography thumbnails inside cards inherit a coordinated inner radius of `12px` (`rounded-xl`) to preserve uniform concentric margins.

## Components

### 1. Buttons & Interaction Triggers
- **Primary Action (Reserve, Ask Genie)**: Solid saffron gold background (`#EBB338`) with dark charcoal typography (`#0D0F0E`), font weight `600`, radius `rounded-xl`. Hover transitions smoothly to `#F5C75D` with subtle micro-scale (`1.01`).
- **Secondary Action (View Menu, Details)**: Ghost button on `#1C201E` surface with a `1px` border of `rgba(255, 255, 255, 0.12)` and off-white text (`#F5F5F3`).
- **Tertiary / Utility**: Transparent background with muted sage (`#7EA88B`) or saffron hover underline.

### 2. Badges & Filter Chips
- **Status Badges**: Pill-shaped (`rounded-full`), padded `4px 12px`.
  - *Must Try / Genie Pick*: Warm gold background tint `rgba(235, 179, 56, 0.15)` with `#EBB338` text and a subtle golden outline `rgba(235, 179, 56, 0.3)`.
  - *Dietary / Botanical (e.g., Pure Veg, Pet Friendly)*: Sage green background tint `rgba(126, 168, 139, 0.15)` with `#A2C4AD` text.
- **Filter Chips**: Dark charcoal surface (`#1C201E`), `1px solid rgba(255, 255, 255, 0.08)`. When selected, transitions to saffron border (`#EBB338`) and inner warm saffron glow.

### 3. Cards & Recommendation Blocks
- **Culinary Showcase Card**: Multi-layered card (`#1C201E`) featuring `rounded-2xl` corners, a 16:9 or 4:3 high-resolution hero photo with a bottom black gradient scrim (`rgba(13, 15, 14, 0.8)`), housing the restaurant name in `headline-sm` Playfair Display, price tier (`₹₹₹`), neighborhood tag, and aggregated Genie Match score badge in the top right.

### 4. Input Fields & Chat Prompts
- **AI Prompt Console**: Floating conversational capsule with `rounded-2xl` border, `#151817` surface, and an ambient saffron outline on focus (`rgba(235, 179, 56, 0.4)`). Text input set in `Plus Jakarta Sans`, placeholder text `#686E6A`. Action send trigger integrated directly into the right edge.
- **Standard Text Fields**: Height of `48px`, `rounded-xl` corners, background `#151817`, border `1px solid rgba(255, 255, 255, 0.08)`.

### 5. Checkboxes & Radio Controls
- Circular and rounded square indicators featuring an active saffron core (`#EBB338`) against a deep charcoal inset. Inactive state marked by an understated border (`rgba(255, 255, 255, 0.2)`).

### 6. Specialized App Components
- **Genie Match Dial**: Compact radial or badge gauge displaying matching percentage (e.g., *98% Match for Craft Beer & Open Air*), rendered in saffron with a warm blur backdrop.
- **Vibe Meter**: Horizontal segmented bar expressing ambiance attributes (e.g., *Romantic*, *Buzzing*, *Work-friendly*) using sage and gold fill states.