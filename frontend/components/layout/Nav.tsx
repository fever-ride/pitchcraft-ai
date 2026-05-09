"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Home" },
  { href: "/clients", label: "Clients" },
  { href: "/pipeline", label: "New Proposal" },
  { href: "/files", label: "Files" },
  { href: "/resources", label: "Resources" },
  { href: "/research", label: "Research" },
  { href: "/analytics", label: "Analytics" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="border-b bg-white px-6 py-3 flex items-center gap-6">
      <span className="font-bold text-lg">Pitchcraft</span>
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={`text-sm ${
            pathname === link.href
              ? "text-blue-600 font-medium"
              : "text-gray-600 hover:text-gray-900"
          }`}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
