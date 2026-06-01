import { Sidebar } from "@/components/sidebar";
import { requireOwner } from "@/lib/auth";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireOwner();
  return (
    <div className="flex min-h-dvh">
      <Sidebar />
      <main className="flex-1 overflow-x-auto">{children}</main>
    </div>
  );
}
