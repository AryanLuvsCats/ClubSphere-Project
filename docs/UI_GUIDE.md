# ClubSphere UI Guide

This guide describes the current website as implemented in `frontend/src/`, and points to the files to edit when you want to change it.

## Visual direction

The interface now follows a vintage broadsheet direction: newsprint cream (`#F5F2EA`), charcoal ink (`#1A1817`), fine paper rules, and signature burgundy (`#7A1219`). Fraunces supplies display headlines; Public Sans handles interface labels. Layouts use straight-edged cards, 1px column dividers, double-rule section breaks, burgundy stamps, and a dark editorial footer. Shared tokens and responsive styles live in `frontend/src/index.css`.

## Page structure and routes

| Route | Audience and purpose | Main UI location |
|---|---|---|
| `/` | Public introduction, campus stories, 3D globe, and links into the app | `frontend/src/pages/LandingPage.tsx`, `NewsGlobe.tsx`, `scrollfilm/` |
| `/login` | Sign in and account/session entry | `frontend/src/pages/LoginPage.tsx` |
| `/clubs` | Browse and discover clubs | `frontend/src/pages/ClubsPage.tsx` |
| `/events` | Browse campus events and registrations | `frontend/src/pages/EventsPage.tsx` |
| `/joinclub` | Request membership in a club | `frontend/src/pages/JoinClubPage.tsx` |
| `/applyclub` | Submit a proposal to start a club | `frontend/src/pages/ApplyClubPage.tsx` |
| `/manage-club` | Club manager tools and club operations | `frontend/src/pages/ManageClubPage.tsx` |
| `/admin` | Faculty, HOD, and administrator oversight | `frontend/src/pages/AdminDashboardPage.tsx` |
| `*` | Friendly fallback for unknown routes | `frontend/src/pages/NotFoundPage.tsx` |

`frontend/src/App.tsx` declares routes and authentication/role gates. `frontend/src/components/Layout.tsx` wraps authenticated screens with the responsive navigation drawer, account summary, notification popover, and sign-out action. On desktop the navigation stays in a left sidebar; on narrow screens it becomes a keyboard-accessible off-canvas menu.

## Landing page

The landing page uses a campus ticker, an edition/date strip, a centered ClubSphere masthead, and a double-ruled navigation bar. Its lead-story area places the large “Campus, in orbit.” headline, the revolving 3D globe, and Today’s Brief together. The brief loads published events from the same `/api/v1/events` endpoint used by the Events page and shows their venue, date/time, registration deadline, and available seats. The scroll-film sphere uses the newsprint cream backdrop; its motion sequence remains in `frontend/src/components/scrollfilm/`.

The club directory presents each club as a charter notice in a bordered column grid. Program names provide the burgundy classification banner; club descriptions use a drop cap, while charter numbers, membership totals, steward names, and join/manage actions remain visible. Search and academic filters stay at the top of the page.

The events board presents event data as telegram notices, with a monospaced date/time stamp, event number, registration state, live seat count, capacity indicator, and a sharp-cornered action stamp. The first result receives a featured notice treatment. Search and status filtering remain functional.

The sign-in screen is styled as a university press desk: centered logo and press-pass heading, double-line frame, square fields, and rectangular sign-in/register tabs. Authentication and account registration behavior are unchanged.

## Signed-in workspace

The authenticated workspace retains its responsive left navigation, selected-page highlighting, notification access, role and sign-out controls, but the surface treatment now matches the broadsheet system. Shared task pages use warm stock, ink rules, and square controls; every workspace route closes with the dark multi-column editorial footer in `frontend/src/components/GazetteFooter.tsx`.

Authentication is restored centrally by `AuthProvider`. `RequireAuth` sends signed-out users to login and preserves the target route; `RequireRoles` protects the admin page. Feature API calls are separated into services such as `clubService.ts`, `eventService.ts`, and `proposalService.ts`, which helps keep page rendering separate from request details.

## Customization map

| Change | Start here |
|---|---|
| Brand colors, fonts, global backgrounds, shared visual tokens | `frontend/src/index.css` |
| Sidebar links and role labels | `frontend/src/domain/constants.ts` |
| Navigation shell, logo placement, mobile menu, account area | `frontend/src/components/Layout.tsx` |
| Landing page headline, stories, editorial sections | `frontend/src/pages/LandingPage.tsx` |
| Shared dark editorial footer links and columns | `frontend/src/components/GazetteFooter.tsx` |
| Club charter grid and category styling | `frontend/src/pages/ClubsPage.tsx` plus Gazette rules in `frontend/src/index.css` |
| Event notice and timestamp treatment | `frontend/src/pages/EventsPage.tsx` plus Gazette rules in `frontend/src/index.css` |
| Press-pass sign-in frame and controls | `frontend/src/pages/LoginPage.tsx` plus Gazette rules in `frontend/src/index.css` |
| Globe appearance and interaction | `frontend/src/components/NewsGlobe.tsx` |
| Scroll film scenes and timing | `frontend/src/components/scrollfilm/scene.ts`, `ScrollFilm.tsx` |
| A specific application screen | Its component in `frontend/src/pages/` |
| Shared buttons, fields, and other UI primitives | `frontend/src/components/ui.tsx` |
| API request/response behavior | Matching file in `frontend/src/services/` and types in `frontend/src/domain/` |
| Screen availability and role checks | `frontend/src/App.tsx`, `frontend/src/domain/permissions.ts` |

## Logo

`frontend/public/clubsphere-logo.svg` is the primary vector mark: a minimal orbiting sphere/community motif in burgundy, parchment, and dusty rose. It appears in the public masthead, signed-in navigation, footer, sign-in press pass, and favicon. Keep the SVG accessible with appropriate alternative text when it communicates the brand; decorative repetitions can use empty alt text.

## Accessibility and responsive behavior

The mobile navigation has explicit open/close controls, an Escape-key close behavior, focus return, and a focus trap while open. Continue using semantic headings, visible focus states, descriptive button labels, and sufficient text contrast when adding UI. Check both narrow and wide layouts because the workspace navigation changes from a sidebar to a drawer.
