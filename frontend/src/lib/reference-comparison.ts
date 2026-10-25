import type { RoutingPolicy } from "./contracts";

export type SavedPolicyResult = {
  policy: RoutingPolicy;
  deliveryRatio: number;
  deliveryRatioRange: [number, number];
  deliveredMean: number;
  deliveredRange: [number, number];
  undeliveredMean: number;
  sourceRejectedMean: number;
  expirationRatio: number;
  medianLatencySeconds: number | null;
  medianLatencyRangeSeconds: [number, number] | null;
  meanHops: number | null;
  meanHopsRange: [number, number] | null;
  contactUtilization: number;
  meanBufferMb: number;
};

export type SavedScenarioResult = {
  id: string;
  name: string;
  factor: string;
  generated: number;
  policies: SavedPolicyResult[];
};

// Generated with backend compare_routing_policies for seeds 42–46 at a
// 3,600-second cutoff. Means and ranges below are across the five individual
// per-seed runs; null latency/hops mean no bundle was delivered in those runs.
export const savedOneHourComparison: SavedScenarioResult[] = [
  {
    id: "leo-mumbai-new-york",
    name: "Mumbai–New York · baseline",
    factor: "Eight satellites · 50 MB bundles every 60 seconds",
    generated: 60,
    policies: [
      { policy: "contact_aware_earliest_arrival", deliveryRatio: 0.06, deliveryRatioRange: [0, 0.3], deliveredMean: 3.6, deliveredRange: [0, 18], undeliveredMean: 56.4, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: 2963.3121, medianLatencyRangeSeconds: [2963.3121, 2963.3121], meanHops: 4, meanHopsRange: [4, 4], contactUtilization: 0.0052903275, meanBufferMb: 1517.0989 },
      { policy: "static_minimum_hop", deliveryRatio: 0, deliveryRatioRange: [0, 0], deliveredMean: 0, deliveredRange: [0, 0], undeliveredMean: 60, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: null, medianLatencyRangeSeconds: null, meanHops: null, meanHopsRange: null, contactUtilization: 0, meanBufferMb: 1523.3333 },
    ],
  },
  {
    id: "leo-sparse-constellation",
    name: "Mumbai–New York · sparse constellation",
    factor: "Four satellites · baseline traffic and buffers",
    generated: 60,
    policies: [
      { policy: "contact_aware_earliest_arrival", deliveryRatio: 0.0133333333, deliveryRatioRange: [0, 0.0666666667], deliveredMean: 0.8, deliveredRange: [0, 4], undeliveredMean: 59.2, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: 1123.726033, medianLatencyRangeSeconds: [1123.726033, 1123.726033], meanHops: 4, meanHopsRange: [4, 4], contactUtilization: 0.0095336646, meanBufferMb: 1496.8414 },
      { policy: "static_minimum_hop", deliveryRatio: 0, deliveryRatioRange: [0, 0], deliveredMean: 0, deliveredRange: [0, 0], undeliveredMean: 60, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: null, medianLatencyRangeSeconds: null, meanHops: null, meanHopsRange: null, contactUtilization: 0.0081651884, meanBufferMb: 1523.3333 },
    ],
  },
  {
    id: "leo-limited-buffers",
    name: "Mumbai–New York · limited buffers",
    factor: "Eight satellites · 50 MB satellite buffers",
    generated: 60,
    policies: [
      { policy: "contact_aware_earliest_arrival", deliveryRatio: 0.0033333333, deliveryRatioRange: [0, 0.0166666667], deliveredMean: 0.2, deliveredRange: [0, 1], undeliveredMean: 59.8, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: 3439.3121, medianLatencyRangeSeconds: [3439.3121, 3439.3121], meanHops: 4, meanHopsRange: [4, 4], contactUtilization: 0.0237859148, meanBufferMb: 1522.8925 },
      { policy: "static_minimum_hop", deliveryRatio: 0, deliveryRatioRange: [0, 0], deliveredMean: 0, deliveredRange: [0, 0], undeliveredMean: 60, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: null, medianLatencyRangeSeconds: null, meanHops: null, meanHopsRange: null, contactUtilization: 0, meanBufferMb: 1523.3333 },
    ],
  },
  {
    id: "leo-high-traffic",
    name: "Mumbai–New York · high traffic",
    factor: "100 MB bundles every 15 seconds",
    generated: 240,
    policies: [
      { policy: "contact_aware_earliest_arrival", deliveryRatio: 0.0166666667, deliveryRatioRange: [0, 0.0833333333], deliveredMean: 4, deliveredRange: [0, 20], undeliveredMean: 236, sourceRejectedMean: 94.4, expirationRatio: 0, medianLatencySeconds: 3376.8121, medianLatencyRangeSeconds: [3376.8121, 3376.8121], meanHops: 4, meanHopsRange: [4, 4], contactUtilization: 0.017844781, meanBufferMb: 9806.3347 },
      { policy: "static_minimum_hop", deliveryRatio: 0, deliveryRatioRange: [0, 0], deliveredMean: 0, deliveredRange: [0, 0], undeliveredMean: 240, sourceRejectedMean: 140, expirationRatio: 0, medianLatencySeconds: null, medianLatencyRangeSeconds: null, meanHops: null, meanHopsRange: null, contactUtilization: 0, meanBufferMb: 7931.9444 },
    ],
  },
  {
    id: "leo-expanded-constellation",
    name: "Mumbai–New York · expanded constellation",
    factor: "Sixteen satellites · baseline traffic and buffers",
    generated: 60,
    policies: [
      { policy: "contact_aware_earliest_arrival", deliveryRatio: 0.3266666667, deliveryRatioRange: [0, 0.5333333333], deliveredMean: 19.6, deliveredRange: [0, 32], undeliveredMean: 40.4, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: 1314.830906, medianLatencyRangeSeconds: [20, 2627.3121], meanHops: 5.143124, meanHopsRange: [4.433333, 5.75], contactUtilization: 0.0038681984, meanBufferMb: 1188.9252 },
      { policy: "static_minimum_hop", deliveryRatio: 0, deliveryRatioRange: [0, 0], deliveredMean: 0, deliveredRange: [0, 0], undeliveredMean: 60, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: null, medianLatencyRangeSeconds: null, meanHops: null, meanHopsRange: null, contactUtilization: 0, meanBufferMb: 1523.3333 },
    ],
  },
];


// Backend paired comparison: baseline preset, seeds 42–46, 28,800-second (8-hour) cutoff.
export const savedEightHourComparison: SavedScenarioResult[] = [
  {
    id: "leo-mumbai-new-york",
    name: "Mumbai–New York · baseline",
    factor: "Eight satellites · 50 MB bundles every 60 seconds · 8-hour cutoff",
    generated: 480,
    policies: [
      { policy: "contact_aware_earliest_arrival", deliveryRatio: 0.6841666667, deliveryRatioRange: [0.56875, 0.81875], deliveredMean: 328.4, deliveredRange: [273, 393], undeliveredMean: 151.6, sourceRejectedMean: 0, expirationRatio: 0, medianLatencySeconds: 5538.782993, medianLatencyRangeSeconds: [4210.378728, 7830.522469], meanHops: 4.061669, meanHopsRange: [3.336996, 5.027439], contactUtilization: 0.0160343934, meanBufferMb: 4526.962044 },
      { policy: "static_minimum_hop", deliveryRatio: 0.17375, deliveryRatioRange: [0.1145833333, 0.2791666667], deliveredMean: 83.4, deliveredRange: [55, 134], undeliveredMean: 396.6, sourceRejectedMean: 133.2, expirationRatio: 0.1016666667, medianLatencySeconds: 19607.250664, medianLatencyRangeSeconds: [19395.622153, 20068.724275], meanHops: 2, meanHopsRange: [2, 2], contactUtilization: 0.0029392223, meanBufferMb: 8094.528813 },
    ],
  },
];
