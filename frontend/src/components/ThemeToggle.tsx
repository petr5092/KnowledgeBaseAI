// src/components/ThemeToggle.tsx
import { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const [isDark, setIsDark] = useState(
    () => document.documentElement.classList.contains('dark')
  );

  useEffect(() => {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const shouldBeDark = saved === 'dark' || (!saved && prefersDark);

    if (shouldBeDark !== document.documentElement.classList.contains('dark')) {
      if (shouldBeDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
    setIsDark(shouldBeDark);
    // Это безопасно: один раз при монтировании синхронизируем состояние с DOM
  }, []);

  const toggle = () => {
    const newDark = !document.documentElement.classList.contains('dark');

    if (newDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }

    setIsDark(newDark);
  };

  return (
    <button
      onClick={toggle}
      className="px-3 py-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors text-sm font-medium"
      aria-label="Переключить тему"
      title="Переключить тему"
    >
      {isDark ? 'Светлая' : 'Тёмная'}
    </button>
  );
}