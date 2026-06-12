import { redirect } from "next/navigation";

/** Orphan route — redirect into the ToS tab (T-231). */
export default function DisclaimerPage() {
  redirect("/admin/tos?tab=disclaimer");
}
