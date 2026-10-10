# LEO-DTN project specification

## Problem

Low Earth Orbit satellite links are intermittent: two nodes can exchange data only during contact windows. A message may therefore need to wait at a satellite or ground station until a later forwarding opportunity. LEO-DTN will simulate this store-carry-forward behavior and make the resulting network state and bundle journeys inspectable.

The research question is: **How do contact availability, buffer capacity, and routing strategy affect bundle delivery performance in a simulated LEO satellite network?**

## Objectives

- Model satellites and ground stations connected by time-bounded contacts.
- Create, queue, forward, deliver, and expire bundles under finite buffers.
- Compare understandable routing strategies and measure delivery outcomes.
- Support repeatable scenarios, seeded randomized configurations, and JSON/CSV result export.
- Present actual engine state in an interactive dashboard, including topology, active links, bundle journeys, simulated time, and metrics.
- Let users configure the constellation before a run by selecting a preset or custom satellite count and adding satellites by explicit placement or seeded random placement. The scene and controls must work as the configured node count changes, not assume the mockup's sample count.
- Show satellites and ground stations in a 3D scene. Keep Earth fixed in the simulation's scene frame with automatic spin disabled; let users rotate the view. Provide packet-follow framing that keeps a selected bundle visible by adjusting the camera/view, based on engine-reported forwarding/transmission state.

## Core concepts

- **Contact:** a scheduled opportunity to transmit from one endpoint to another during a defined time interval, with a data rate and optional propagation delay.
- **Bundle:** an application-level payload with source, destination, lifetime, size, current holder, status, and forwarding history.
- **Store-carry-forward:** a node retains an admitted bundle while waiting for a feasible contact and route.
- **Discrete-event simulation:** simulated time advances between state-changing events; it is independent of elapsed computer time.

## Scope

The simulation uses a small node model, finite byte-capacity buffers, complete-bundle transmissions, deterministic event ordering, and a baseline plus contact-aware routing. Satellite motion uses a documented two-body circular-orbit approximation in an Earth-fixed scene frame; contacts can be generated from line-of-sight and minimum ground-station elevation over a finite run horizon. These orbital assumptions are essential to showing why LEO links appear and disappear, but they are not high-fidelity ephemerides or operational predictions.

## Technology and constraints

- Frontend: TypeScript, Next.js, React.
- API: Python, FastAPI, Pydantic.
- Engine: Python discrete-event engine, directly testable without a server.
- Testing: pytest plus suitable frontend type, lint, and test tools.
- Initial persistence: in-memory state; JSON and CSV exports. No database by default.
- Local development; no cloud, microservices, broker, job system, or Kubernetes by default.
- Engine owns all simulation state and behavior. The frontend renders read-only state and the API is an adapter, not a second simulation implementation.

## Non-goals

- Real satellite operations, flight software, or validated operational performance.
- Claiming complete Bundle Protocol (BP) compliance or custody-transfer behavior.
- High-fidelity orbital propagation, perturbations, attitude, antenna patterns, atmospheric effects, and operational satellite performance.
- Partial bundle fragmentation/resumption, authentication, persistent multi-user state, or distributed simulation unless separately justified.
- Decorative visualization that implies contacts or forwarding absent from engine state.

## High-level requirements

1. Repeated runs with identical inputs and seed produce identical event histories and metrics.
2. A bundle cannot be forwarded when no valid contact exists; it can remain stored until one does.
3. Transmission, reception, buffer admission, expiry, and delivery have explicit distinct semantics.
4. Metrics define denominators and cutoff treatment so comparisons are fair.
5. UI distinguishes observed/current state, past events, and engine-computed predictions.
6. Assumptions and limitations are documented separately from implemented behavior.
