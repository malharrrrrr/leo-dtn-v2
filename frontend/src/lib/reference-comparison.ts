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

// Backend paired comparison: baseline preset, seeds 42–46, 28,800-second (8-hour) cutoff.
export const savedReferenceComparison: SavedScenarioResult[] = [
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
