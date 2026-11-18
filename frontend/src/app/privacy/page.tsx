import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const dynamic = "force-static";
export const metadata: Metadata = { title: "Privacy Policy" };

export default function Page() {
  return <LegalPage file="privacy.md" />;
}
