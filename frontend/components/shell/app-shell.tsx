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
  PanelLeftClose,
  PanelLeftOpen,
  Scan,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { BakufuLockup } from "@/components/brand/logo-b";
import { LIVE_MODE } from "@/lib/api/client";
import { SheetFrame } from "./sheet-frame";
import styles from "./app-shell.module.css";

/** Remembers a collapsed sidebar across visits; a per-viewer convenience only. */
const COLLAPSE_KEY = "bakufu-sidebar-collapsed";

/** Routes whose figures come from the FastAPI backend in live mode. */
const LIVE_ROUTES = new Set(["/operations", "/mines", "/production", "/actions", "/explorer"]);

const navigationGroups = [
  {
    label: "Operations",
    items: [
      { href: "/operations", label: "Command Center", icon: LayoutDashboard, sheet: "01" },
      { href: "/mines", label: "Mine Fleet", icon: MapPin, sheet: "11" },
      {
        href: "/production",
        label: "Production & Risk",
        icon: ChartNoAxesCombined,
        sheet: "03",
      },
      { href: "/actions", label: "Corrective Actions", icon: ListChecks, sheet: "04" },
      { href: "/assets", label: "Assets & Inventory", icon: Archive, sheet: "05" },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/explorer", label: "Prospectivity", icon: Scan, sheet: "02" },
      {
        href: "/feedback",
        label: "Geologist Feedback",
        icon: MessageSquareText,
        sheet: "06",
      },
      { href: "/pipeline", label: "Data Pipeline", icon: Database, sheet: "07" },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/compliance", label: "Compliance", icon: FileCheck2, sheet: "08" },
      { href: "/reports", label: "Reports & Exports", icon: FileOutput, sheet: "09" },
      { href: "/admin", label: "Administration & RBAC", icon: ShieldCheck, sheet: "10" },
    ],
  },
];

/** Sheets in the atlas, counted rather than written down, so a new module
 * cannot leave the header claiming the old total. */
const SHEET_TOTAL = String(navigationGroups.reduce((total, group) => total + group.items.length, 0)).padStart(2, "0");

function isActive(pathname: string, href: string) {
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
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

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "true");
    } catch {
      // Storage can be blocked; the sidebar simply starts expanded.
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, String(next));
      } catch {
        // Not persisted when storage is unavailable.
      }
      return next;
    });
  }

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
      data-theme="dark"
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
        <button
          type="button"
          className={styles.collapseButton}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          aria-controls="workspace-sidebar"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={toggleCollapsed}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} strokeWidth={1.6} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={18} strokeWidth={1.6} aria-hidden="true" />
          )}
        </button>
        <div className={styles.context}>
          {activeItem && <span className={styles.sheetRef}>Sheet {activeItem.sheet} / {SHEET_TOTAL}</span>}
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
      <div className={styles.body} data-collapsed={collapsed}>
        <aside
          id="workspace-sidebar"
          className={styles.sidebar}
          data-theme="dark"
          data-open={menuOpen}
          aria-label="Workspace modules"
        >
          <div className={styles.workspaceLabel}><span className={styles.workspaceMonogram}>B</span><div><strong>Mineral intelligence</strong><small>Research workspace</small></div></div>
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
                        title={collapsed ? label : undefined}
                      >
                        <Icon size={17} strokeWidth={1.6} aria-hidden="true" />
                        <span className={styles.linkLabel}>{label}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </nav>
          <div className={styles.sidebarFooter}>
            <MapPin size={15} aria-hidden="true" />
            <div className={styles.footerText}>
              <strong>Sausar Belt, India</strong>
              <p>Validated geographic scope</p>
            </div>
          </div>
        </aside>
        <div className={`workspace-main ${styles.mainColumn}`}>
          <SheetFrame />
          <main
            ref={main}
            id="main-content"
            tabIndex={-1}
            className={`workspace-content ${styles.content}`}
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
