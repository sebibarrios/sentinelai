"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Dialog as DialogPrimitive } from "radix-ui";
import {
  FileUp,
  FolderKanban,
  LayoutDashboard,
  List,
  LogOut,
  Menu,
  Settings,
  Siren,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";

import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/table";
import { isUnauthorized, useLogout, useMe } from "@/hooks/use-auth";
import { capitalize, cn } from "@/lib/utils";
import type { Role } from "@/lib/types";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  minRole?: Role;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/alerts", label: "Alerts", icon: Siren },
  { href: "/incidents", label: "Incidents", icon: FolderKanban },
  { href: "/events", label: "Events", icon: List },
  { href: "/uploads", label: "Uploads", icon: FileUp },
];

const NAV_FOOTER: NavItem[] = [
  { href: "/admin/users", label: "Users", icon: Users, minRole: "admin" },
  { href: "/settings", label: "Settings", icon: Settings },
];

function NavLinks({ items, role, onNavigate }: { items: NavItem[]; role?: Role; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <ul className="flex flex-col gap-0.5">
      {items
        .filter((item) => !item.minRole || role === item.minRole)
        .map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <li key={href}>
              <Link
                href={href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-base transition-colors",
                  active
                    ? "bg-secondary font-medium text-foreground"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                )}
              >
                <Icon className={cn("size-4", active && "text-primary")} />
                {label}
              </Link>
            </li>
          );
        })}
    </ul>
  );
}

function SidebarContents({ role, onNavigate }: { role?: Role; onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <Link href="/dashboard" onClick={onNavigate} className="px-2 pt-1">
        <Logo />
      </Link>
      <nav aria-label="Main" className="flex flex-1 flex-col justify-between">
        <NavLinks items={NAV} role={role} onNavigate={onNavigate} />
        <NavLinks items={NAV_FOOTER} role={role} onNavigate={onNavigate} />
      </nav>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: me, error, isPending } = useMe();
  const logout = useLogout();
  const router = useRouter();
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (isUnauthorized(error)) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [error, router, pathname]);

  return (
    <div className="flex min-h-dvh">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 border-r bg-panel lg:block">
        <SidebarContents role={me?.role} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b bg-ink/90 px-4 backdrop-blur lg:px-8">
          <div className="flex items-center gap-2 lg:hidden">
            <DialogPrimitive.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
              <DialogPrimitive.Trigger asChild>
                <Button variant="ghost" size="icon" aria-label="Open navigation">
                  <Menu />
                </Button>
              </DialogPrimitive.Trigger>
              <DialogPrimitive.Portal>
                <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/60" />
                <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 w-64 border-r bg-panel">
                  <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
                  <DialogPrimitive.Close
                    className="absolute right-3 top-4 text-muted-foreground hover:text-foreground"
                    aria-label="Close navigation"
                  >
                    <X className="size-4" />
                  </DialogPrimitive.Close>
                  <SidebarContents role={me?.role} onNavigate={() => setDrawerOpen(false)} />
                </DialogPrimitive.Content>
              </DialogPrimitive.Portal>
            </DialogPrimitive.Root>
            <Logo compact />
          </div>
          <div className="hidden lg:block" />

          {isPending ? (
            <Skeleton className="h-8 w-36" />
          ) : me ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-3 rounded-md px-2 py-1 text-left hover:bg-secondary">
                  <span className="grid size-8 place-items-center rounded-full bg-secondary text-sm font-semibold">
                    {me.full_name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden flex-col leading-tight sm:flex">
                    <span className="text-base font-medium">{me.full_name}</span>
                    <span className="text-xs text-muted-foreground">{capitalize(me.role)}</span>
                  </span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>
                  <div className="text-base font-medium">{me.full_name}</div>
                  <div className="text-sm text-muted-foreground">{me.email}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => router.push("/settings")}>
                  <Settings /> Settings
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => logout.mutate()}>
                  <LogOut /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
