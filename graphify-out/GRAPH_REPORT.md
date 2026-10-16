# Graph Report - web  (2026-10-14)

## Corpus Check
- Corpus is ~1,501 words - fits in a single context window. You may not need a graph.

## Summary
- 29 nodes · 28 edges · 8 communities (4 shown, 4 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.83)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- OTA Booking Integrations
- Working Capital Repayment
- Funding Engine Dashboard
- Fynza Growth Flywheel
- Booking Path Script
- Civitatis Integration
- FareHarbor Integration
- GetYourGuide Integration

## God Nodes (most connected - your core abstractions)
1. `Fynza` - 7 edges
2. `Connect Booking Systems` - 7 edges
3. `Working Capital from OTA Bookings` - 4 edges
4. `OTA Bookings` - 4 edges
5. `Cash Flow Gap` - 3 edges
6. `Fynza Dashboard` - 3 edges
7. `Funding Limit Engine` - 2 edges
8. `Funding Limit` - 2 edges
9. `Revenue-Based Repayment` - 2 edges
10. `Growth Flywheel` - 2 edges

## Surprising Connections (you probably didn't know these)
- `Fynza` --conceptually_related_to--> `Cash Flow Gap`  [EXTRACTED]
  index.html → index.html  _Bridges community 3 → community 1_
- `Fynza` --references--> `Fynza Dashboard`  [EXTRACTED]
  index.html → index.html  _Bridges community 3 → community 2_
- `Working Capital from OTA Bookings` --shares_data_with--> `OTA Bookings`  [EXTRACTED]
  index.html → index.html  _Bridges community 1 → community 2_
- `Connect Booking Systems` --shares_data_with--> `OTA Bookings`  [EXTRACTED]
  index.html → index.html  _Bridges community 2 → community 0_

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **How It Works Funding Flow** — index_connect_booking_systems, index_funding_engine, index_funding_limit, index_working_capital, index_revenue_based_repayment [EXTRACTED 1.00]
- **OTA and ResTech Integrations** — index_ventrata, index_palisis, index_bokun, index_fareharbor, index_civitatis, index_expedia, index_getyourguide, index_viator, index_klook [EXTRACTED 1.00]
- **Four-Week Cash-Negative Timeline** — index_cash_flow_gap, index_ota_processing, index_ota_bookings, index_tour_operators [EXTRACTED 1.00]

## Communities (8 total, 4 thin omitted)

### Community 0 - "OTA Booking Integrations"
Cohesion: 0.29
Nodes (7): Bókun, Connect Booking Systems, Expedia, Klook, Palisis, Ventrata, Viator

### Community 1 - "Working Capital Repayment"
Cohesion: 0.40
Nodes (5): Cash Flow Gap, Deductions Schedule, OTA Processing Delay, Revenue-Based Repayment, Working Capital from OTA Bookings

### Community 2 - "Funding Engine Dashboard"
Cohesion: 0.50
Nodes (5): Credit Eligibility, Funding Limit Engine, Funding Limit, Fynza Dashboard, OTA Bookings

### Community 3 - "Fynza Growth Flywheel"
Cohesion: 0.50
Nodes (5): Fynza, Fynza Ventures S.L., Growth Flywheel, Tour Operators, Vicious Growth Cycle

## Knowledge Gaps
- **13 isolated node(s):** `Fynza Ventures S.L.`, `OTA Processing Delay`, `Ventrata`, `Palisis`, `Bókun` (+8 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 16 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OTA Bookings` connect `Funding Engine Dashboard` to `OTA Booking Integrations`, `Working Capital Repayment`?**
  _High betweenness centrality (0.307) - this node is a cross-community bridge._
- **What connects `Fynza Ventures S.L.`, `OTA Processing Delay`, `Ventrata` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Why does `Connect Booking Systems` connect `OTA Booking Integrations` to `Funding Engine Dashboard`?**
  _High betweenness centrality (0.278) - this node is a cross-community bridge._
- **Why does `Fynza` connect `Fynza Growth Flywheel` to `Working Capital Repayment`, `Funding Engine Dashboard`?**
  _High betweenness centrality (0.214) - this node is a cross-community bridge._