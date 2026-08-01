"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth-context";

// Matches BursaTrack.dc.html's `isApp` header block exactly (colors, spacing,
// hover/focus states). The design also shows a "Settings" nav item, a trial
// chip, and routes the avatar to a Settings page on click — all omitted here
// since no Settings page exists yet (Epic 5 territory). Same "don't build a
// link to a page that doesn't exist" discipline already applied to the
// Sell Calculator tab in FE-3.1. "Log out" has no equivalent in the design
// at all (it lives nowhere in the prototype), but is kept as a necessary,
// pre-existing deviation — there is no other way to end a session yet.
const NAV_ITEMS = [
  {
    href: "/dashboard",
    label: "Dashboard",
    isActive: (path: string) => path === "/dashboard" || path.startsWith("/positions/"),
  },
  {
    href: "/calendar",
    label: "Calendar",
    isActive: (path: string) => path.startsWith("/calendar"),
  },
];

export function AppHeader() {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const { user, logout } = useAuth();

  async function handleLogout() {
    await logout();
    router.push("/");
  }

  return (
    <div className="sticky top-0 z-40 border-b border-border bg-card">
      <div className="mx-auto flex h-[58px] max-w-[1200px] items-center gap-[26px] px-6">
        <Link href="/dashboard" className="mr-1.5 flex items-center gap-2.5 hover:no-underline">
          <div className="flex h-7 w-7 items-center justify-center rounded-[7px] bg-primary text-sm font-bold text-primary-foreground">
            B
          </div>
          <div className="text-[16.5px] font-bold tracking-[-0.01em] text-foreground">BursaTrack</div>
        </Link>

        <nav className="flex flex-1 gap-1">
          {NAV_ITEMS.map((item) => {
            const active = item.isActive(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-lg px-3.5 py-2 text-sm font-semibold hover:bg-muted hover:text-foreground hover:no-underline focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 ${
                  active ? "bg-muted text-foreground" : "text-muted-foreground"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {user && (
          <>
            <button
              type="button"
              onClick={handleLogout}
              className="cursor-pointer text-xs text-muted-foreground hover:text-foreground"
            >
              Log out
            </button>
            <div className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full border border-[#D5DEFC] bg-secondary text-[13px] font-bold text-secondary-foreground">
              {user.email.slice(0, 2).toUpperCase()}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
