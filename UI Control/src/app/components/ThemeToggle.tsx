import { useEffect, useState } from 'react';
import { Check, Laptop, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

const OPTIONS = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Laptop },
] as const;

/** Light / Dark / System switch. The choice is saved by next-themes (localStorage `hc-studio-theme`). */
export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  // next-themes only knows the real theme after mount; avoid a mismatched first paint.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === 'dark';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Change colour theme"
          title="Theme"
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-300 bg-card text-slate-700 shadow-xs transition hover:bg-slate-50 active:bg-slate-100 cursor-pointer"
        >
          {isDark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        {OPTIONS.map(({ value, label, Icon }) => (
          <DropdownMenuItem key={value} onClick={() => setTheme(value)} className="cursor-pointer gap-2 text-xs">
            <Icon className="h-3.5 w-3.5" />
            <span className="flex-1">{label}</span>
            {mounted && theme === value && <Check className="h-3.5 w-3.5 text-sky-600" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
