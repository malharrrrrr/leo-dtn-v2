# Routing policies

## Policy boundary

A routing policy receives a read-only view of bundle, node, contact-plan, time, and relevant resource/buffer state and returns a proposed next contact/neighbor or no route. The engine owns validation, queueing, transmission, admission, expiry, and all state mutation. This boundary permits policy comparison without changing event semantics.

## Initial comparison

The static minimum-hop path in the union of known contacts is a deliberately weak baseline. It does not account for contact timing, so a selected hop may be unavailable now and waiting may make its path stale. It is useful to demonstrate why static connectivity is insufficient, not as a strong DTN algorithm.

The recommended contact-aware strategy computes a time-respecting earliest-arrival path over precomputed future contacts, allowing waiting at nodes. Edge traversal duration is serialization plus propagation; each contact must fit the full serialization interval. It returns the first hop of the path and re-evaluates on state changes. The algorithm is myopic with respect to contention unless it explicitly models scheduled reservations and other bundles. It knows the declared future contact plan; no predicted contact or arrival may be presented as observed fact.

Do not call either policy Contact Graph Routing (CGR), Epidemic Routing, or another established algorithm merely because it uses contacts or shortest paths. A published algorithm claim requires implementing its defining contact graph, route ranking/selection, queue/capacity assumptions, replication/custody behavior where applicable, and citing its primary specification/paper. In particular, defer a CGR conformance claim until the applicable BPv7 Bundle Protocol specification and CGR reference are selected and behavior is checked against them.

Primary references for future protocol/algorithm work are the IETF's [Bundle Protocol Version 7 specification, RFC 9171](https://www.rfc-editor.org/rfc/rfc9171.html) and the NASA Technical Reports Server entry for [Contact Graph Routing](https://ntrs.nasa.gov/search.jsp?R=20120006508). They are reference points, not a claim that this simulator implements BPv7 or CGR. A future conformance milestone must select the applicable specifications, implement their relevant behavior, and validate against suitable examples; the current single-copy atomic-hop model is intentionally simpler.

## Knowledge and limitations

| Policy | Future contacts | Time ordering | Contention/buffer awareness | Main limitation |
|---|---|---|---|---|
| Static minimum-hop baseline | Contact union only | No | No | May wait on a poor or infeasible next hop |
| Time-dependent earliest arrival | Yes, precomputed plan | Yes | Current state can be checked; future contention initially ignored | Predicted path may not execute as planned |

For fair results, record policy name/version and all contact-plan knowledge assumptions. Use identical scenario, generated bundles, seed, and run horizon when comparing strategies.
