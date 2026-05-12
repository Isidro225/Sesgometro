import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { AlertsBell } from './AlertsBell';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `min-w-0 flex-1 basis-0 rounded-lg px-1 py-1.5 text-center text-xs font-medium transition sm:flex-none sm:basis-auto sm:px-3 sm:text-sm ${
    isActive ? 'bg-ink text-paper' : 'text-ink/70 hover:bg-ink/5 hover:text-ink'
  }`;

const menuItemClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition ${
    isActive ? 'bg-ink text-paper' : 'text-ink/70 hover:bg-ink/5 hover:text-ink'
  }`;

export function Layout() {
  const { user, logout, loading } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [menuOpen]);

  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="min-h-full bg-paper">
      <header className="border-b border-ink/10 bg-paper/80 backdrop-blur">
        <div className="flex w-full flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3 sm:flex-nowrap sm:px-8">
          <Link to="/" className="order-1 flex items-center text-ink transition hover:opacity-80">
            <img src="/icono.png" alt="Sesgómetro" className="h-11 w-auto" />
          </Link>
          <nav className="order-3 flex w-full items-center gap-1 sm:order-2 sm:w-auto sm:flex-1 sm:justify-center">
            <NavLink to="/" end className={navLinkClass}>
              Inicio
            </NavLink>
            <NavLink to="/portales" className={navLinkClass}>
              Portales
            </NavLink>
            <NavLink to="/historias" className={navLinkClass}>
              Historias
            </NavLink>
            <NavLink to="/categorias" className={navLinkClass}>
              Categorías
            </NavLink>
            {user && (
              <NavLink to="/favoritos" className={navLinkClass}>
                Favoritos
              </NavLink>
            )}
          </nav>
          <div className="order-2 flex items-center gap-2 text-sm sm:order-3">
            {loading ? null : (
              <>
                {user && <AlertsBell />}
                {user && <span className="hidden text-ink/60 sm:inline">{user.email}</span>}
                <div ref={menuRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setMenuOpen((open) => !open)}
                    aria-label={menuOpen ? 'Cerrar menú' : 'Abrir menú'}
                    aria-expanded={menuOpen}
                    aria-haspopup="menu"
                    className="relative flex h-10 w-10 items-center justify-center rounded-lg border border-ink/15 transition hover:border-ink"
                  >
                    <span className="sr-only">Menú</span>
                    <span className="relative block h-3.5 w-5">
                      <span
                        className={`absolute left-0 right-0 h-0.5 origin-center bg-ink transition-all duration-300 ease-out ${
                          menuOpen ? 'top-1.5 rotate-45' : 'top-0 rotate-0'
                        }`}
                      />
                      <span
                        className={`absolute left-0 right-0 top-1.5 h-0.5 bg-ink transition-all duration-300 ease-out ${
                          menuOpen ? 'scale-x-0 opacity-0' : 'scale-x-100 opacity-100'
                        }`}
                      />
                      <span
                        className={`absolute left-0 right-0 h-0.5 origin-center bg-ink transition-all duration-300 ease-out ${
                          menuOpen ? 'top-1.5 -rotate-45' : 'top-3 rotate-0'
                        }`}
                      />
                    </span>
                  </button>
                  <div
                    role="menu"
                    className={`absolute right-0 top-full z-50 mt-2 flex min-w-44 flex-col gap-1 rounded-xl border border-ink/10 bg-white p-2 shadow-lg transition-all duration-200 ease-out ${
                      menuOpen
                        ? 'translate-y-0 opacity-100'
                        : 'pointer-events-none -translate-y-2 opacity-0'
                    }`}
                  >
                    {user ? (
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          closeMenu();
                          logout();
                        }}
                        className="rounded-lg px-3 py-2 text-left text-sm font-medium text-ink/70 transition hover:bg-ink/5 hover:text-ink"
                      >
                        Salir
                      </button>
                    ) : (
                      <>
                        <NavLink
                          to="/login"
                          onClick={closeMenu}
                          role="menuitem"
                          className={menuItemClass}
                        >
                          Entrar
                        </NavLink>
                        <NavLink
                          to="/signup"
                          onClick={closeMenu}
                          role="menuitem"
                          className={({ isActive }) =>
                            `rounded-lg px-3 py-2 text-sm font-medium transition ${
                              isActive
                                ? 'bg-ink text-paper'
                                : 'bg-ink/90 text-paper hover:bg-ink'
                            }`
                          }
                        >
                          Crear cuenta
                        </NavLink>
                      </>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="w-full px-4 py-10 sm:px-8 sm:py-14">
        <Outlet />
      </main>
      <footer className="w-full px-4 pb-10 pt-4 text-xs text-ink/40 sm:px-8">
        Sesgómetro · El análisis es una estimación automática, no un veredicto absoluto.
      </footer>
    </div>
  );
}
