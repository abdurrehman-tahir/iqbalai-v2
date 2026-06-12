/**
 * T-029 — Districts admin page (Platform Admin only).
 * List + create. Districts are the root of the school org hierarchy (ARCH §3.3).
 */
import { DistrictsClient } from "./DistrictsClient";

export default function DistrictsPage() {
  return <DistrictsClient />;
}
