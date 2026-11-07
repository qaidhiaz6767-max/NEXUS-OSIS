# Executive UI implementation notes

The visual references inspected were **NEXUS Liquid Glass Executive Dashboard.png** and **NEXUS Executive Intelligence Dashboard.png**. The written master directive controls behavior where a concept image differs: exactly five mapped Home portals, no percentage-based fake loading, quiet defaults, no market ticker on Home, and six OSIS functions.

The shell uses executive navy `#060D1B`, deep glass blue `#10243D`, muted steel `#91A7BB`, cyan `#1EC1CB`, and soft white `#F4F6FA`. Workspace accents are blue, champagne gold, royal violet, energy teal and neutral steel. Photographic cards remain intentionally unfilled until the user's photos are provided.

The optical object is one inline SVG with spherical shading, rim refraction, internal curved glass ribbons, highlight gradients and a diffuse ground reflection. CSS animates transforms/opacity; no WebGL renderer or new animation dependency is required. The startup shell repositions the same element and uses a FLIP animation into Home. Hidden-tab animation pauses and `prefers-reduced-motion` removes motion.

Navigation uses a quiet topbar, a profile/workspace drawer, a scoped trail, and dedicated workspace landings. The five Home cards form one row on wide screens, then three columns and two columns. The final narrow card spans the mobile grid. Workspace functions form a 3×2 desktop grid and reflow to two columns on small screens. Tool pages keep the established forms, tables, approvals and conversation layout.

`web/app.js` is the single active controller. Business writes call existing `/api/propose` and `/api/decide`; frontend labels do not change backend identity. New directory entries are visibly simple facts, documents are visibly text notes, and the ledger is visibly browser-only. No capability is represented by fabricated records, optimistic success metrics, autonomous agents or made-up market prices.
