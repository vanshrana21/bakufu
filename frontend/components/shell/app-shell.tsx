"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Archive,
  ChartNoAxesCombined,
  Database,
  FileCheck2,
  FileOutput,
  FlaskConical,
  LayoutDashboard,
  ListChecks,
  MapPin,
  Menu,
  MessageSquareText,
  Scan,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { BakufuLockup } from "@/components/brand/logo-b";
import { LIVE_MODE } from "@/lib/api/client";
import styles from "./app-shell.module.css";

/** Routes whose figures come from the FastAPI backend in live mode. */
const LIVE_ROUTES = new Set(["/operations", "/production", "/actions", "/explorer"]);

const navigationGroups = [
  {
    label: "Operations",
    items: [
      { href: "/operations", label: "Command Center", icon: LayoutDashboard },
      {
        href: "/production",
        label: "Production & Risk",
        icon: ChartNoAxesCombined,
      },
      { href: "/actions", label: "Corrective Actions", icon: ListChecks },
      { href: "/assets", label: "Assets & Inventory", icon: Archive },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/explorer", label: "Prospectivity", icon: Scan },
      {
        href: "/feedback",
        label: "Geologist Feedback",
        icon: MessageSquareText,
      },
      { href: "/pipeline", label: "Data Pipeline", icon: Database },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/compliance", label: "Compliance", icon: FileCheck2 },
      { href: "/reports", label: "Reports & Exports", icon: FileOutput },
      { href: "/admin", label: "Administration & RBAC", icon: ShieldCheck },
    ],
  },
];

function isActive(pathname: string, href: string) {
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const main = useRef<HTMLElement>(null);
  const activeGroup = navigationGroups.find((group) =>
    group.items.some((item) => isActive(pathname, item.href)),
  );
  const activeItem = activeGroup?.items.find((item) =>
    isActive(pathname, item.href),
  );
  // Only these routes read the backend; every other module is a demonstration
  // snapshot. Without an API configured, every route renders fixtures.
  const showDemoBadge =
    !LIVE_MODE || !activeItem || !LIVE_ROUTES.has(activeItem.href);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  function navigate() {
    if (menuOpen) {
      setMenuOpen(false);
      // Inline disclosure, not a modal: transfer focus out of the closed navigation.
      main.current?.focus();
    }
  }

  return (
    <div
      className="workspace"
      onKeyDown={(event) => {
        if (event.key === "Escape" && menuOpen) {
          event.preventDefault();
          setMenuOpen(false);
          menuButton.current?.focus();
        }
      }}
    >
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <header className={styles.header} data-theme="dark">
        <Link
          href="/"
          className={styles.brand}
          aria-label="BAKUFU home"
          onClick={navigate}
        >
          <BakufuLockup size={28} />
        </Link>
        <div className={styles.context}>
          <span>{activeGroup?.label}</span>
          <span aria-hidden="true">/</span>
          <strong>{activeItem?.label}</strong>
        </div>
        <div className={styles.status}>
          {showDemoBadge && (
            <span>
              <FlaskConical size={12} aria-hidden="true" /> Demo data
            </span>
          )}
          <small>MOIL-oriented prototype</small>
        </div>
        <Button
          ref={menuButton}
          type="button"
          variant="outline"
          className={styles.menuButton}
          aria-label="Toggle navigation"
          aria-expanded={menuOpen}
          aria-controls="workspace-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? (
            <X size={18} aria-hidden="true" />
          ) : (
            <Menu size={18} aria-hidden="true" />
          )}
          <span>Menu</span>
        </Button>
      </header>
      <div className={styles.body}>
        <aside
          className={styles.sidebar}
          data-theme="dark"
          data-open={menuOpen}
          aria-label="Workspace modules"
        >
          <nav
            id="workspace-navigation"
            aria-label="Main navigation"
            className={styles.navigation}
          >
            {navigationGroups.map((group) => (
              <section key={group.label} aria-label={group.label}>
                <h2 className={styles.groupLabel}>{group.label}</h2>
                <ul>
                  {group.items.map(({ href, label, icon: Icon }) => (
                    <li key={href}>
                      <Link
                        href={href}
                        aria-label={label}
                        aria-current={
                          isActive(pathname, href) ? "page" : undefined
                        }
                        onClick={navigate}
                      >
                        <Icon size={17} strokeWidth={1.6} aria-hidden="true" />
                        <span>{label}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </nav>
          <div className={styles.sidebarFooter}>
            <MapPin size={15} aria-hidden="true" />
            <div>
              <strong>Sausar Belt, India</strong>
              <p>Validated geographic scope</p>
            </div>
          </div>
        </aside>
        <div className={`workspace-main ${styles.mainColumn}`}>
          <div className={styles.scopeStrip}>
            <span>Sausar Belt · Gondite geology</span>
            <span>September 2026 scenario</span>
          </div>
          <main
            ref={main}
            id="main-content"
            tabIndex={-1}
            className="workspace-content"
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
