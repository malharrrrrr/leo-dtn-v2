import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  Activity, ArrowDown, ArrowRight, BookOpen, CircleHelp, Clock3, Compass,
  Database, FlaskConical, Gauge, Globe2, Layers3, Orbit, Route, Satellite,
  ShieldAlert, Waypoints,
} from "lucide-react";

export const metadata: Metadata = {
  title: "About the model | LEO-DTN",
  description: "A plain-language and mathematical guide to the LEO-DTN store-carry-forward simulator.",
};

const contents = [
  ["overview", "What this project is"],
  ["workflow", "How a run works"],
  ["orbit", "Satellite motion"],
  ["contacts", "Contacts and visibility"],
  ["forwarding", "Bundles and forwarding"],
  ["routing", "Routing strategies"],
  ["time", "Time and reproducibility"],
  ["metrics", "Metrics and formulas"],
  ["example", "Worked example"],
  ["limits", "Assumptions and limits"],
  ["glossary", "Glossary"],
];

function Formula({ children, note }: { children: string; note?: string }) {
  return <div className="about-formula"><div className="about-math" role="math">{children}</div>{note && <small>{note}</small>}</div>;
}

function Term({ name, children }: { name: string; children: ReactNode }) {
  return <div className="about-term"><dt>{name}</dt><dd>{children}</dd></div>;
}

function Notation({ children }: { children: ReactNode }) {
  return <div className="about-notation"><b>Symbols and units</b><dl className="about-glossary">{children}</dl></div>;
}

function SymbolTerm({ symbol, unit, children }: { symbol: string; unit?: string; children: ReactNode }) {
  return <div className="about-term"><dt><span className="notation-symbol">{symbol}</span>{unit && <> <span className="notation-unit">({unit})</span></>}</dt><dd>{children}</dd></div>;
}

export default function AboutPage() {
  return (
    <main className="about-shell">
      <header className="about-topbar">
        <Link className="about-brand" href="/" aria-label="LEO-DTN dashboard">
          <span className="brand-mark"><Globe2 size={22} /></span>
          <span><b>LEO-DTN</b><small>Satellite Network Simulator</small></span>
        </Link>
        <nav className="about-topnav" aria-label="Main navigation">
          <Link className="nav-item" href="/"><ArrowRight size={15} /> Dashboard</Link>
          <span className="nav-item selected" aria-current="page"><BookOpen size={15} /> About the model</span>
        </nav>
      </header>

      <section className="about-hero">
        <div className="about-hero-copy">
          <div className="eyebrow"><BookOpen size={13} /> PROJECT GUIDE</div>
          <h1>Understand the network behind the dashboard.</h1>
          <p>Start with the idea, follow one bundle through the model, then explore the equations, metrics, assumptions, and vocabulary used by LEO-DTN.</p>
          <div className="about-hero-actions">
            <Link className="primary" href="/"><Activity size={15} /> Open the simulator</Link>
            <a className="secondary" href="#workflow">Start with how it works <ArrowDown size={14} /></a>
          </div>
        </div>
        <div className="about-hero-orbit" aria-hidden="true">
          <div className="about-orbit-ring ring-one" /><div className="about-orbit-ring ring-two" />
          <span className="about-earth"><Globe2 size={54} /></span>
          <span className="orbit-point point-a"><Satellite size={15} /></span><span className="orbit-point point-b"><Satellite size={15} /></span>
          <span className="orbit-ground ground-a" /><span className="orbit-ground ground-b" />
        </div>
      </section>

      <div className="about-layout">
        <aside className="about-toc panel">
          <span className="eyebrow">ON THIS PAGE</span>
          <nav aria-label="About page contents">
            {contents.map(([id, title], index) => <a key={id} href={`#${id}`}><span>{String(index + 1).padStart(2, "0")}</span>{title}</a>)}
          </nav>
          <div className="about-toc-note"><CircleHelp size={15} /><p>New to this topic? Read top to bottom. The glossary is here whenever a term is unfamiliar.</p></div>
        </aside>

        <div className="about-article">
          <section className="about-section" id="overview">
            <div className="about-section-heading"><span className="about-section-icon blue"><Compass size={18} /></span><div><span className="eyebrow">01 · THE IDEA</span><h2>What this project is</h2></div></div>
            <p className="about-lead">LEO-DTN is an academic simulator for sending bundles through a network whose satellite links appear and disappear as satellites move.</p>
            <p>Unlike a continuously connected network, a sender may not have a usable link right now. It keeps a bundle, waits for a contact opportunity, and forwards the bundle when the network can carry it. Satellites can act as relays between distant ground stations.</p>
            <div className="about-callout"><ShieldAlert size={18} /><div><b>A model for learning and experiments</b><p>This is a simulator, not an operational communications system. Its results describe the configured model and assumptions; they are not predictions for a real satellite constellation.</p></div></div>
            <div className="about-fact-grid">
              <article><span><Layers3 size={16} /></span><b>Store, then forward</b><p>Bundles wait at nodes until a valid contact is available.</p></article>
              <article><span><Clock3 size={16} /></span><b>Simulated time</b><p>The engine advances between events, not according to your computer clock.</p></article>
              <article><span><Database size={16} /></span><b>Engine-owned state</b><p>The Python engine makes decisions; the dashboard displays its snapshots.</p></article>
            </div>
          </section>

          <section className="about-section" id="workflow">
            <div className="about-section-heading"><span className="about-section-icon cyan"><Waypoints size={18} /></span><div><span className="eyebrow">02 · THE PIPELINE</span><h2>How one run works</h2></div></div>
            <p>Each run follows the same path from configuration to measured outcomes.</p>
            <ol className="about-steps">
              <li><span>1</span><div><b>Configure a scenario</b><p>Choose nodes, satellite orbits, bundle templates, buffers, link settings, routing policy, random seed, and observation window.</p></div></li>
              <li><span>2</span><div><b>Build the network over time</b><p>The engine propagates satellite positions and creates directed contact windows from geometric visibility, or uses an explicitly supplied contact plan.</p></div></li>
              <li><span>3</span><div><b>Process the next event</b><p>A stable event queue chooses what happens next: a contact opens, a bundle is created, a transmission completes, a bundle arrives, or its lifetime expires.</p></div></li>
              <li><span>4</span><div><b>Choose and validate a hop</b><p>A routing policy proposes a next contact. The engine checks timing, contact capacity, bundle lifetime, and receiver buffer space before accepting the transfer.</p></div></li>
              <li><span>5</span><div><b>Render state and calculate metrics</b><p>The API returns read-only snapshots and results. The dashboard shows current state, event history, transfers, and summary measures.</p></div></li>
            </ol>
            <div className="about-boundary"><b>One source of truth</b><span>Routing, contact scheduling, bundle forwarding, and simulated state live in the engine. The browser does not independently guess where packets should go.</span></div>
          </section>

          <section className="about-section" id="orbit">
            <div className="about-section-heading"><span className="about-section-icon violet"><Orbit size={18} /></span><div><span className="eyebrow">03 · ORBIT MODEL</span><h2>How satellite motion is represented</h2></div></div>
            <p>Each moving satellite follows a circular two-body Kepler orbit around a spherical Earth. The input gives altitude, inclination, right ascension of the ascending node, and phase at the simulation epoch.</p>
            <div className="about-equation-grid">
              <Formula>r = Rₑ + h</Formula>
              <Formula>n = √(μ / r³)</Formula>
              <Formula>θ(t) = θ₀ + n · t</Formula>
              <Formula>T = 2π / n       v = √(μ / r)</Formula>
            </div>
            <Notation>
              <SymbolTerm symbol="Rₑ" unit="km">Mean spherical-Earth radius: 6,371 km.</SymbolTerm>
              <SymbolTerm symbol="h" unit="km">Satellite altitude above the Earth's surface.</SymbolTerm>
              <SymbolTerm symbol="r" unit="km">Orbital radius, measured from Earth's centre; r = Rₑ + h.</SymbolTerm>
              <SymbolTerm symbol="μ" unit="km³/s²">Earth's gravitational parameter, 398,600.4418 km³/s².</SymbolTerm>
              <SymbolTerm symbol="n" unit="rad/s">Mean angular speed of the circular orbit, √(μ/r³).</SymbolTerm>
              <SymbolTerm symbol="θ(t), θ₀" unit="rad">Current orbital phase at elapsed time t, and the phase at the simulation epoch; configured phase values in degrees are converted to radians.</SymbolTerm>
              <SymbolTerm symbol="t" unit="s">Elapsed simulated time from the orbit epoch. The engine stores time as integer microseconds and converts for propagation.</SymbolTerm>
              <SymbolTerm symbol="T; v" unit="s; km/s">Orbital period and circular orbital speed, respectively.</SymbolTerm>
              <SymbolTerm symbol="Ω, i" unit="rad">RAAN and inclination; they orient the orbital plane. Configuration values are supplied in degrees and converted to radians for these equations.</SymbolTerm>
              <SymbolTerm symbol="sin, cos">Sine and cosine functions. Trigonometric arguments in the equations are radians.</SymbolTerm>
              <SymbolTerm symbol="xᵢ, yᵢ, zᵢ" unit="km">Position coordinates in the Earth-centred inertial (ECI) frame.</SymbolTerm>
              <SymbolTerm symbol="xₑ, yₑ, zₑ" unit="km">Position coordinates in the Earth-centred Earth-fixed (ECEF) frame.</SymbolTerm>
              <SymbolTerm symbol="ωₑ" unit="rad/s">Earth's rotation rate, 7.2921150 × 10⁻⁵ rad/s.</SymbolTerm>
              <SymbolTerm symbol="φ, λ" unit="rad">Ground-station latitude and longitude. Configuration values are supplied in degrees.</SymbolTerm>
            </Notation>
            <details className="about-details"><summary>Show the position equations</summary>
              <p>In the Earth-centred inertial (ECI) frame, with RAAN Ω, inclination i, and orbital phase θ, all trigonometric angles are in radians:</p>
              <Formula>xᵢ = r(cos Ω cos θ − sin Ω sin θ cos i)</Formula>
              <Formula>yᵢ = r(sin Ω cos θ + cos Ω sin θ cos i)</Formula>
              <Formula>zᵢ = r sin θ sin i</Formula>
              <p>The scene uses an Earth-centred Earth-fixed (ECEF) frame. With Earth rotation rate ωₑ and elapsed time t, both measured in radians per second and seconds respectively, the implementation rotates the inertial position as follows:</p>
              <Formula>xₑ = cos(ωₑt)xᵢ + sin(ωₑt)yᵢ</Formula><Formula>yₑ = −sin(ωₑt)xᵢ + cos(ωₑt)yᵢ       zₑ = zᵢ</Formula>
              <p>Velocity is propagated and transformed into the same rotating Earth-fixed frame. Earth stays still in the dashboard scene; satellite coordinates move as simulation time advances.</p>
            </details>
            <div className="about-constant-row"><span><b>Earth radius</b><code>6,371 km</code></span><span><b>Gravitational parameter μ</b><code>398,600.4418 km³/s²</code></span><span><b>Earth rotation ωₑ</b><code>7.2921150 × 10⁻⁵ rad/s</code></span></div>
            <p className="about-small-note">Ground stations are fixed points on the spherical Earth. Given latitude φ and longitude λ (in radians in this equation), their Earth-fixed coordinates are x = Rₑ cos φ cos λ, y = Rₑ cos φ sin λ, z = Rₑ sin φ.</p>
          </section>

          <section className="about-section" id="contacts">
            <div className="about-section-heading"><span className="about-section-icon blue"><Satellite size={18} /></span><div><span className="eyebrow">04 · LINK OPPORTUNITIES</span><h2>When can two nodes communicate?</h2></div></div>
            <p>A <b>contact</b> is a time-limited, directed chance to send data from one node to another. In orbital mode, a contact is planned while the geometry permits a usable line of sight.</p>
            <div className="about-equation-grid">
              <Formula>min₀≤u≤₁ ‖a + u(b − a)‖ ≥ Rₑ</Formula>
              <Formula>e = (180/π) asin(((rₛ − r_g) · r_g) / (‖rₛ − r_g‖ ‖r_g‖)) ≥ eₘᵢₙ</Formula>
            </div>
            <Notation>
              <SymbolTerm symbol="a, b" unit="km">Three-dimensional ECEF position vectors of the two endpoints of a candidate link; each coordinate is measured in kilometers.</SymbolTerm>
              <SymbolTerm symbol="u" unit="unitless">Fraction of the way along the straight line from a to b; it ranges from 0 to 1.</SymbolTerm>
              <SymbolTerm symbol="‖x‖" unit="km">Length of vector x. The minimum must be at least Earth radius Rₑ for the link to clear Earth.</SymbolTerm>
              <SymbolTerm symbol="rₛ, r_g" unit="km">Three-dimensional ECEF position vectors of the satellite and ground station; each coordinate is measured in kilometers.</SymbolTerm>
              <SymbolTerm symbol="e, eₘᵢₙ" unit="degrees">Elevation angle of the satellite above the ground station's local horizon, and the configured minimum (10° by default). asin is inverse sine and returns radians; multiplying by 180/π converts it to degrees.</SymbolTerm>
              <SymbolTerm symbol="·">Vector dot product. The ground station's position vector points along its local vertical.</SymbolTerm>
              <SymbolTerm symbol="asin">Inverse sine; it returns the angle whose sine equals the input value, in radians.</SymbolTerm>
            </Notation>
            <p>Satellite-to-satellite links must clear the spherical Earth. Ground links must also meet the minimum elevation angle.</p>
            <ul className="about-bullet-list">
              <li>Visibility is sampled at a configured interval (10 seconds by default); detected start and end boundaries are refined to microsecond resolution.</li>
              <li>A window shorter than the sampling interval may be missed.</li>
              <li>Each direction is a separate contact with its own transmission resource. Two opposite-direction contacts do not share one simulated radio.</li>
              <li>Contacts use the half-open interval <code>[start, end)</code>: no new transmission starts at the end time.</li>
            </ul>
            <div className="about-horizon"><Clock3 size={17} /><p><b>Plan horizon vs. run cutoff</b><br />In orbital mode, the requested horizon is a minimum contact-plan lookahead. The engine plans through configured bundle expiry and extends its lookahead during playback. A comparison's observation cutoff is different: it is the time at which metrics are measured.</p></div>
          </section>

          <section className="about-section" id="forwarding">
            <div className="about-section-heading"><span className="about-section-icon cyan"><ArrowRight size={18} /></span><div><span className="eyebrow">05 · STORE AND CARRY</span><h2>What happens to a bundle?</h2></div></div>
            <p>A bundle is a complete application-level payload with a source, destination, size, creation time, lifetime, holder, status, and forwarding history. It is kept at its current node until another node accepts it.</p>
            <div className="about-equation-grid">
              <Formula>d = ⌈B × 8 × 1,000,000 / R⌉</Formula>
              <Formula>t_arrival = t_start + d + p</Formula>
              <Formula>t_arrival &lt; t_end</Formula>
              <Formula>t_expiry = t_create + TTL</Formula>
            </div>
            <Notation>
              <SymbolTerm symbol="B" unit="bytes">Complete bundle payload size.</SymbolTerm>
              <SymbolTerm symbol="R" unit="bits/s">Data rate of the directed contact.</SymbolTerm>
              <SymbolTerm symbol="d" unit="μs">Serialization duration, rounded up to an integer microsecond. One byte is eight bits.</SymbolTerm>
              <SymbolTerm symbol="t_start, t_arrival, t_end" unit="μs">Transmission start, last-bit arrival at the receiver, and contact end times.</SymbolTerm>
              <SymbolTerm symbol="p" unit="μs">Configured propagation delay after serialization; zero by default.</SymbolTerm>
              <SymbolTerm symbol="t_create, t_expiry, TTL" unit="μs">Bundle creation time, absolute expiry time, and its time-to-live. Expiry equals creation time plus TTL.</SymbolTerm>
              <SymbolTerm symbol="⌈x⌉">Ceiling function: round x upward to the next integer.</SymbolTerm>
            </Notation>
            <p>The sender holds the entire bundle through serialization and propagation. Only after the receiver has room and accepts the bundle does the sender release it. If a contact ends too early, an interruption happens, or the receiver has no buffer space, the transfer fails and the sender keeps the complete bundle for a later attempt. Partial fragments are not sent.</p>
            <div className="about-status-row"><span className="status-pill queued">Queued <small>stored and waiting</small></span><span className="status-pill transmitting">Transmitting <small>being serialized</small></span><span className="status-pill transit">In transit <small>bits propagating</small></span><span className="status-pill delivered">Delivered <small>accepted at destination</small></span><span className="status-pill expired">Expired <small>TTL elapsed</small></span></div>
            <p className="about-small-note">Buffers have finite byte capacity. Occupancy includes bundles held in queues or during outgoing serialization. A receiver that cannot fit the full bundle rejects the arrival; the sender retains it.</p>
          </section>

          <section className="about-section" id="routing">
            <div className="about-section-heading"><span className="about-section-icon amber"><Route size={18} /></span><div><span className="eyebrow">06 · ROUTING</span><h2>How the two strategies differ</h2></div></div>
            <div className="about-policy-grid">
              <article><span className="policy-label">TIME-AWARE</span><h3>Contact-aware earliest arrival</h3><p>Searches future contacts in time order, allows a bundle to wait at a node, and chooses the first hop on the route with the earliest predicted destination arrival.</p><Formula>tₖ₊₁ = max(tₖ, aₖ) + dₖ + pₖ</Formula><small>Must also satisfy tₖ₊₁ &lt; bₖ for each contact window [aₖ, bₖ).</small></article>
              <article><span className="policy-label baseline">BASELINE</span><h3>Static minimum hop</h3><p>Finds a path with the fewest links in the union of known contacts. The chosen next hop can be poorly timed or make the bundle wait, so this is a deliberately weak comparator for intermittent links.</p><Formula>minimize number of hops</Formula><small>Contact timing still gates actual transmission.</small></article>
            </div>
            <Notation>
              <SymbolTerm symbol="k" unit="hop index">Identifies one hop in the candidate route.</SymbolTerm>
              <SymbolTerm symbol="tₖ" unit="μs">Time the bundle is available at the current node after hop k.</SymbolTerm>
              <SymbolTerm symbol="aₖ, bₖ" unit="μs">Opening and closing times of the contact used for hop k.</SymbolTerm>
              <SymbolTerm symbol="dₖ, pₖ" unit="μs">Serialization duration and propagation delay for hop k.</SymbolTerm>
              <SymbolTerm symbol="max(tₖ, aₖ)">The hop cannot start until both the bundle has arrived and the contact has opened; the difference is waiting time.</SymbolTerm>
            </Notation>
            <p>This is a planner over the generated contact schedule—not Contact Graph Routing (CGR), Epidemic Routing, or another standards-based protocol.</p>
            <div className="about-callout muted"><CircleHelp size={18} /><div><b>A prediction is not a guarantee</b><p>The planner can account for time and waiting in its known contact plan, but it does not know future contention from other bundles or guarantee future buffer admission. Sampling can also miss short visibility windows.</p></div></div>
          </section>

          <section className="about-section" id="time">
            <div className="about-section-heading"><span className="about-section-icon violet"><Clock3 size={18} /></span><div><span className="eyebrow">07 · REPEATABLE RUNS</span><h2>Simulation time, events, and seeds</h2></div></div>
            <p>The engine represents time as integer microseconds from the start of a run. It never reads wall-clock time to make a routing or forwarding decision. A run advances by processing the next event, ordered by timestamp, event priority, then a stable insertion sequence.</p>
            <div className="about-priority-list"><span>1 <b>Bundle expiration</b></span><span>2 <b>Contact end or interruption</b></span><span>3 <b>Contact start</b></span><span>4 <b>Serialization completion</b></span><span>5 <b>Arrival and receiver admission</b></span><span>6 <b>Bundle generation</b></span><span>7 <b>Routing and dispatch</b></span></div>
            <p>At an exact tie between expiry and delivery, expiry wins. In Simulation, the placement seed controls random orbital elements only when you add a random satellite group; changing it does not move satellites already in the setup. In paired preset comparisons, a versioned SHA-256 mapping gives each satellite a repeatable phase; the same seed and satellite ID receive the same phase, and both routing policies get the same realization.</p>
            <Formula note="For paired preset comparisons, hash the seed and stable satellite ID using the versioned phase mapping, then take the first 64 SHA-256 bits as U.">phase = 360 × U / 2⁶⁴</Formula>
            <Notation>
              <SymbolTerm symbol="phase" unit="degrees">Satellite phase assigned for this seeded comparison realization, from 0° up to (but not including) 360°.</SymbolTerm>
              <SymbolTerm symbol="U" unit="integer">Unsigned integer from 0 to 2⁶⁴ − 1, formed from the first 64 bits of the SHA-256 digest.</SymbolTerm>
              <SymbolTerm symbol="2⁶⁴">Number of possible 64-bit unsigned values; dividing U by this maps it to a fraction from 0 to 1.</SymbolTerm>
              <SymbolTerm symbol="seed; node_id" unit="integer; text">The explicit integer random seed and the satellite's stable text identifier used as inputs to the phase hash.</SymbolTerm>
              <Term name="SHA-256">A deterministic hash function; the project uses its first 64 output bits for U.</Term>
            </Notation>
            <p className="about-small-note">The hashed text is <code>leo-dtn-orbit-phase-v1:{"{seed}"}:{"{node_id}"}</code>. Identical seed and satellite ID therefore yield identical phases across paired presets.</p>
            <p className="about-small-note">Changing the scenario, seed, cutoff, orbit, sampling interval, minimum elevation, link rate, or traffic settings can change results. A seed is not a real-world date or a different physical orbit model.</p>
          </section>

          <section className="about-section" id="metrics">
            <div className="about-section-heading"><span className="about-section-icon cyan"><Gauge size={18} /></span><div><span className="eyebrow">08 · READING RESULTS</span><h2>Metrics and their formulas</h2></div></div>
            <p>Let H be the observation cutoff. The comparison dashboard runs both policies on the same scenario realization, generated bundle workload, seed, and cutoff, then averages the per-seed results.</p>
            <div className="about-metric-list">
              <article><div><b>Delivery ratio</b><span>How many attempted bundles reached their destination by H?</span></div><Formula>|D| / |G|</Formula><small>G includes every generation attempt, including source-buffer rejections. D includes bundles delivered by H.</small></article>
              <article><div><b>Delivery latency</b><span>How long did delivered bundles take?</span></div><Formula>delivery time − creation time</Formula><small>Mean and median use delivered bundles only; undelivered bundles get no invented latency.</small></article>
              <article><div><b>Hop count</b><span>How many successful transfers did a delivered bundle make?</span></div><Formula>successful receiver admissions</Formula><small>Failed attempts and interrupted transfers are not hops.</small></article>
              <article><div><b>Expiration ratio</b><span>How many generated bundles reached their TTL?</span></div><Formula>expired bundles / |G|</Formula><small>A bundle still pending at H is not expired just because it missed the cutoff.</small></article>
              <article><div><b>Mean buffer occupancy</b><span>Average stored payload bytes over time.</span></div><Formula>∫ occupancy(t) dt / H</Formula><small>Capacity fraction divides mean occupied bytes by total configured buffer capacity.</small></article>
              <article><div><b>Contact utilization</b><span>How much scheduled directed-link capacity carried completed payloads?</span></div><Formula>serialized payload bits / scheduled capacity bits</Formula><small>Scheduled capacity is rate × eligible contact duration clipped to the measured interval. Interrupted partial bits are discarded.</small></article>
            </div>
            <Notation>
              <SymbolTerm symbol="H" unit="μs">Observation cutoff: the simulated time at which outcomes are measured.</SymbolTerm>
              <SymbolTerm symbol="G">Set of all bundle-generation attempts made by time H, including source-buffer rejections.</SymbolTerm>
              <SymbolTerm symbol="D">Subset of G delivered to their destinations by time H.</SymbolTerm>
              <SymbolTerm symbol="|X|" unit="count">Number of elements in set X; therefore |D|/|G| is delivered bundles divided by generation attempts.</SymbolTerm>
              <SymbolTerm symbol="occupancy(t)" unit="bytes">Total payload bytes held in all node buffers at simulated time t.</SymbolTerm>
              <SymbolTerm symbol="t, ∫₀ᴴ" unit="μs">Simulated time and the time integral from the start of the run through cutoff H. Dividing byte-microseconds by H gives mean occupied bytes.</SymbolTerm>
            </Notation>
            <div className="about-horizon"><FlaskConical size={17} /><p><b>Cutoff means “not yet by this time”</b><br />At H, pending queued, transmitting, or propagating bundles count as undelivered for delivery ratio. They are right-censored at the cutoff, not automatically expired. The dashboard's small seed sweeps are descriptive and do not compute significance tests or confidence intervals.</p></div>
          </section>

          <section className="about-section" id="example">
            <div className="about-section-heading"><span className="about-section-icon blue"><ArrowRight size={18} /></span><div><span className="eyebrow">09 · WALK THROUGH IT</span><h2>A small worked example</h2></div></div>
            <p>Imagine two ground stations connected through one satellite. The bundle is 1,000 bytes. The first contact is open from 0 to 10 seconds at 8,000 bits per second. The second is open from 20 to 30 seconds at the same rate. Propagation delay is zero.</p>
            <div className="about-example-path"><div><span>0–10 s</span><b>Ground station A</b><small>Contact to relay is open</small></div><ArrowRight size={18} /><div className="example-node"><span>10–20 s</span><b>Satellite relay</b><small>Stores bundle and waits</small></div><ArrowRight size={18} /><div><span>20–30 s</span><b>Ground station B</b><small>Contact to destination is open</small></div></div>
            <ol className="about-example-list"><li><b>At 2 s:</b> the source creates and stores the bundle.</li><li><b>At 2 s:</b> the first contact can carry it. 1,000 bytes × 8 bits ÷ 8,000 bits/s = 1 second of serialization.</li><li><b>At 3 s:</b> the relay accepts it. It waits there because the next contact does not open until 20 s.</li><li><b>At 20 s:</b> the second transmission starts; the destination accepts the bundle at 21 s.</li></ol>
            <p>This example shows why a connected path in a static diagram is not enough: the route must also respect when each contact is available.</p>
          </section>

          <section className="about-section" id="limits">
            <div className="about-section-heading"><span className="about-section-icon amber"><ShieldAlert size={18} /></span><div><span className="eyebrow">10 · MODEL BOUNDARIES</span><h2>What the simulator does—and does not—claim</h2></div></div>
            <div className="about-limits-grid"><article><h3>Included</h3><ul><li>Deterministic discrete-event state transitions</li><li>Finite byte-capacity node buffers</li><li>Complete-bundle, single-copy forwarding</li><li>Circular two-body satellite motion</li><li>Spherical-Earth line-of-sight and minimum-elevation windows</li><li>Explicit seeds, event history, JSON/CSV exports, and paired comparisons</li></ul></article><article><h3>Not included</h3><ul><li>High-fidelity ephemerides, orbital perturbations, attitude, or maneuvering</li><li>RF link budgets, antenna patterns, weather, terrain, or operational access constraints</li><li>Fragmentation, partial-transfer resumption, custody acknowledgements, or full Bundle Protocol compliance</li><li>Future contention and buffer admission guarantees in the route planner</li><li>Persistent runs after the local API process restarts</li><li>Statistical significance from the small descriptive dashboard sweep</li></ul></article></div>
            <p>These limits are part of the model description, not small-print exceptions. Use the run manifest and exact settings when discussing results.</p>
          </section>

          <section className="about-section glossary-section" id="glossary">
            <div className="about-section-heading"><span className="about-section-icon violet"><BookOpen size={18} /></span><div><span className="eyebrow">11 · QUICK REFERENCE</span><h2>Glossary</h2></div></div>
            <p>Definitions used in the simulator and this guide.</p>
            <dl className="about-glossary">
              <Term name="API">Application Programming Interface. The FastAPI layer accepts validated commands and returns read-only simulation data.</Term>
              <Term name="Buffer">Finite node storage measured in bytes. A bundle must fit in the source or receiver buffer to be admitted.</Term>
              <Term name="Bundle">A complete payload with endpoints, size, creation time, TTL, current holder, status, and forwarding history.</Term>
              <Term name="Bundle Protocol (BP)">An IETF protocol family for delay- and disruption-tolerant networking. This simulator does not claim full BP compliance.</Term>
              <Term name="Contact">A directed opportunity to send data between two nodes, with a start, end, rate, and optional propagation delay.</Term>
              <Term name="Contact plan">The set of known scheduled contact windows available to the routing policy and engine.</Term>
              <Term name="Contact window">The interval when one directed contact is available. The interval is half-open: [start, end).</Term>
              <Term name="Contact-aware earliest arrival">The simulator's time-dependent policy. It searches the generated future contact plan for a feasible route with earliest predicted arrival.</Term>
              <Term name="Discrete-event simulation">A simulation that advances from one state-changing event to the next instead of updating every real-time instant.</Term>
              <Term name="ECEF">Earth-Centred, Earth-Fixed coordinates. The rotating frame used for the scene and fixed ground stations.</Term>
              <Term name="ECI">Earth-Centred Inertial coordinates. A non-rotating reference frame used for the circular orbit calculation.</Term>
              <Term name="Elevation angle">The angle of a satellite above a ground station's local horizon. A ground contact needs at least the configured minimum.</Term>
              <Term name="Event priority">The tie-break order for events with the same simulated timestamp; a stable insertion sequence breaks any remaining tie.</Term>
              <Term name="Expiry / TTL">The absolute time after which a bundle cannot be delivered. TTL means time-to-live and is measured from creation.</Term>
              <Term name="Ground station">A fixed point on the spherical Earth that can generate, receive, or relay bundles.</Term>
              <Term name="Horizon / cutoff">The measurement boundary for a run. In orbital mode, plan horizon can also refer to future-contact lookahead; the dashboard labels these separately.</Term>
              <Term name="Hop">One successful transfer where a receiver admits the whole bundle. A failed attempt is not a hop.</Term>
              <Term name="In transit">The bundle has finished serialization and is propagating to the receiver, but has not yet been admitted there.</Term>
              <Term name="LEO">Low Earth Orbit. The project models satellites above a spherical Earth using simplified circular orbits.</Term>
              <Term name="Mean motion (n)">The angular rate of a circular orbit, calculated as √(μ/r³), in radians per second.</Term>
              <Term name="Node">A network participant: a satellite or ground station with a buffer.</Term>
              <Term name="Propagation delay">The modeled travel delay after serialization. It defaults to zero unless configured.</Term>
              <Term name="RAAN (Ω)">Right ascension of the ascending node: the angle that orients an orbit plane around Earth's axis.</Term>
              <Term name="Right-censored bundle">A bundle not delivered by the observation cutoff. It counts as undelivered at that cutoff, but is not assumed to have expired.</Term>
              <Term name="Seed">An explicit number that initializes reproducible random choices, such as satellite phases in paired comparisons.</Term>
              <Term name="Serialization">Putting the bundle's bits onto a link at its configured rate; duration is rounded up to integer microseconds.</Term>
              <Term name="Static minimum hop">A baseline that chooses fewest hops in the union of known contacts and ignores their timing when selecting a path.</Term>
              <Term name="Store-carry-forward">Keeping a bundle at its current node until a later contact lets it move toward its destination.</Term>
              <Term name="Time-respecting route">A sequence of contacts whose ordering, waiting times, transfer durations, and contact windows make a journey feasible.</Term>
              <Term name="Transmission resource">The capacity of one directed contact. At most one bundle serializes on it at a time.</Term>
              <Term name="Two-body circular orbit">A simplified orbital model assuming a spherical Earth and gravity from Earth alone, with each satellite on a circular path.</Term>
            </dl>
          </section>

          <footer className="about-footer"><span>LEO-DTN · Local academic simulator</span><Link href="/">Return to the dashboard <ArrowRight size={14} /></Link></footer>
        </div>
      </div>
    </main>
  );
}
