import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const dynamic = "force-static";
export const metadata: Metadata = { title: "Terms of Service" };

export default function Page() {
  return <LegalPage file="terms.md" />;
}
