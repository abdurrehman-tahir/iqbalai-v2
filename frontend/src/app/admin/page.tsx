import { redirect } from "next/navigation";

// Dashboard root redirects to Languages (first nav item)
export default function AdminPage() {
  redirect("/admin/languages");
}
