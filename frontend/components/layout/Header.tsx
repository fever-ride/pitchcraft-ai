"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

interface TokenPayload {
  email?: string;
  name?: string;
}

function decodeToken(token: string): TokenPayload | null {
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return null;
  }
}

export function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<TokenPayload | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login");
      return;
    }
    const payload = decodeToken(token);
    if (!payload) {
      router.replace("/login");
      return;
    }
    setUser(payload);
  }, [pathname, router]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    router.replace("/login");
  };

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-end px-6 shrink-0">
      {user && (
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-semibold">
              {(user.name || user.email || "?")[0].toUpperCase()}
            </div>
            <span className="text-sm text-gray-600 hidden sm:block">
              {user.name || user.email}
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-gray-900 border border-gray-200 rounded-md px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            Log out
          </button>
        </div>
      )}
    </header>
  );
}
