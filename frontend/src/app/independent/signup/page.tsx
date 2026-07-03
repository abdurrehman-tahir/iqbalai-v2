import { Suspense } from "react";
import { IndependentSignupClient } from "./IndependentSignupClient";

export default function IndependentSignupPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <Suspense fallback={<p className="text-sm text-gray-500">Loading…</p>}>
          <IndependentSignupClient />
        </Suspense>
      </div>
    </div>
  );
}
